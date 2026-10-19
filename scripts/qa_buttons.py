# -*- coding: utf-8 -*-
"""단추 상태 점검 — 이미 만든 것을 다시 만들지 않게.

2026-10-19 대표님: 「이미 AI 보고서가 작성되어 있는 경우는 AI 보고서를 비활성화해 주세요」
한 번 만든 보고서를 모르고 다시 만들면 AI 호출이 또 나가고 내용도 바뀝니다.
작성된 회차에서는 만드는 단추를 끄고, 보는 단추만 남깁니다.
"""
import os, sys, functools
print = functools.partial(print, flush=True)
from playwright.sync_api import sync_playwright

SITE=(os.environ.get("SITE") or "http://localhost:8099").rstrip("/")
fails=[]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1100,"height":900})
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)[:150]))
    pg.goto(SITE+"/index.html?ci=1", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(4000)
    res = pg.evaluate("""()=>{
      state.user={role:'operator',name:'QA',email:'qa@example.invalid',id:'q'};
      const mk=(id,rep,reg)=>({id,title:'회의 '+id,dt:'2026.10.19',attendees:[],
        report:rep?'# 제목\\n\\n## 개요\\n한 줄입니다.':'', reportAt:rep?'10/19':'',
        regReport:reg?'<h3>규제</h3>':''});
      const html = sessionRow(mk('A',false,false),'pv_') + sessionRow(mk('B',true,true),'pv_');
      const box=document.createElement('div'); box.id='btnTest'; box.innerHTML=html;
      document.body.appendChild(box);
      const btns=[...box.querySelectorAll('button')].map(x=>({t:(x.innerText||'').trim(),d:x.disabled}));
      return btns;
    }""")
    for r in res: print(("꺼짐 " if r["d"] else "켜짐 ")+r["t"])
    names={r["t"]:r["d"] for r in res}
    if names.get("AI 보고서") is not False: fails.append("보고서 없는 회차의 [AI 보고서] 가 꺼져 있습니다")
    if names.get("AI 보고서 ✓") is not True: fails.append("보고서 있는 회차의 [AI 보고서 ✓] 가 안 꺼졌습니다")
    if "보고서 보기" not in names: fails.append("[보고서 보기] 가 없습니다 — 열 길이 없습니다")
    if "요약 보기" not in names: fails.append("[요약 보기] 가 없습니다 — 목록에서 축약본을 못 봅니다")
    if names.get("규제 리포트 ✓") is not True: fails.append("규제 리포트가 있는데 단추가 안 꺼졌습니다")
    # 축약 상자가 실제로 펴지고 「한눈에」 표가 그려지는지
    dg = pg.evaluate("""()=>{
      state.records=[{id:'B',title:'회의 B',dt:'2026.10.19',attendees:[],
        report:'# 제목\\n\\n## 한눈에\\n\\n| | |\\n|---|---|\\n| 결정된 방향 | 한 줄 |\\n\\n## 개요\\n개요 문장입니다.',
        reportAt:'10/19'}];
      try{ reportDigestBox('B','dgpv_B'); }catch(e){ return 'ERR:'+e.message; }
      const d=document.getElementById('dgpv_B');
      return d ? {len:(d.innerText||'').length, table:d.querySelectorAll('table').length} : null;
    }""")
    print("축약 상자:", dg)
    if not isinstance(dg, dict): fails.append("축약 상자가 안 열립니다: "+str(dg))
    else:
        if dg["table"] < 1: fails.append("축약 상자에 「한눈에」 표가 없습니다")
        if dg["len"] < 20: fails.append("축약 상자가 비어 있습니다")

    if errs: fails.append("스크립트 오류: "+errs[0])
    b.close()
import datetime
kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
lines=[f"### 단추 상태 점검 {kst:%Y-%m-%d %H:%M} KST",""]
lines += (["**살펴볼 것**",""]+[f"- {x}" for x in fails]+[""]) if fails else ["이상 없음",""]
lines += ["<details><summary>본 것</summary>","",
          "- 보고서 없는 회차: [AI 보고서] 켜짐",
          "- 보고서 있는 회차: [AI 보고서 ✓] 꺼짐 · [보고서 보기] 켜짐",
          "- 규제 리포트도 같은 방식",
          "- [요약 보기]로 「한눈에」 표가 그 자리에서 펴지는가",
          "","</details>"]
open("buttons-report.md","w",encoding="utf-8").write("\n".join(lines))
print(); print("\n".join(lines))
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"],"a") as f:
        f.write("rc=%d\n" % (1 if fails else 0))
sys.exit(1 if fails else 0)
