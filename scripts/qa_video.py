# -*- coding: utf-8 -*-
"""화상회의 → 회의록 점검.

2026-10-19 대표님: 「화상 회의 저장 후 회의록 만들기 기능도 넣어주세요」

예전에는 iframe 만 띄워서, 회의가 끝나도 앱은 아무것도 몰랐습니다. 다른 탭으로 가서
[회의 종료]를 눌러야만 기록이 남았고, 그걸 모르면 회의가 그냥 사라졌습니다.

여기서 보는 것 (진짜 Jitsi 서버는 부르지 않습니다 — 가짜 API 를 끼워 넣습니다):
  · 들어가면 회의가 열린 것으로 기록되는가
  · 들어온 사람이 참석자에 더해지는가
  · 나가면 [회의록 만들기] 가 뜨는가
  · Jitsi API 가 막혀 있어도 화상회의 자체는 뜨는가 (iframe 되돌림)
"""
import os, sys, functools
print = functools.partial(print, flush=True)
from playwright.sync_api import sync_playwright

SITE=(os.environ.get("SITE") or "http://localhost:8099").rstrip("/")
fails=[]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1000,"height":900})
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)[:150]))
    # 진짜 Jitsi 는 부르지 않습니다
    pg.route("**meet.jit.si/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=""))
    pg.goto(SITE+"/index.html?ci=1", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(4000)

    res = pg.evaluate("""async ()=>{
      const log={};
      state.user={role:'operator',name:'나',email:'me@example.invalid',id:'u'};
      state.meetings=[{id:'m1',title:'화상 테스트',date:'2026-10-19',time:'16:00',attendees:[{name:'나'}]}];
      state.currentMeetingId='m1'; syncCurrentMeeting();
      state.meeting.started=null; state.segments=[];

      // 가짜 Jitsi API — 진짜 서버에 안 붙고 이벤트만 흉내 냅니다
      const H={};
      window.JitsiMeetExternalAPI=function(){ 
        this.addListener=(k,f)=>{H[k]=f;};
        this.dispose=()=>{};
      };
      document.body.insertAdjacentHTML('beforeend',
        '<div id="vFrame"></div><div id="vAfter"></div>');

      await startJitsi();
      log.listeners=Object.keys(H).sort().join(",");

      H.videoConferenceJoined && H.videoConferenceJoined({});
      log.started = !!state.meeting.started;
      log.afterJoin = (document.getElementById('vAfter').innerText||'').slice(0,60);

      H.participantJoined && H.participantJoined({displayName:'방 교수님'});
      H.participantJoined && H.participantJoined({displayName:'방 교수님'});   // 두 번 들어와도 한 번만
      log.attendees = (currentMeeting().attendees||[]).map(a=>a.name).join("/");

      H.videoConferenceLeft && H.videoConferenceLeft({});
      const box=document.getElementById('vAfter');
      log.afterLeft = (box.innerText||'').replace(/\\s+/g,' ').slice(0,90);
      log.hasBtn = !!document.getElementById('vMakeMinutes');
      return log;
    }""")
    for k,v in res.items(): print(f"{k}: {v}")

    if "videoConferenceJoined" not in (res.get("listeners") or ""): fails.append("참가 이벤트를 안 듣고 있습니다")
    if "videoConferenceLeft" not in (res.get("listeners") or ""): fails.append("퇴장 이벤트를 안 듣고 있습니다")
    if not res.get("started"): fails.append("화상회의에 들어가도 회의가 시작된 것으로 기록되지 않습니다")
    if "방 교수님" not in (res.get("attendees") or ""): fails.append("들어온 사람이 참석자에 안 더해집니다")
    if (res.get("attendees") or "").count("방 교수님") != 1: fails.append("같은 사람이 두 번 더해집니다")
    if not res.get("hasBtn"): fails.append("[회의록 만들기] 단추가 없습니다")
    if "회의록" not in (res.get("afterLeft") or ""): fails.append("끝난 뒤 안내가 안 나옵니다")

    # Jitsi API 가 막혀도 화상회의는 떠야 합니다
    fb = pg.evaluate("""async ()=>{
      delete window.JitsiMeetExternalAPI;
      document.getElementById('vFrame').innerHTML='';
      await startJitsi();
      return document.getElementById('vFrame').innerHTML.indexOf('iframe')>=0;
    }""")
    print("API 막혔을 때 iframe 되돌림:", fb)
    if not fb: fails.append("Jitsi API 가 막히면 화상회의가 아예 안 뜹니다")

    if errs: fails.append("스크립트 오류: "+errs[0])
    b.close()

import datetime
kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
lines=[f"### 화상회의 → 회의록 점검 {kst:%Y-%m-%d %H:%M} KST",""]
lines += (["**살펴볼 것**",""]+[f"- {x}" for x in fails]+[""]) if fails else ["이상 없음",""]
lines += ["<details><summary>본 것</summary>","",
          "- 들어가면 회의가 열린 것으로 기록되는가",
          "- 들어온 사람이 참석자에 더해지는가 (중복 없이)",
          "- 나가면 [회의록 만들기] 가 뜨는가",
          "- Jitsi API 가 막혀도 화상회의는 뜨는가",
          "","</details>"]
open("video-report.md","w",encoding="utf-8").write("\n".join(lines))
print(); print("\n".join(lines))
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"],"a") as f:
        f.write("rc=%d\n" % (1 if fails else 0))
sys.exit(1 if fails else 0)
