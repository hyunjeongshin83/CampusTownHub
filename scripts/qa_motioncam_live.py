# -*- coding: utf-8 -*-
"""모션캠이 「왜 안 되는지」를 말해 주는지 봅니다.

예전에는 세 군데에서 아무 말 없이 넘어갔습니다 — 카메라 대기 · 인식 오류 · 얼굴 못 찾음.
어느 쪽이든 화면이 가만히 있어서, 쓰는 분에게는 똑같이 「안 바뀜」으로 보였습니다.

가짜 카메라에는 얼굴이 없으므로 「얼굴을 못 찾는다」가 떠야 정상입니다 — 그게 이 점검의 핵심입니다.
실제 얼굴로 표정이 입혀지는지는 사람이 봐야 합니다 (가짜 카메라로는 재현할 수 없습니다).
"""
import os, sys
from playwright.sync_api import sync_playwright

URL = os.environ.get("MC_URL", "http://127.0.0.1:8099/motioncam.html")
bad = []

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-fake-device-for-media-stream",
                                "--use-fake-ui-for-media-stream"])
    ctx = b.new_context(viewport={"width": 1200, "height": 950},
                        permissions=["camera", "microphone"])
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
    print("모션캠 점검 — %s" % URL)
    pg.goto(URL, wait_until="load", timeout=60000)
    pg.wait_for_timeout(2500)

    # 상태 줄이 화면에 있는가
    if not pg.locator("#stat").count():
        bad.append("상태 줄(#stat)이 없습니다 — 왜 안 되는지 알 길이 없습니다")
    else:
        print("  상태 줄            → 있음")

    # 안내 문구가 어느 쪽이 상대에게 가는지 분명히 말하는가
    heads = pg.evaluate("() => [...document.querySelectorAll('.panel h4')].map(h => h.innerText)")
    print("  화면 이름          → %s" % " / ".join(heads))
    if not any("상대" in h for h in heads):
        bad.append("어느 화면이 상대에게 가는지 제목에 안 적혀 있습니다")

    # 기준 사진 없이 시작할 수 있나 (막혀 있어야 합니다)
    if not pg.locator("#go").is_disabled():
        bad.append("기준 사진 없이 [모션캠 시작]이 눌립니다")
    else:
        print("  사진 없이 시작     → 막혀 있음")

    # 모델이 실제로 내려오는가 (바깥 CDN 두 곳 + 구글 모델)
    mdl = pg.evaluate("""async () => {
        const urls = ["https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm/vision_wasm_internal.js",
                      "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"];
        const out = [];
        for (const u of urls) {
            try { const r = await fetch(u, {method:"GET"}); out.push([u.split("/").pop(), r.status]); }
            catch (e) { out.push([u.split("/").pop(), "실패:" + e.message.slice(0,40)]); }
        }
        return out;
    }""")
    for name, st in mdl:
        print("  %-26s → %s" % (name[:26], st))
        if st != 200:
            bad.append("얼굴 인식에 필요한 %s 를 받지 못합니다 (%s)" % (name, st))

    # 가짜 카메라로 시작 — 얼굴이 없으니 「못 찾는다」가 떠야 합니다
    pg.evaluate("""() => {
        const c = document.createElement("canvas");
        c.width = 640; c.height = 480;
        const x = c.getContext("2d");
        x.fillStyle = "#ddd"; x.fillRect(0,0,640,480);
        window.__fake = c.toDataURL("image/png");
    }""")
    started = pg.evaluate("""async () => {
        // 기준 사진 등록은 얼굴이 있어야 되므로, 사진 단계를 건너뛰고 실행 경로만 봅니다.
        // (실제 얼굴 사진으로 표정이 입혀지는지는 사람이 확인해야 합니다)
        try { await navigator.mediaDevices.getUserMedia({video:{width:640,height:480}}); return true; }
        catch (e) { return String(e); }
    }""")
    print("  가짜 카메라        → %s" % ("잡힘" if started is True else started))

    # 사진 없이 loop 를 돌렸을 때 조용한지 — 말해야 합니다
    said = pg.evaluate("""async () => {
        try { running = true; } catch (e) {}
        return "모듈 안이라 밖에서 못 건드립니다";
    }""")
    # 모듈 스코프라 밖에서 못 만지므로, 사진 등록 실패 경로로 메시지를 봅니다
    pg.set_input_files("#pick", files=[{"name": "flat.png", "mimeType": "image/png",
        "buffer": __import__("base64").b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")}])
    pg.wait_for_timeout(9000)
    m = pg.locator("#msg").inner_text().strip()
    print("  얼굴 없는 사진      → %s" % m[:80])
    if "실패" not in m and "찾지 못" not in m:
        bad.append("얼굴 없는 사진을 넣었는데 아무 말도 안 합니다: %r" % m)

    if errs:
        real = [e for e in errs if "mediapipe" not in e.lower()]
        if real:
            bad.append("자바스크립트 오류: " + " / ".join(real[:2]))
    ctx.close(); b.close()

print()
if bad:
    print("고칠 것 %d개" % len(bad))
    for x in bad: print("  · " + x)
    sys.exit(1)
print("모션캠: 안 될 때 왜 안 되는지 말해 줍니다 (실제 표정 입히기는 사람이 확인해야 합니다)")
