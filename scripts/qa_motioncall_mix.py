# -*- coding: utf-8 -*-
"""섞여도 되는지 — 한쪽은 모션캠 연동(lib), 한쪽은 평소 링크(웹페이지).

대표님이 모션캠으로 들어가고 교수님은 평소처럼 링크로 들어오셔야 합니다.
방 이름 대소문자 때문에 서로 다른 방에 들어가면 아무도 못 만납니다 — 그걸 봅니다.
허브는 iframe 에 'CampusTownHub-mX' 를, lib 에는 소문자를 넘깁니다.
"""
import os, sys, time, json
from playwright.sync_api import sync_playwright

SITE = os.environ.get("SITE", "http://127.0.0.1:8099")
MIXED = "CampusTownHub-Mix" + str(int(time.time()))      # 대문자가 섞인 이름 — 일부러
bad = []

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-fake-device-for-media-stream",
                                "--use-fake-ui-for-media-stream",
                                "--autoplay-policy=no-user-gesture-required"])
    ctx = b.new_context(viewport={"width": 1280, "height": 950},
                        permissions=["camera", "microphone"])
    print("섞임 점검 — 방 %s" % MIXED)

    # ── ① 모션캠 연동 쪽 (허브) ──
    hub = ctx.new_page()
    herr = []
    hub.on("pageerror", lambda e: herr.append(str(e)[:140]))
    hub.goto(SITE + "/index.html?ci=1", wait_until="domcontentloaded", timeout=60000)
    hub.wait_for_timeout(3500)
    hub.evaluate("""room => {
        state.user={role:'operator',name:'대표(모션캠)',email:'qa@example.invalid',id:'u1'};
        state.meetings=[{id:'mmix',title:'섞임 점검',date:'2026-10-22',time:'16:30',attendees:[{name:'대표(모션캠)'}]}];
        state.currentMeetingId='mmix'; syncCurrentMeeting(); state.meeting.started=null;
        // 허브가 쓰는 규칙 그대로: iframe 은 원래 이름, lib 은 소문자
        window.jitsiRoom = () => room;
        document.body.insertAdjacentHTML('beforeend',
          '<div id="vFrame"></div><div id="vAfter"></div><div id="vTranscript"></div>'
          +'<span id="vSegCount"></span><span id="vMicState"></span><input id="vTypeInput">'
          +'<button id="vTypeAdd"></button><button id="vMicBtn"></button><select id="vMicWho"></select>'
          +'<span id="vMicHint"></span><button id="vKakao"></button><button id="vGuess"></button><button id="vClear"></button>');
        openMotionCall();
        const c=document.createElement('canvas'); c.width=320; c.height=240;
        const x=c.getContext('2d'); let n=0;
        setInterval(()=>{ x.fillStyle='#0C7069'; x.fillRect(0,0,320,240);
          x.fillStyle='#fff'; x.font='26px sans-serif'; x.fillText('모션캠 '+(n++%100),16,120); },100);
        window.mcCanvas = () => c;
    }""", MIXED)
    print("  허브가 lib 로 쓸 방 이름: %s" % hub.evaluate("() => mcRoomName()"))
    hub.evaluate("() => mcJoin()")
    ok = False
    for i in range(12):
        hub.wait_for_timeout(5000)
        if hub.evaluate("() => mcJoined"): ok = True; print("  ① 모션캠 입장     → %d초" % ((i+1)*5)); break
    if not ok:
        bad.append("모션캠 쪽이 방에 못 들어갔습니다: %s"
                   % hub.evaluate("() => (document.getElementById('mcMsg')||{}).textContent||''")[:110])

    # ── ② 평소 링크 쪽 (교수님) — 원래 대소문자 그대로 열고 [Join meeting] 을 누릅니다 ──
    guest = ctx.new_page()
    guest.goto("https://jitsi.riot.im/" + MIXED, wait_until="domcontentloaded", timeout=60000)
    guest.wait_for_timeout(10000)
    for sel in ["input[placeholder*='name' i]", "input[aria-label*='name' i]"]:
        el = guest.locator(sel)
        if el.count():
            try: el.first.fill("방 교수님"); break
            except Exception: pass
    jb = guest.get_by_role("button", name="Join meeting")
    print("  ② 손님 Join 단추   → %d개" % jb.count())
    if jb.count():
        try: jb.first.click(); print("  ② 손님 Join 눌렀습니다")
        except Exception as e: bad.append("손님 쪽 Join 클릭 실패: %s" % str(e)[:70])
    gin = False
    for i in range(10):
        guest.wait_for_timeout(4500)
        if guest.evaluate("""() => !!(window.APP&&APP.conference&&APP.conference._room
                               &&APP.conference._room.isJoined&&APP.conference._room.isJoined())"""):
            gin = True; print("  ② 손님 입장       → %d초" % (10+(i+1)*4.5)); break
    if not gin:
        t = guest.evaluate("() => (document.body.innerText||'').replace(/\\n+/g,' | ').slice(0,140)")
        bad.append("손님이 평소 링크로 못 들어갔습니다: %s" % t[:120])

    # ── ③ 서로 보이는가 ──
    if ok and gin:
        found = False
        for i in range(10):
            hub.wait_for_timeout(4000)
            s = hub.evaluate("""() => { const ppl=Object.values(mcRemote);
                return {n:ppl.length, names:ppl.map(x=>x.name),
                        video:ppl.filter(x=>x.tracks.some(t=>t.getType()==='video')).length}; }""")
            g = guest.evaluate("""() => { try{ return APP.conference.listMembers().length; }catch(e){ return -1; } }""")
            if s["n"] >= 1:
                found = True
                print("  ③ 모션캠 쪽이 본 상대: %d명 %s (영상 %d)" % (s["n"], s["names"], s["video"]))
                print("  ③ 손님 쪽이 본 참석자: %d명" % g)
                if s["video"] < 1:
                    bad.append("손님 영상이 모션캠 쪽에 안 옵니다 (소리만)")
                if g < 1:
                    bad.append("손님 쪽에서 모션캠 참석자가 안 보입니다 (%d)" % g)
                break
        if not found:
            bad.append("같은 방에 모이지 않았습니다 — 방 이름 대소문자가 갈린 것일 수 있습니다 "
                       "(lib=%s, 링크=%s)" % (hub.evaluate("() => mcRoomName()"), MIXED))
    try:
        hub.evaluate("() => mcLeave()")
    except Exception:
        pass
    real = [x for x in herr if "jitsi" not in x.lower()]
    if real: bad.append("허브 쪽 오류: " + " / ".join(real[:2]))
    ctx.close(); b.close()

print()
if bad:
    print("고칠 것 %d개" % len(bad))
    for x in bad: print("  · " + x)
    sys.exit(1)
print("섞임: 모션캠으로 들어간 사람과 평소 링크로 들어온 사람이 같은 방에서 만납니다")
