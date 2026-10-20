# -*- coding: utf-8 -*-
"""UX·UI 전수 점검 — 눈으로 보이는 것을 기계가 먼저 봅니다.

기능 점검(훑기·세션·단추)은 「돌아가는가」를 봅니다. 이 도구는 「쓸 만한가」를 봅니다.
휴대폰·태블릿·데스크톱 세 폭에서 모든 탭을 열어 아래를 잽니다.

  · 가로로 삐져나가는가        — 휴대폰에서 옆으로 밀리면 글이 잘립니다
  · 손가락으로 누를 만한가      — 44×44 보다 작은 단추는 노인·떨리는 손에 안 눌립니다
  · 글자가 읽히는가            — WCAG 상대휘도로 실제 색을 재서 4.5:1 미만을 잡습니다
  · 무엇인지 알 수 있는가       — 글자도 설명도 없는 단추, 이름 없는 입력칸
  · id 가 겹치지 않는가        — 겹치면 $() 가 엉뚱한 것을 집습니다

고령친화가 이 앱의 전제입니다(교수님 연구실·입점기업·거래처가 씁니다).
그래서 44px 과 4.5:1 을 눈대중이 아니라 숫자로 지킵니다.
"""
import os, sys, json, functools, datetime
print = functools.partial(print, flush=True)
from playwright.sync_api import sync_playwright

SITE = (os.environ.get("SITE") or "http://localhost:8099").rstrip("/")
WIDTHS = [("휴대폰", 390, 844), ("태블릿", 768, 1024), ("데스크톱", 1440, 900)]
TABS = ["home", "prep", "deck", "video", "projects", "schedule", "lit", "console", "email"]

JS_AUDIT = r"""
(args)=>{
  const [tabName, narrow] = args;
  const out={tab:tabName, overflow:null, small:[], contrast:[], nameless:[], dupIds:[]};

  // ① 가로 넘침 — 문서가 창보다 넓으면 글이 잘립니다
  const de=document.documentElement;
  if(de.scrollWidth > de.clientWidth+1){
    // 가로로 넘기는 칸(overflow-x:auto) 안에 있는 것은 일부러 그런 것이므로 뺍니다 —
    // 안 그러면 탭 줄처럼 「옆으로 미는」 설계를 전부 잘못이라고 올립니다.
    const inScroller=e=>{ let n=e.parentElement;
      while(n && n!==document.documentElement){
        const ox=getComputedStyle(n).overflowX;
        if(ox==='auto'||ox==='scroll'||ox==='hidden') return true;
        n=n.parentElement; }
      return false; };
    const wide=[...document.querySelectorAll('body *')].filter(e=>{
      const r=e.getBoundingClientRect();
      return r.width>0 && (r.right > de.clientWidth+1.5)
             && getComputedStyle(e).position!=='fixed' && !inScroller(e);
    }).slice(0,4).map(e=>(e.id?('#'+e.id):e.tagName.toLowerCase()+'.'+(e.className||'').toString().split(' ')[0])
                         +' ('+Math.round(e.getBoundingClientRect().right)+'px)');
    out.overflow={doc:de.scrollWidth, win:de.clientWidth, who:wide};
  }

  const vis=e=>{ const r=e.getBoundingClientRect(); const s=getComputedStyle(e);
    return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'&&Number(s.opacity)>0.05; };
  const label=e=>((e.innerText||'')+' '+(e.getAttribute('aria-label')||'')+' '+(e.getAttribute('title')||'')).trim().replace(/\s+/g,' ').slice(0,28);

  // ② 누를 수 있는 것의 크기 — 좁은 화면(손가락)에서만 잽니다
  if(narrow){
    // 체크상자·라디오는 그 자체가 작아도 됩니다 — 감싼 라벨이 누르는 범위입니다.
    const hit=e=>{
      const t=(e.getAttribute('type')||'').toLowerCase();
      if(t==='checkbox'||t==='radio'){
        const L=e.closest('label') || e.parentElement;
        if(L) return L.getBoundingClientRect();
      }
      return e.getBoundingClientRect(); };
    [...document.querySelectorAll('button,[role=button],a[href],select,input:not([type=hidden])')]
      .filter(vis).forEach(e=>{
        const r=hit(e);
        if(r.height < 43.5 || r.width < 24){
          out.small.push({t:label(e)||('<'+e.tagName.toLowerCase()+'>'), w:Math.round(r.width), h:Math.round(r.height)});
        }
      });
  }

  // ③ 글자 대비 — 실제로 칠해진 색을 올라가며 찾아 잽니다
  const lum=c=>{ const v=c.map(x=>{x/=255; return x<=0.04045?x/12.92:Math.pow((x+0.055)/1.055,2.4);});
                 return 0.2126*v[0]+0.7152*v[1]+0.0722*v[2]; };
  const rgb=s=>{ const m=(s||'').match(/rgba?\(([^)]+)\)/); if(!m) return null;
                 const p=m[1].split(',').map(Number); return {c:[p[0],p[1],p[2]], a:(p.length>3?p[3]:1)}; };
  // 배경은 겹쳐서 칠해집니다 — 반투명 패널 아래 또 반투명, 그 아래 본문 그라데이션.
  // 겹친 것을 실제로 합성해야 사람 눈이 보는 색이 나옵니다.
  // (처음엔 「알파 0.75 넘으면 불투명」으로 어림했다가, 탭 줄(흰색 72%)을 건너뛰고
  //  본문 그라데이션을 집어 1.15:1 같은 엉뚱한 값을 냈습니다. 틀린 숫자를 내는
  //  검사는 없느니만 못합니다.)
  const blend=(c,a,b)=>[0,1,2].map(i=>c[i]*a + b[i]*(1-a));
  const gstops=s=>{ const m=(s||'').match(/rgba?\([^)]+\)/g);
                    return m ? m.map(x=>rgb(x)).filter(Boolean) : []; };
  const bgOf=e=>{
    const layers=[];                      // 글자 쪽부터 위로 모읍니다
    let n=e, opaque=false;
    while(n && n!==document.documentElement && !opaque){
      const s=getComputedStyle(n);
      const g=gstops(s.backgroundImage);          // 그림은 색 위에 칠해집니다
      if(g.length) layers.push({g:g});
      const b=rgb(s.backgroundColor);
      if(b && b.a>0.001){ layers.push({c:b.c,a:b.a}); if(b.a>=0.999) opaque=true; }
      n=n.parentElement;
    }
    let cands=[[255,255,255]];            // 바탕은 흰색으로 둡니다
    for(let i=layers.length-1;i>=0;i--){  // 뿌리 쪽부터 글자 쪽으로 덮어 갑니다
      const L=layers[i], next=[];
      cands.forEach(base=>{
        if(L.g) L.g.forEach(st=>next.push(blend(st.c, st.a, base)));
        else next.push(blend(L.c, L.a, base));
      });
      cands=next.slice(0,8);              // 지점이 많아도 여덟까지만
    }
    return cands; };
  const ratio=(a,b)=>{ const la=lum(a), lb=lum(b); const hi=Math.max(la,lb), lo=Math.min(la,lb);
                       return (hi+0.05)/(lo+0.05); };
  const seen=new Set();
  [...document.querySelectorAll('body *')].filter(vis).forEach(e=>{
    if(e.children.length) return;                       // 글자를 직접 가진 것만
    const txt=(e.textContent||'').trim(); if(txt.length<2) return;
    const s=getComputedStyle(e);
    const fg=rgb(s.color); if(!fg || fg.a<0.6) return;
    const px=parseFloat(s.fontSize)||16, bold=(parseInt(s.fontWeight)||400)>=700;
    const big=(px>=24)||(px>=18.66&&bold);
    const need=big?3.0:4.5;
    const bgs=bgOf(e);
    const r=Math.min(...bgs.map(bg=>ratio(fg.c, bg)));   // 가장 불리한 지점
    if(r < need){
      const key=s.color+'|'+Math.round(px)+'|'+txt.slice(0,12);
      if(seen.has(key)) return; seen.add(key);
      out.contrast.push({t:txt.slice(0,34), px:Math.round(px), r:Math.round(r*100)/100, need:need,
                         fg:s.color, bg:'rgb('+bgs[0].map(x=>Math.round(x)).join(',')+')',
                         where:(e.className||'').toString().split(' ')[0]||e.tagName.toLowerCase()});
    }
  });

  // ④ 무엇인지 알 수 없는 것
  [...document.querySelectorAll('button,[role=button]')].filter(vis).forEach(e=>{
    if(!label(e)) out.nameless.push('<'+e.tagName.toLowerCase()+(e.id?'#'+e.id:'')+'>');
  });
  [...document.querySelectorAll('input:not([type=hidden]),select,textarea')].filter(vis).forEach(e=>{
    const has=e.getAttribute('aria-label')||e.getAttribute('title')||e.getAttribute('placeholder')
            ||(e.id&&document.querySelector('label[for="'+CSS.escape(e.id)+'"]'))
            ||e.closest('label');
    if(!has) out.nameless.push('입력칸 '+(e.id?('#'+e.id):'<'+e.tagName.toLowerCase()+'>'));
  });

  // ⑤ 겹친 id — $() 가 엉뚱한 것을 집습니다
  const ids={};
  document.querySelectorAll('[id]').forEach(e=>{ ids[e.id]=(ids[e.id]||0)+1; });
  Object.keys(ids).forEach(k=>{ if(ids[k]>1) out.dupIds.push(k+' ×'+ids[k]); });

  return out;
}
"""

SEED = """()=>{
  state.user={role:'operator',name:'점검',email:'ux@example.invalid',id:'ux'};
  state.meetings=[{id:'ux1',title:'UX 점검용 회의',date:'2026-10-20',time:'10:00',place:'온라인',
    attendees:[{name:'점검'},{name:'방준석 교수님'},{name:'박지현'}]}];
  state.currentMeetingId='ux1';
  if(typeof syncCurrentMeeting==='function') syncCurrentMeeting();
  if(typeof enterHub==='function') enterHub();
}"""

fails, notes = [], []
seen_small, seen_contrast, seen_nameless, seen_dup = {}, {}, set(), set()

with sync_playwright() as p:
    b = p.chromium.launch()
    for wname, w, hgt in WIDTHS:
        narrow = w < 820
        ctx = b.new_context(viewport={"width": w, "height": hgt},
                            has_touch=narrow, is_mobile=narrow)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:140]))
        pg.goto(SITE + "/index.html?ci=1", wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(4200)
        pg.evaluate(SEED)
        pg.wait_for_timeout(900)

        for tab in TABS:
            try:
                pg.evaluate("(t)=>{ try{ switchTab(t); }catch(e){} }", tab)
            except Exception:
                continue
            pg.wait_for_timeout(700)
            try:
                r = pg.evaluate(JS_AUDIT, [tab, narrow])
            except Exception as e:
                notes.append(f"[{wname}/{tab}] 점검 중 오류: {str(e)[:70]}")
                continue

            if r["overflow"]:
                o = r["overflow"]
                fails.append(f"[{wname} {w}px · {tab}] 화면이 가로로 {o['doc']-o['win']}px 삐져나갑니다 — "
                             + ", ".join(o["who"][:3]))
            for s in r["small"]:
                key = (s["t"], s["h"])
                if key not in seen_small:
                    seen_small[key] = f"[{wname}·{tab}] {s['t']} ({s['w']}×{s['h']})"
            for c in r["contrast"]:
                key = (c.get("fg"), c["px"], c.get("where"))
                if key not in seen_contrast:
                    seen_contrast[key] = (f"{c.get('fg')} / 바탕 {c.get('bg')} · {c['px']}px"
                                          f" · .{c.get('where')} — {c['r']}:1 (필요 {c['need']}:1) 예: “{c['t'][:16]}”")
            for n in r["nameless"]:
                seen_nameless.add(f"[{tab}] {n}")
            for d in r["dupIds"]:
                seen_dup.add(f"[{tab}] {d}")

        if errs:
            fails.append(f"[{wname}] 스크립트 오류: {errs[0]}")
        ctx.close()
    b.close()

if seen_small:
    v = list(seen_small.values())
    fails.append(f"손가락으로 누르기 작은 것 {len(v)}개 (44px 미만): " + " · ".join(v[:6]))
if seen_contrast:
    v = list(seen_contrast.values())
    fails.append(f"글자 대비 미달 {len(v)}곳: " + " · ".join(v[:6]))
if seen_nameless:
    fails.append(f"무엇인지 알 수 없는 것 {len(seen_nameless)}개: " + " · ".join(list(seen_nameless)[:6]))
if seen_dup:
    fails.append(f"id 가 겹칩니다 {len(seen_dup)}개: " + " · ".join(list(seen_dup)[:6]))

notes.append(f"본 화면 폭 {len(WIDTHS)}종 × 탭 {len(TABS)}개")
notes.append("기준: 터치 44×44(체크상자는 감싼 라벨 기준) · 보통 글자 4.5:1 · 큰 글자 3:1 (WCAG 상대휘도로 실측)")
notes.append("그라데이션 배경은 색 지점을 모두 재서 가장 불리한 곳의 값을 씁니다")

kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
lines = [f"### UX·UI 점검 {kst:%Y-%m-%d %H:%M} KST", ""]
lines += (["**살펴볼 것**", ""] + [f"- {x}" for x in fails] + [""]) if fails else ["이상 없음", ""]
lines += ["<details><summary>본 것</summary>", ""] + [f"- {n}" for n in notes] + ["", "</details>"]
open("ux-report.md", "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))

if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write("rc=%d\n" % (1 if fails else 0))
sys.exit(1 if fails else 0)
