# -*- coding: utf-8 -*-
"""미팅 예약 신청이 실제로 되는지 봅니다.

바깥 분이 쓰는 길이라 두 가지를 같이 봅니다.
  1) 로그인 없이 신청 창이 열리고, 빈 칸·동의 없이는 안 보내지는지
  2) 들어온 신청을 보는 길이 로그인 없이는 막혀 있는지 (신청에 남의 연락처가 있습니다)

실제 신청은 보내지 않습니다 — 보내는 단추는 누르지 않고, 막는 길만 서버에 물어봅니다.
"""
import os, re, sys, json, pathlib, urllib.request, urllib.error
from playwright.sync_api import sync_playwright


def _lum(c):
    c = [x / 255 for x in c]
    c = [(x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4) for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def rgb(s):
    m = re.findall(r"[\d.]+", s or "")
    return tuple(int(float(x)) for x in m[:3]) if len(m) >= 3 else (0, 0, 0)

ROOT = pathlib.Path(__file__).resolve().parent.parent
URL = os.environ.get("HUB_URL", "http://127.0.0.1:8111/index.html")
FN = "https://xaclqvveppvccdpebzsz.supabase.co/functions/v1/demo-request"
ORIGIN = "https://hyunjeongshin83.github.io"

bad = []


def post(body, headers=None, origin=ORIGIN):
    h = {"Content-Type": "application/json", "Origin": origin}
    h.update(headers or {})
    req = urllib.request.Request(FN, data=json.dumps(body).encode(), headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "error": "http_%d" % e.code}
    except Exception as e:
        return {"ok": False, "error": "net:%s" % e}


def server_checks():
    print("── 서버 쪽 ──")
    # 목록 보기는 토큰 없이 막혀야 합니다 (신청자 연락처가 들어 있습니다)
    d = post({"action": "list"})
    ok = d.get("error") in ("forbidden", "unauthorized")
    print("  목록 보기, 토큰 없음   → %s" % json.dumps(d, ensure_ascii=False))
    if not ok:
        bad.append("토큰 없이 신청 목록이 보입니다 — 남의 연락처가 새어 나갑니다: %s" % d)

    d = post({"action": "mark", "id": "00000000-0000-0000-0000-000000000000", "status": "done"})
    if d.get("error") not in ("forbidden", "unauthorized"):
        bad.append("토큰 없이 신청 상태를 바꿀 수 있습니다: %s" % d)
    print("  상태 바꾸기, 토큰 없음 → %s" % json.dumps(d, ensure_ascii=False))

    # 날짜 없는 미팅 신청은 거절되어야 합니다
    d = post({"kind": "meeting", "name": "테스트", "org": "테스트기관",
              "email": "qa-%d@example.invalid" % os.getpid(), "consent": True, "elapsed_ms": 9000})
    if d.get("error") != "invalid" or d.get("field") != "preferred_date":
        bad.append("희망 날짜 없이 미팅 신청이 통과했습니다: %s" % d)
    print("  미팅, 날짜 없음        → %s" % json.dumps(d, ensure_ascii=False))

    # 허니팟 — 봇에게는 성공처럼 보이게 응답하되(그래야 다시 안 옴) 저장은 하지 않습니다.
    # 「저장 안 했다」를 토큰 없이 증명하는 방법: 같은 이메일로 네 번 넣어 봅니다.
    # 저장되었다면 하루 3건 제한에 걸려 rate_limited 가 나옵니다. 안 나오면 버린 것입니다.
    hp_mail = "honeypot-%d@example.invalid" % os.getpid()
    hp = []
    for _ in range(4):
        hp.append(post({"kind": "meeting", "name": "봇", "org": "봇", "email": hp_mail,
                        "preferred_date": "2026-12-01", "preferred_slot": "am",
                        "website": "http://spam.example", "consent": True, "elapsed_ms": 9000}))
    limited = [x for x in hp if x.get("error") == "rate_limited"]
    if limited:
        bad.append("허니팟을 채운 신청이 실제로 저장되고 있습니다 (4번째에 %s)" % limited[0])
    elif not all(x.get("ok") for x in hp):
        bad.append("허니팟 응답이 봇에게 들킵니다 — 성공처럼 보여야 합니다: %s" % hp)
    else:
        print("  허니팟 4번 채움        → 매번 ok (저장은 0건 · 하루 제한에 안 걸림)")

    # 너무 빠른 제출
    d = post({"kind": "meeting", "name": "빠름", "org": "빠름", "email": "fast@example.invalid",
              "preferred_date": "2026-12-01", "preferred_slot": "am", "consent": True, "elapsed_ms": 100})
    if d.get("error") != "too_fast":
        bad.append("1초도 안 걸린 신청이 통과했습니다: %s" % d)
    print("  너무 빠름              → %s" % json.dumps(d, ensure_ascii=False))

    # 다른 출처
    d = post({"kind": "meeting", "name": "출처", "org": "출처", "email": "o@example.invalid",
              "preferred_date": "2026-12-01", "preferred_slot": "am", "consent": True,
              "elapsed_ms": 9000}, origin="https://evil.example")
    if d.get("error") != "origin":
        bad.append("허용하지 않은 출처에서 신청이 통과했습니다: %s" % d)
    print("  다른 출처              → %s" % json.dumps(d, ensure_ascii=False))


def ui_checks():
    print("── 화면 쪽 ──")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(URL, wait_until="load")
        pg.wait_for_timeout(1500)

        # 로그인 화면에 단추가 있어야 합니다
        btn = pg.locator("button", has_text="미팅 예약 신청")
        if not btn.count():
            bad.append("로그인 화면에 「미팅 예약 신청」 단추가 없습니다")
            b.close()
            return
        print("  게이트 단추            → 있음 (%d개)" % btn.count())
        btn.first.click()
        pg.wait_for_timeout(500)
        if not pg.locator("#bkModal").count():
            bad.append("「미팅 예약 신청」을 눌러도 신청 창이 열리지 않습니다")
            b.close()
            return
        print("  신청 창                → 열림")

        # 필요한 칸이 다 있는지
        for i in ["bk_name", "bk_org", "bk_email", "bk_date", "bk_slot", "bk_ok", "bk_web"]:
            if not pg.locator("#" + i).count():
                bad.append("신청 창에 %s 칸이 없습니다" % i)

        # 허니팟은 사람 눈에 닿지 않아야 합니다.
        # display:none 은 봇이 알아채므로 화면 밖으로 밀어내는 방식을 씁니다 —
        # 그래서 "보이는가"가 아니라 "화면 밖에 있는가 · 탭으로 닿는가"를 봅니다.
        hp = pg.locator("#bk_web")
        bb = hp.bounding_box() or {"x": 0, "y": 0, "width": 0, "height": 0}
        vw = pg.viewport_size["width"]
        offscreen = (bb["x"] + bb["width"] <= 0) or (bb["x"] >= vw) or (bb["width"] == 0)
        if not offscreen:
            bad.append("허니팟 칸(bk_web)이 화면 안에 있습니다 (x=%s) — 사람이 채우게 됩니다" % bb["x"])
        if hp.get_attribute("tabindex") != "-1":
            bad.append("허니팟 칸이 탭 순서에 들어 있습니다 — 키보드로 쓰는 분이 채우게 됩니다")
        if not bad:
            print("  허니팟                 → 화면 밖(x=%d) · 탭에서 빠짐" % bb["x"])

        # 빈 칸으로 보내면 막혀야 합니다 (서버로 안 나가야 함)
        sent = []
        pg.route("**/functions/v1/demo-request", lambda r: (sent.append(1), r.abort()))
        pg.click("#bkSend")
        pg.wait_for_timeout(400)
        msg = pg.locator("#bk_msg_out").inner_text().strip()
        if sent:
            bad.append("빈 칸인데도 서버로 신청을 보냈습니다")
        if "이름" not in msg:
            bad.append("빈 이름으로 보냈을 때 안내가 나오지 않습니다 (나온 글: %r)" % msg)
        else:
            print("  빈 칸 막기             → %s" % msg)

        # 다 채우고 동의만 빼면 막혀야 합니다
        pg.fill("#bk_name", "테스트")
        pg.fill("#bk_org", "테스트기관")
        pg.fill("#bk_email", "qa@example.invalid")
        pg.fill("#bk_date", "2026-12-01")
        pg.click("#bkSend")
        pg.wait_for_timeout(400)
        msg = pg.locator("#bk_msg_out").inner_text().strip()
        if sent:
            bad.append("개인정보 동의 없이 서버로 신청을 보냈습니다")
        if "동의" not in msg:
            bad.append("동의 없이 보냈을 때 안내가 나오지 않습니다 (나온 글: %r)" % msg)
        else:
            print("  동의 없이 막기         → %s" % msg)

        # 로그인 전에는 신청 함이 뜨지 않아야 합니다
        if pg.locator("#bookBox").count():
            bad.append("로그인 전에 신청 목록 자리(#bookBox)가 화면에 있습니다")

        if errs:
            bad.append("자바스크립트 오류: " + " / ".join(errs[:3]))
        b.close()


FIELDS = ["#bk_name", "#bk_org", "#bk_email", "#bk_phone", "#bk_date", "#bk_slot",
          "#bk_msg", "#bkSend", "#bkCancel", "#bkClose"]


def size_checks():
    """터치 44px·대비를 폭 3종에서 실측합니다.

    이 창은 앱을 처음 보는 바깥 분이, 흔히 태블릿으로 채웁니다 — 그래서 휴대폰 폭에서만
    44px 을 지키는 것으로는 모자랍니다. 눈대중 금지(저장소 규칙)라 수치를 찍습니다.
    """
    print("── 터치 크기·대비 (폭 3종) ──")
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w, label in [(390, "휴대폰 390"), (768, "태블릿 768"), (1280, "데스크톱 1280")]:
            pg = b.new_page(viewport={"width": w, "height": 860})
            pg.goto(URL, wait_until="load")
            pg.wait_for_timeout(1200)
            pg.locator("button", has_text="미팅 예약 신청").first.click()
            pg.wait_for_timeout(400)
            small = []
            for sel in FIELDS:
                bb = pg.locator(sel).bounding_box()
                if not bb:
                    bad.append("%s: %s 칸이 없습니다" % (label, sel))
                    continue
                if bb["height"] < 44 or bb["width"] < 44:
                    small.append("%s %d×%d" % (sel, bb["width"], bb["height"]))
            lb = pg.locator("label:has(#bk_ok)").bounding_box()
            if lb and lb["height"] < 44:
                small.append("동의 라벨 %d×%d" % (lb["width"], lb["height"]))
            if small:
                bad.append("%s: 44px 못 미치는 칸 — %s" % (label, ", ".join(small)))
            ov = pg.evaluate("()=>{const x=document.getElementById('bkModal').firstElementChild;"
                             "return [x.scrollWidth,x.clientWidth,document.documentElement.scrollWidth,window.innerWidth];}")
            if ov[0] > ov[1] + 2 or ov[2] > ov[3] + 2:
                bad.append("%s: 신청 창이 화면을 넘칩니다 %s" % (label, ov))
            # 라벨 글자 대비 (작고 굵은 글자 — 4.5:1 기준)
            st = pg.evaluate("()=>{const e=document.querySelector('label[for=bk_name]');"
                             "return [getComputedStyle(e).color,"
                             "getComputedStyle(document.querySelector('#bkModal > div')).backgroundColor];}")
            r = ratio(rgb(st[0]), rgb(st[1]))
            if r < 4.5:
                bad.append("%s: 칸 이름 글자 대비 %.2f:1 — 4.5:1 에 못 미칩니다" % (label, r))
            marks = []
            for sel in ["#bkSend", "#bkCancel", "#bk_name"]:
                c = pg.evaluate("s=>{const e=document.querySelector(s);const g=getComputedStyle(e);"
                                "return [g.color,g.backgroundColor];}", sel)
                bgc = "rgb(255,255,255)" if "rgba(0, 0, 0, 0)" in c[1] else c[1]
                rr = ratio(rgb(c[0]), rgb(bgc))
                marks.append("%s %.2f:1" % (sel.lstrip("#"), rr))
                if rr < 4.5:
                    bad.append("%s: %s 글자 대비 %.2f:1 — 4.5:1 에 못 미칩니다" % (label, sel, rr))
            print("  %-14s 44px OK · 라벨 %.2f:1 · %s" % (label, r, " · ".join(marks)))
            pg.close()
        b.close()


def main():
    print("미팅 예약 점검 — %s" % URL)
    ui_checks()
    if not bad:
        size_checks()
    server_checks()
    print()
    if bad:
        print("고칠 것 %d개" % len(bad))
        for x in bad:
            print("  · " + x)
        sys.exit(1)
    print("미팅 예약: 막아야 할 길은 다 막혀 있고 신청 창은 열립니다")


if __name__ == "__main__":
    main()
