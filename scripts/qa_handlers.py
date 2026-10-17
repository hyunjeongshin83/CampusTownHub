# -*- coding: utf-8 -*-
"""실행 중인 앱에서 정적으로는 안 보이는 버그를 찾는다.
1) HTML onclick 등이 부르는 전역 함수가 실제로 정의돼 있는지
2) 중복 id
3) 화면 전환을 한 바퀴 돌며 스크립트 오류가 나는지"""
import os,re,json
from playwright.sync_api import sync_playwright
S=os.environ.get("TARGET") or (os.environ.get("SITE","https://hyunjeongshin83.github.io/CampusTownHub").rstrip("/")+"/index.html?ci=1")
bad=[]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1280,"height":900})
    errs=[]; pg.on("pageerror",lambda e:errs.append(str(e)))
    pg.goto(S,wait_until="networkidle",timeout=60000); pg.wait_for_timeout(4000)

    # 1) 인라인 핸들러가 부르는 전역 이름 수집 → 정의 여부 확인
    missing=pg.evaluate("""()=>{
      const names=new Set();
      const re=/(^|[^.\\w$])([A-Za-z_$][\\w$]*)\\s*\\(/g;
      document.querySelectorAll('*').forEach(el=>{
        for(const a of el.attributes||[]) if(a.name.startsWith('on')){
          let m; re.lastIndex=0; while((m=re.exec(a.value))) names.add(m[2]);
        }});
      const skip=new Set(['if','for','while','return','typeof','function','catch','this','String','Number','Boolean','JSON','Array','Object','encodeURIComponent','decodeURIComponent','parseInt','parseFloat','alert','confirm','prompt','setTimeout','event','switch']);
      return [...names].filter(n=>!skip.has(n)&&typeof window[n]!=='function');
    }""")
    if missing: bad.append("정의되지 않은 핸들러 함수: "+", ".join(sorted(missing)))

    # 2) 중복 id
    dup=pg.evaluate("""()=>{const c={};document.querySelectorAll('[id]').forEach(e=>c[e.id]=(c[e.id]||0)+1);
      return Object.entries(c).filter(([,v])=>v>1).map(([k,v])=>k+'×'+v);}""")
    if dup: bad.append("중복 id: "+", ".join(dup))

    # 3) 주요 화면을 한 바퀴 돌린다 (로그인 없이 가능한 범위)
    pg.evaluate("""()=>{ window.CURRENT_CONN='medit';
      state.user={name:'점검',role:'operator',email:'qa@example.invalid'};
      state.meetings=[{id:'t1',title:'점검 회의',date:'2026-10-17',host:'점검',attendees:[{name:'점검',email:'qa@example.invalid'}]}];
    }""")
    for fn in ["showMeetingList","showConnList","renderResearch","renderFiles","opsPanel","diagStatus"]:
        r=pg.evaluate(f"()=>{{try{{ if(typeof {fn}==='function') {fn}(); return '' }}catch(e){{return String(e)}}}}")
        if r: bad.append(f"{fn}() 실행 중 오류: {r[:160]}")
    pg.wait_for_timeout(1500)
    if errs: bad.append("스크립트 오류 %d건: %s"%(len(errs)," | ".join(errs[:3])[:300]))
    b.close()
print("=== 버그 점검 ===")
print("\n".join(" · "+x for x in bad) if bad else "이상 없음")
print("총",len(bad),"건")
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"],"a") as f: f.write("rc=%d\n"%(1 if bad else 0))
open("handler-report.md","w",encoding="utf-8").write(
  "### 핸들러·렌더 점검\n\n"+("\n".join("- "+x for x in bad) if bad else "이상 없음")+"\n")
raise SystemExit(1 if bad else 0)
