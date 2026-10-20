# -*- coding: utf-8 -*-
"""세션 점검 — 창이 여러 개일 때 로그인·회의 선택이 섞이지 않는지.

2026-10-19 대표님 보고: 크롬 창을 둘 띄워 다른 계정으로 로그인했는데 한 계정처럼
보였습니다. 원인은 둘이었습니다.

  ① 로그인은 브라우저(프로필)마다 하나입니다 — 나중 로그인이 앞의 것을 덮어씁니다.
     그런데 앞 창의 화면은 그대로여서 「표시는 A · 서버에는 B」로 갈라져 있었습니다.
  ② 「지금 보고 있는 회의」가 공용 칸(medit:hub1)에 있어, 한 사람이 회의를 옮기면
     남의 화면도 따라 옮겨졌습니다.

둘 다 고쳤고, 여기서 다시 새지 않는지 봅니다.
"""
import os, sys, functools
print = functools.partial(print, flush=True)
from playwright.sync_api import sync_playwright

SITE = os.environ.get("SITE", "http://localhost:8099")
fails = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 420, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:150]))
    pg.goto(SITE + "/index.html?ci=1", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(4000)

    # ① 계정이 바뀐 상황을 흉내 냅니다
    pg.evaluate("""()=>{ state.user={role:'operator',name:'가',email:'a@example.invalid',id:'a'};
                         switchedAccount('b@example.invalid'); }""")
    pg.wait_for_timeout(700)
    m = pg.evaluate("""()=>{ const m=document.getElementById('fmModal');
      return m ? (m.innerText||'').replace(/\\s+/g,' ') : null; }""")
    print("안내 창:", (m or "(없음)")[:170])
    if not m:
        fails.append("계정이 바뀌어도 아무 안내가 없습니다")
    else:
        for need in ["a@example.invalid", "b@example.invalid", "시크릿", "프로필"]:
            if need not in m:
                fails.append("안내에 '" + need + "' 가 없습니다")

    # 두 번 불러도 창이 겹치지 않아야 합니다
    pg.evaluate("()=>switchedAccount('c@example.invalid')")
    pg.wait_for_timeout(400)
    n = pg.evaluate("()=>document.querySelectorAll('#fmModal').length")
    if n > 1:
        fails.append(f"안내 창이 {n}개 겹쳐 떴습니다")

    # ② 회의 선택이 이 브라우저에만 적히는지
    pg.evaluate("""()=>{ const m=document.getElementById('fmModal'); if(m) m.remove();
      state.meetings=[{id:'m1',title:'회의1',attendees:[]},{id:'m2',title:'회의2',attendees:[]}];
      state.currentMeetingId='m2'; syncCurrentMeeting(); }""")
    saved = pg.evaluate("()=>{ try{ return localStorage.getItem(CUR_MTG_KEY); }catch(e){ return 'ERR'; } }")
    print("이 브라우저가 기억한 회의:", saved)
    if saved != "m2":
        fails.append(f"회의 선택이 이 브라우저에 안 적혔습니다 (값 {saved})")

    # 머리글 로고를 누르면 첫 화면(회의 목록)으로 — 길을 잃었을 때의 출구
    logo = pg.evaluate("""()=>{
      state.meetings=[{id:'mL',title:'로고 시험',date:'2026-10-20',time:'10:00',attendees:[{name:'나'}]}];
      state.currentMeetingId='mL'; syncCurrentMeeting();
      if(typeof enterHub==='function') enterHub();
      const el=document.getElementById('ctHome');
      if(!el) return {found:false};
      const before=getComputedStyle(document.getElementById('appMain')).display;
      el.click();
      return {found:true, before, after:getComputedStyle(document.getElementById('appMain')).display,
              clickable:getComputedStyle(el).cursor};
    }""")
    print("로고:", logo)
    if not logo.get("found"): fails.append("머리글 로고(ctHome)가 없습니다")
    else:
        if logo.get("before")=="none": fails.append("시험 전부터 앱 화면이 아니었습니다")
        elif logo.get("after")!="none": fails.append("로고를 눌러도 첫 화면으로 안 갑니다")
        if logo.get("clickable")!="pointer": fails.append("로고가 눌리는 것처럼 보이지 않습니다")

    if errs:
        fails.append("스크립트 오류: " + errs[0])
    b.close()

import datetime
kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
lines = [f"### 세션 점검 {kst:%Y-%m-%d %H:%M} KST", ""]
lines += (["**살펴볼 것**", ""] + [f"- {x}" for x in fails] + [""]) if fails else ["이상 없음", ""]
lines += ["<details><summary>본 것</summary>", "",
          "- 다른 창에서 계정이 바뀌면 알려 주는가 (표시와 서버가 갈라지지 않게)",
          "- 안내 창이 겹쳐 뜨지 않는가",
          "- 「보고 있는 회의」가 이 브라우저에만 적히는가 (남의 화면을 끌고 가지 않게)",
          "- 머리글 로고를 누르면 첫 화면(회의 목록)으로 가는가",
          "", "</details>"]
open("session-report.md", "w", encoding="utf-8").write("\n".join(lines))
print()
print("\n".join(lines))
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write("rc=%d\n" % (1 if fails else 0))
sys.exit(1 if fails else 0)
