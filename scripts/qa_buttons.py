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
    if "전체 보고서" not in names: fails.append("[전체 보고서] 가 없습니다 — 열 길이 없습니다")
    if "원문 보기" not in names: fails.append("[원문 보기] 가 없습니다 — 녹취 원문을 못 봅니다")
    if names.get("규제 리포트 ✓") is not True: fails.append("규제 리포트가 있는데 단추가 안 꺼졌습니다")
    # 요약이 기본으로 펼쳐져 있는가 — 보고서가 그 회차의 얼굴이어야 합니다
    dg = pg.evaluate("""()=>{
      const rec={id:'B',title:'회의 B',dt:'2026.10.19',attendees:[],
        rawNote:'녹취 원문입니다',
        report:'# 제목\\n\\n## 한눈에\\n\\n| | |\\n|---|---|\\n| 결정된 방향 | 한 줄 |\\n\\n## 개요\\n개요 문장입니다.',
        reportAt:'10/19'};
      state.records=[rec];
      const box=document.createElement('div'); box.id='dgrow';
      box.innerHTML=sessionRow(rec,'pvx_'); document.body.appendChild(box);
      return {table:box.querySelectorAll('table').length,
              text:(box.innerText||'').replace(/\\s+/g,' ').slice(0,80),
              openByDefault:(box.innerText||'').indexOf('개요 문장입니다')>=0};
    }""")
    print("요약 기본 노출:", dg)
    if not dg.get("openByDefault"): fails.append("보고서 요약이 기본으로 안 펼쳐집니다")
    if dg.get("table",0) < 1: fails.append("요약에 「한눈에」 표가 없습니다")

    # 원문 보기는 보고서를 빼고 녹취만
    rawv = pg.evaluate("""()=>{
      const r=state.records[0];
      const withRep=recordToMD(r), noRep=recordToMD(r,{noReport:true});
      return {hasInFull: withRep.indexOf('개요 문장입니다')>=0,
              hasInRaw: noRep.indexOf('개요 문장입니다')>=0,
              rawHasNote: noRep.indexOf('녹취 원문입니다')>=0};
    }""")
    print("원문 분리:", rawv)
    if not rawv.get("hasInFull"): fails.append("전체 회의록에 보고서가 안 들어갑니다")
    if rawv.get("hasInRaw"): fails.append("원문 보기에 보고서가 또 나옵니다")
    if not rawv.get("rawHasNote"): fails.append("원문 보기에 녹취가 없습니다")

    if errs: fails.append("스크립트 오류: "+errs[0])
    b.close()
import datetime
kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
lines=[f"### 단추 상태 점검 {kst:%Y-%m-%d %H:%M} KST",""]
lines += (["**살펴볼 것**",""]+[f"- {x}" for x in fails]+[""]) if fails else ["이상 없음",""]
lines += ["<details><summary>본 것</summary>","",
          "- 보고서 없는 회차: [AI 보고서] 켜짐",
          "- 보고서 있는 회차: [AI 보고서 ✓] 꺼짐 · [전체 보고서]·[원문 보기] 켜짐",
          "- 규제 리포트도 같은 방식",
          "- 보고서 요약이 기본으로 펼쳐져 있는가 (보고서가 그 회차의 얼굴)",
          "- [원문 보기]는 보고서를 빼고 녹취만 보여주는가",
          "","</details>"]
open("buttons-report.md","w",encoding="utf-8").write("\n".join(lines))
print(); print("\n".join(lines))
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"],"a") as f:
        f.write("rc=%d\n" % (1 if fails else 0))
sys.exit(1 if fails else 0)
