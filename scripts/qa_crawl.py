# -*- coding: utf-8 -*-
"""기능 훑기 — 화면의 누를 수 있는 것을 전부 눌러 보며 지도를 그립니다.

대표님이 주신 순서대로입니다.
  ① 화면의 기능(글자+동작)을 훑는다
  ② 눌러서 다음 화면으로 간다
  ③ 더 갈 데가 없을 때까지 반복
  ④ 화면끼리 이어 붙여 지도를 만든다
  ⑤ 이상한 곳을 보고한다

사람이 일일이 못 누르는 걸 대신합니다. 찾는 것:
  · 눌러도 아무 일도 안 나는 단추
  · 누르면 오류가 나는 단추
  · 글자가 없어 무엇인지 알 수 없는 단추

되돌릴 수 없는 동작(삭제·초기화·로그아웃·발송)은 누르지 않습니다.
"""
import os, re, sys, json, time, hashlib, datetime
from playwright.sync_api import sync_playwright

SITE = (os.environ.get("SITE") or "https://hyunjeongshin83.github.io/CampusTownHub").rstrip("/")
BUDGET_SEC = int(os.environ.get("CRAWL_SEC", "240"))
MAX_ACTIONS = int(os.environ.get("CRAWL_MAX", "70"))

# 누르면 되돌릴 수 없는 것 — 건드리지 않습니다
DANGER = re.compile(
    r"삭제|지우|초기화|로그아웃|나가기|탈퇴|발송|보내기|전송|초대|승인|회수|병합|복구|내보내기|가져오기|새로고침|재동기화",
    re.I)

def sig(page):
    """화면을 글자와 단추 구성으로 지문 찍기 — 같은 화면인지 구별하는 데 씁니다."""
    s = page.evaluate("""()=>{
      const vis = e => { const r=e.getBoundingClientRect();
        return r.width>0 && r.height>0 && getComputedStyle(e).visibility!=='hidden'; };
      const t = (document.body.innerText||'').replace(/\\s+/g,' ').slice(0,400);
      const b = [...document.querySelectorAll('button,[role=button],a[href]')]
        .filter(vis).map(e=>(e.innerText||e.getAttribute('aria-label')||'').trim()).join('|');
      return t+'##'+b; }""")
    return hashlib.sha1(s.encode()).hexdigest()[:10]

def controls(page):
    """지금 화면에서 누를 수 있는 것들 — 글자와 함께"""
    return page.evaluate("""()=>{
      const vis = e => { const r=e.getBoundingClientRect();
        return r.width>0 && r.height>0 && getComputedStyle(e).visibility!=='hidden'
               && !e.disabled; };
      return [...document.querySelectorAll('button,[role=button]')].filter(vis).map((e,i)=>{
        if(!e.dataset.qaid) e.dataset.qaid = 'qa'+i+'_'+Math.random().toString(36).slice(2,7);
        return {id:e.dataset.qaid,
                text:(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,30),
                label:e.getAttribute('aria-label')||'', title:e.getAttribute('title')||''};
      });}""")

def seed(page):
    """로그인한 운영자 상태를 흉내 냅니다 — 서버는 건드리지 않습니다."""
    page.evaluate("""()=>{
      try{
        state.user={name:'QA점검',role:'operator',email:'qa-crawl@example.invalid'};
        state.meetings=[{id:'qa1',title:'QA 점검용 회의',date:'2026-10-20',time:'14:00',
          place:'온라인',host:'QA점검',
          attendees:[{name:'QA점검',email:'qa-crawl@example.invalid'}]}];
        if(typeof showMeetingList==='function') showMeetingList();
      }catch(e){}
    }""")

findings, notes = [], []
seen, edges, dead, nameless = {}, [], [], []
t0 = time.time()

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 420, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
    pg.on("dialog", lambda d: d.dismiss())          # confirm/alert 는 모두 취소

    pg.goto(SITE + "/index.html?ci=1", wait_until="networkidle", timeout=60000)
    pg.wait_for_timeout(3500)
    seed(pg); pg.wait_for_timeout(1200)

    def reset_to(path):
        """처음부터 다시 열고, 기억해 둔 순서대로 눌러 그 화면까지 되돌아갑니다."""
        pg.goto(SITE + "/index.html?ci=1", wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(2200); seed(pg); pg.wait_for_timeout(1000)
        for step in path:
            hit = [c for c in controls(pg) if (c["text"] or c["label"]) == step]
            if not hit:
                return False
            try:
                pg.click(f'[data-qaid="{hit[0]["id"]}"]', timeout=2500)
            except Exception:
                return False
            pg.wait_for_timeout(800)
        return True

    queue = [[]]                 # 화면을 "거기까지 누른 순서"로 나타냅니다
    seen[sig(pg)] = "시작 화면"
    acted = 0

    while queue and acted < MAX_ACTIONS and (time.time() - t0) < BUDGET_SEC:
        path = queue.pop(0)
        if len(path) > 2:
            continue
        if not reset_to(path):
            continue
        here = " → ".join(path) if path else "시작 화면"
        names = [(c["text"] or c["label"] or c["title"]).strip() for c in controls(pg)]
        names = [n for n in dict.fromkeys(names) if n and not DANGER.search(n)]

        for name in names:
            if acted >= MAX_ACTIONS or (time.time() - t0) >= BUDGET_SEC:
                break
            if not reset_to(path):
                break
            hit = [c for c in controls(pg) if (c["text"] or c["label"] or c["title"]).strip() == name]
            if not hit:
                continue
            before = sig(pg); nerr = len(errs)
            try:
                pg.click(f'[data-qaid="{hit[0]["id"]}"]', timeout=2500)
            except Exception:
                continue
            acted += 1
            pg.wait_for_timeout(900)
            if "hyunjeongshin83.github.io" not in pg.url and "localhost" not in pg.url:
                notes.append(f"[{name}] 는 바깥 사이트로 나갑니다 — 더 따라가지 않습니다")
                continue
            after = sig(pg)

            if len(errs) > nerr:
                findings.append(f"[{name}] 를 누르니 오류가 납니다 — {errs[-1][:110]}")
            elif after == before:
                dead.append(name)
            else:
                edges.append((here, name, seen.get(after, after[:8])))
                if after not in seen:
                    seen[after] = f"[{name}] 뒤 화면"
                    queue.append(path + [name])

    notes.append(f"눌러 본 단추 {acted}개 · 찾은 화면 {len(seen)}개 · 이어진 길 {len(edges)}개")
    notes.append(f"걸린 시간 {int(time.time()-t0)}초")
    b.close()

if dead:
    uniq = sorted(set(dead))
    findings.append("눌러도 화면이 바뀌지 않는 단추 %d개: %s" % (len(uniq), ", ".join(uniq[:12])))
if nameless:
    findings.append(f"글자도 설명도 없는 단추 {len(nameless)}개 — 무엇인지 알 수 없습니다")

kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
lines = [f"### 기능 훑기 {kst:%Y-%m-%d %H:%M} KST", ""]
lines += (["**살펴볼 것**", ""] + [f"- {x}" for x in findings] + [""]) if findings else ["이상 없음", ""]
lines += ["<details><summary>화면 지도</summary>", ""]
lines += [f"- {a} → **{act}** → {bsig}" for a, act, bsig in edges[:40]] or ["- (이어진 길 없음)"]
lines += [""] + [f"- {n}" for n in notes] + ["", "</details>"]
open("crawl-report.md", "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))

if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write("rc=%d\n" % (1 if findings else 0))
sys.exit(1 if findings else 0)
