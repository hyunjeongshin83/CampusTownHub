# -*- coding: utf-8 -*-
"""화상회의를 진짜 서버에 붙여 봅니다.

scripts/qa_video.py 는 가짜 Jitsi 로 허브 쪽 배선만 봅니다 — 빠르고 요금도 없지만,
「진짜 화상이 되느냐」는 확인하지 못합니다. 이 점검은 그 빈칸을 메웁니다.

  · meet.jit.si/external_api.js 가 실제로 내려오는가
  · 방이 진짜 열리고 videoConferenceJoined 가 오는가
  · 카메라·마이크 권한을 요구할 때 화면이 뜨는가 (가짜 장치로 대신 봅니다)

바깥 서버(meet.jit.si)에 붙으므로 CI 에서 매번 돌리지 않습니다 — 회의 전에 손으로 돌립니다.
"""
import os, sys, time
from playwright.sync_api import sync_playwright

SITE = os.environ.get("SITE", "https://hyunjeongshin83.github.io/CampusTownHub")
ROOM = os.environ.get("ROOM", "mediths-qa-" + str(int(time.time())))
fails, net = [], []
JITSI_EMBEDDABLE = {"jitsi.riot.im", "meet.jit.si"}   # 임베드가 되는 서버 (새 창 전용과 섞이면 안 됩니다)

with sync_playwright() as p:
    b = p.chromium.launch(args=[
        "--use-fake-device-for-media-stream",   # 컨테이너에는 카메라가 없습니다
        "--use-fake-ui-for-media-stream",       # 권한 창을 자동 허용
        "--autoplay-policy=no-user-gesture-required",
    ])
    ctx = b.new_context(viewport={"width": 1280, "height": 900},
                        permissions=["camera", "microphone"])
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    pg.on("response", lambda r: net.append((r.url, r.status))
          if "jit.si" in r.url or "jitsi" in r.url else None)

    print("화상회의 실제 점검 — %s" % SITE)
    print("  방 이름: %s" % ROOM)
    pg.goto(SITE + "/index.html?ci=1", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(4000)

    # ── 1. 진짜 external_api.js 가 내려오는가 ──
    got = pg.evaluate("""async () => {
        try { await loadJitsiApi(); }
        catch (e) { return {ok: false, why: e.message || String(e)}; }
        return {ok: !!window.JitsiMeetExternalAPI,
                type: typeof window.JitsiMeetExternalAPI};
    }""")
    if not got.get("ok"):
        fails.append("화상 라이브러리를 못 받았습니다: %s" % got.get("why", got))
        print("  external_api.js  → 실패 (%s)" % got.get("why"))
    else:
        print("  external_api.js  → 받았습니다 (%s)" % got["type"])

    # ── 2. 허브의 실제 흐름으로 방을 엽니다 (가짜 Jitsi 아님) ──
    #   예전 점검은 raw API 로만 열어 봐서, 허브가 실제로 쓰는 설정·서버가 빠졌습니다.
    if got.get("ok"):
        pg.evaluate("""() => {
            state.user={role:'operator',name:'점검',email:'qa@example.invalid',id:'u'};
            state.meetings=[{id:'m1',title:'화상 점검',date:'2026-10-22',time:'16:30',
                             attendees:[{name:'점검'}]}];
            state.currentMeetingId='m1'; syncCurrentMeeting();
            state.meeting.started=null; state.segments=[];
            document.body.insertAdjacentHTML('beforeend',
              '<div id="vFrame" style="width:900px;height:520px"></div><div id="vAfter"></div>'
              +'<div id="vTranscript"></div><span id="vSegCount"></span><span id="vMicState"></span>'
              +'<input id="vTypeInput"><button id="vTypeAdd"></button>'
              +'<button id="vMicBtn"></button><select id="vMicWho"></select><span id="vMicHint"></span>'
              +'<button id="vKakao"></button><button id="vGuess"></button><button id="vClear"></button>');
        }""")
        print("  쓰는 서버         → %s" % pg.evaluate("() => JITSI_HOST"))
        pg.evaluate("() => { startJitsi(); }")

        joined = False
        for i in range(16):
            pg.wait_for_timeout(5000)
            st = pg.evaluate("""() => {
                const f = document.querySelector("#vFrame iframe");
                let inner = "";
                return {started: !!state.meeting.started,
                        joined: !!jitsiJoinedAt,
                        iframe: !!f,
                        host: JITSI_HOST,
                        after: (document.getElementById("vAfter").innerText||"").replace(/\s+/g," ").slice(0,70)};
            }""")
            if st["joined"]:
                joined = True
                print("  방 입장           → %d초에 들어갔습니다 (%s)" % ((i+1)*5, st["host"]))
                break
            if i == 2:
                print("  %2d초              iframe=%s 서버=%s" % ((i+1)*5, st["iframe"], st["host"]))
        if not joined:
            # 공개 Jitsi 는 사람이 [Join meeting] 을 눌러야 들어갑니다 — 자동으로는 여기까지가 한계입니다.
            # 그래서 「프레임이 떴고 프리조인 화면이 보이는가」까지만 봅니다.
            inner = ""
            for f in pg.frames:
                if any(x in f.url for x in ["jitsi", "jit.si", "ffmuc"]):
                    try:
                        inner = f.evaluate("() => (document.body.innerText||'').replace(/\\n+/g,' | ').slice(0,180)")
                    except Exception:
                        inner = "(못 읽음)"
            print("  프레임 안          → %s" % (inner[:110] or "(빈 화면)"))
            if "Join meeting" in inner:
                print("  방 입장           → 프리조인까지 정상 (사람이 [Join meeting] 을 눌러야 들어갑니다)")
            elif "moderator" in inner.lower():
                fails.append("화상 서버가 로그인한 주최자를 요구합니다 — 이 서버로는 회의를 못 엽니다: %s" % inner[:120])
            elif not inner:
                fails.append("화상 화면이 아예 안 떴습니다 (iframe 로드 실패 — 임베드가 막힌 서버일 수 있습니다)")
            else:
                fails.append("방이 열리지 않았습니다: %s" % inner[:120])

        # 새 창 길이 살아 있는지 — 허브 안에서 안 될 때의 유일한 대안입니다
        win = pg.evaluate("() => ({link: jitsiWindowLink(), host: JITSI_WINDOW_HOST, room: jitsiRoom()})")
        print("  새 창 길           → %s" % win["link"])
        if win["host"] in JITSI_EMBEDDABLE:
            fails.append("새 창 서버가 임베드 가능한 서버입니다 — 새 창 전용 서버를 따로 둬야 합니다")
        if win["room"] not in win["link"]:
            fails.append("새 창 주소의 방 이름이 허브 안의 방과 다릅니다 — 참석자가 서로 다른 방에 들어갑니다")

        shape = pg.evaluate("""() => {
            const f = document.querySelector("#vFrame iframe");
            if (!f) return {iframe: false};
            const r = f.getBoundingClientRect();
            return {iframe: true, w: Math.round(r.width), h: Math.round(r.height),
                    src: (f.src || "").slice(0, 70)};
        }""")
        if not shape.get("iframe"):
            fails.append("화상 화면(iframe)이 안 만들어졌습니다")
        else:
            print("  화면              → %d×%d · %s" % (shape["w"], shape["h"], shape["src"]))

        dev = pg.evaluate("""async () => {
            try { const s = await navigator.mediaDevices.getUserMedia({audio:true, video:true});
                  const n = {a: s.getAudioTracks().length, v: s.getVideoTracks().length};
                  s.getTracks().forEach(t => t.stop()); return n; }
            catch (e) { return {err: e.name}; }
        }""")
        print("  장치              → %s" % (dev.get("err") or ("마이크 %d · 카메라 %d (가짜)" % (dev["a"], dev["v"]))))
        sr = pg.evaluate("() => !!(window.SpeechRecognition || window.webkitSpeechRecognition)")
        print("  음성 녹취 기능     → %s" % ("있음" if sr else "없음"))

    print("── 네트워크 ──")
    seen = {}
    for u, s in net:
        k = u.split("?")[0]
        seen.setdefault(k, s)
    for u, s in list(seen.items())[:8]:
        mark = "OK " if s < 400 else "!! "
        print("  %s%s  %s" % (mark, s, u[:92]))
        if s >= 400 and "external_api" in u:
            fails.append("external_api.js 가 %d 로 떨어집니다" % s)

    if errs:
        real = [e for e in errs if "jitsi" not in e.lower()]
        if real:
            print("── 페이지 오류 ──")
            for e in real[:3]:
                print("  " + e)
    ctx.close(); b.close()

print()
if fails:
    print("문제 %d개" % len(fails))
    for f in fails:
        print("  · " + f)
    sys.exit(1)
print("화상회의: 진짜 서버에 붙고 방이 열립니다")
