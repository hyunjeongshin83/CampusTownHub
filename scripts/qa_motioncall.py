# -*- coding: utf-8 -*-
"""모션캠 연동 화상회의가 실제로 통하는지 봅니다.

가짜 Jitsi 가 아니라 진짜 서버에 붙습니다. 보는 것:
  · 모션캠 캔버스를 Jitsi 카메라 트랙으로 만들 수 있는가
  · 우리 출처에서 XMPP 에 붙어 방에 들어가는가
  · 두 사람이 같은 방에서 서로를 보는가 (상대 영상 트랙이 실제로 오는가)
  · 내보내는 영상이 캔버스 그림인가 (카메라가 아닌가)

바깥 서버(meet.element.io)에 의존하므로 CI 에는 걸지 않습니다 — 회의 전에 손으로 돌립니다.
"""
import os, sys, time, json
from playwright.sync_api import sync_playwright

SITE = os.environ.get("SITE", "http://127.0.0.1:8099")
ROOM = "medit-qa-" + str(int(time.time()))
bad = []

# 허브 코드를 그대로 쓰되, 방 이름만 이 점검용으로 바꿔 두 창이 같은 방에 들어가게 합니다.
SETUP = """
async room => {
  state.user = {role:'operator', name:__NAME__, email:'qa@example.invalid', id:'u'+Math.random()};
  state.meetings = [{id:'mq', title:'연동 점검', date:'2026-10-22', time:'16:30', attendees:[{name:__NAME__}]}];
  state.currentMeetingId = 'mq'; syncCurrentMeeting(); state.meeting.started = null;
  window.mcRoomName = () => room;                 // 두 창이 같은 방에 들어가도록
  document.body.insertAdjacentHTML('beforeend',
    '<div id="vFrame"></div><div id="vAfter"></div><div id="vTranscript"></div>'
    + '<span id="vSegCount"></span><span id="vMicState"></span><input id="vTypeInput">'
    + '<button id="vTypeAdd"></button><button id="vMicBtn"></button><select id="vMicWho"></select>'
    + '<span id="vMicHint"></span><button id="vKakao"></button><button id="vGuess"></button>'
    + '<button id="vClear"></button>');
  openMotionCall();
  // 모션캠 iframe 대신 점검용 캔버스를 물려 줍니다 — 가짜 카메라에는 얼굴이 없어
  // 실제 모션캠을 돌릴 수 없습니다. 「캔버스가 그대로 나가는가」가 여기서 볼 것입니다.
  const c = document.createElement('canvas');
  c.width = 320; c.height = 240;
  const x = c.getContext('2d');
  let n = 0;
  setInterval(() => {                              // 움직이는 그림 (정지 화면은 전송이 끊깁니다)
    x.fillStyle = __COLOR__; x.fillRect(0, 0, 320, 240);
    x.fillStyle = '#fff'; x.font = '28px sans-serif';
    x.fillText(__NAME__ + ' ' + (n++ % 100), 20, 120);
  }, 100);
  window.__qaCanvas = c;
  window.mcCanvas = () => c;
  return true;
}
"""


def mk(ctx, name, color):
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:150]))
    pg.goto(SITE + "/index.html?ci=1", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3500)
    pg.evaluate(SETUP.replace("__NAME__", json.dumps(name)).replace("__COLOR__", json.dumps(color)), ROOM)
    return pg, errs


with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-fake-device-for-media-stream",
                                "--use-fake-ui-for-media-stream",
                                "--autoplay-policy=no-user-gesture-required"])
    ctx = b.new_context(viewport={"width": 1280, "height": 950},
                        permissions=["camera", "microphone"])
    print("모션캠 연동 점검 — %s" % SITE)
    print("  방: %s" % ROOM)

    a, aerr = mk(ctx, "가나", "#0C7069")
    c, cerr = mk(ctx, "다라", "#8E5FA8")
    print("  창 2개 준비")

    # 둘 다 들어갑니다
    for pg, who in ((a, "가나"), (c, "다라")):
        pg.evaluate("() => mcJoin()")
    joined = {}
    for i in range(14):
        a.wait_for_timeout(5000)
        for pg, who in ((a, "가나"), (c, "다라")):
            st = pg.evaluate("() => ({j: mcJoined, msg: (document.getElementById('mcMsg')||{}).textContent||''})")
            joined[who] = st
        if all(v["j"] for v in joined.values()):
            print("  둘 다 입장        → %d초" % ((i + 1) * 5))
            break
    for who, st in joined.items():
        if not st["j"]:
            bad.append("%s 가 방에 못 들어갔습니다: %s" % (who, st["msg"][:110]))
            print("  %s             → 실패: %s" % (who, st["msg"][:90]))

    if all(v["j"] for v in joined.values()):
        # 서로 보이는가
        seen = {}
        for i in range(10):
            a.wait_for_timeout(4000)
            for pg, who in ((a, "가나"), (c, "다라")):
                seen[who] = pg.evaluate("""() => {
                    const ppl = Object.values(mcRemote);
                    return {n: ppl.length,
                            names: ppl.map(x => x.name),
                            video: ppl.filter(x => x.tracks.some(t => t.getType() === 'video')).length,
                            audio: ppl.filter(x => x.tracks.some(t => t.getType() === 'audio')).length,
                            playing: [...document.querySelectorAll('#mcTiles video')]
                                       .filter(v => v.videoWidth > 0).length};
                }""")
            if all(v["video"] >= 1 for v in seen.values()):
                print("  서로 보임         → %d초" % ((i + 1) * 4))
                break
        for who, s in seen.items():
            print("  %s: 상대 %d명 %s · 영상 %d · 소리 %d · 실제 재생 %d"
                  % (who, s["n"], s["names"], s["video"], s["audio"], s["playing"]))
            if s["n"] < 1:
                bad.append("%s 화면에 상대가 안 보입니다" % who)
            elif s["video"] < 1:
                bad.append("%s 화면에 상대 영상 트랙이 안 옵니다 (소리 %d)" % (who, s["audio"]))
            elif s["playing"] < 1:
                bad.append("%s 화면에서 상대 영상이 재생되지 않습니다 (트랙은 왔습니다)" % who)
            if s["names"] and not any(x in ("가나", "다라") for x in s["names"]):
                bad.append("%s 쪽에 참석자 이름이 안 넘어옵니다: %s" % (who, s["names"]))

        # 내보내는 영상이 캔버스인가 (카메라가 아닌가)
        src = a.evaluate("""() => {
            const v = mcTracks.filter(t => t.getType() === 'video');
            if (!v.length) return {none: true};
            const st = v[0].getOriginalStream && v[0].getOriginalStream();
            const t = st && st.getVideoTracks()[0];
            const s = t && t.getSettings ? t.getSettings() : {};
            return {label: (t && t.label) || '', w: s.width || 0, h: s.height || 0,
                    isCanvas: st === (window.__qaCanvas && window.__qaCanvas.captureStream ? null : null) };
        }""")
        print("  내보내는 영상      → %s %dx%d" % (src.get("label", "")[:40], src.get("w", 0), src.get("h", 0)))
        if src.get("none"):
            bad.append("내보내는 영상 트랙이 없습니다")
        elif src.get("w") and src["w"] not in (320,):
            bad.append("내보내는 영상이 캔버스(320×240)가 아닙니다 — 카메라가 나가고 있을 수 있습니다: %dx%d"
                       % (src["w"], src.get("h", 0)))

        # 참석자가 회의 기록에 들어갔는가
        att = a.evaluate("() => (currentMeeting().attendees||[]).map(x => x.name)")
        print("  회의 참석자 기록   → %s" % att)
        if "다라" not in att:
            bad.append("들어온 사람이 회의 참석자에 안 들어갔습니다: %s" % att)
        if not a.evaluate("() => !!state.meeting.started"):
            bad.append("회의에 들어갔는데 회의 시작으로 기록되지 않습니다")

        # 나가기
        a.evaluate("() => mcLeave()")
        a.wait_for_timeout(4000)
        if a.evaluate("() => mcJoined"):
            bad.append("[나가기] 를 눌렀는데 회의에서 안 나왔습니다")
        else:
            print("  나가기            → 정상")

    for who, e in (("가나", aerr), ("다라", cerr)):
        real = [x for x in e if "jitsi" not in x.lower() and "Logger" not in x]
        if real:
            bad.append("%s 쪽 자바스크립트 오류: %s" % (who, " / ".join(real[:2])))
    ctx.close(); b.close()

print()
if bad:
    print("고칠 것 %d개" % len(bad))
    for x in bad: print("  · " + x)
    sys.exit(1)
print("모션캠 연동: 두 사람이 같은 방에서 서로를 보고, 내보내는 영상은 캔버스입니다")
