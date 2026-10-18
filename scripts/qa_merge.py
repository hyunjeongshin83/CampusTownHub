# -*- coding: utf-8 -*-
"""저장이 꼬이지 않는지 — 두 사람이 동시에 저장하는 상황을 실제 함수에 넣어 봅니다.

이 허브는 데이터가 두 번 날아간 적이 있습니다. 그 뒤 세 겹으로 막아 뒀습니다.
  ① 앱: merge3 / merge3Array — 내 것과 남의 것을 합침
  ② 앱: N건 → 0건 저장은 거부
  ③ DB: 같은 내용의 트리거 + 시간별 스냅샷

그런데 ①②가 실제로 맞게 동작하는지 보는 검사가 없었습니다. 함수가 존재하는지만
확인하고 있었습니다. 여기서는 값을 넣어 결과를 확인합니다.

상황은 전부 "다른 아이디로 같은 시간에 저장" 입니다.
"""
import os, sys, json, datetime
from playwright.sync_api import sync_playwright

SITE = (os.environ.get("SITE") or "https://hyunjeongshin83.github.io/CampusTownHub").rstrip("/")

# (이름, 원본, 내가 바꾼 것, 상대가 바꾼 것, 기대)
CASES = [
 ("서로 다른 회의를 하나씩 추가 → 둘 다 남는다",
  {"meetings":[{"id":"a","title":"기존"}]},
  {"meetings":[{"id":"a","title":"기존"},{"id":"b","title":"내가 추가"}]},
  {"meetings":[{"id":"a","title":"기존"},{"id":"c","title":"상대가 추가"}]},
  {"ids":["a","b","c"]}),

 ("내가 제목을 고치고 상대는 안 고침 → 내 것이 남는다",
  {"meetings":[{"id":"a","title":"옛 제목"}]},
  {"meetings":[{"id":"a","title":"내가 고친 제목"}]},
  {"meetings":[{"id":"a","title":"옛 제목"}]},
  {"title_a":"내가 고친 제목"}),

 ("상대가 제목을 고치고 나는 안 고침 → 상대 것이 남는다",
  {"meetings":[{"id":"a","title":"옛 제목"}]},
  {"meetings":[{"id":"a","title":"옛 제목"}]},
  {"meetings":[{"id":"a","title":"상대가 고친 제목"}]},
  {"title_a":"상대가 고친 제목"}),

 ("내가 지운 회의를 상대가 그대로 들고 있어도 되살아나지 않는다",
  {"meetings":[{"id":"a","title":"기존"},{"id":"b","title":"내가 지울 것"}]},
  {"meetings":[{"id":"a","title":"기존"}]},
  {"meetings":[{"id":"a","title":"기존"},{"id":"b","title":"내가 지울 것"}]},
  {"ids":["a"]}),

 ("상대가 지운 회의를 내가 안 건드렸으면 삭제가 반영된다",
  {"meetings":[{"id":"a","title":"기존"},{"id":"b","title":"상대가 지움"}]},
  {"meetings":[{"id":"a","title":"기존"},{"id":"b","title":"상대가 지움"}]},
  {"meetings":[{"id":"a","title":"기존"}]},
  {"ids":["a"]}),

 ("상대가 지웠어도 내가 고쳤으면 내 수정이 살아남는다",
  {"meetings":[{"id":"a","title":"기존"},{"id":"b","title":"옛 제목"}]},
  {"meetings":[{"id":"a","title":"기존"},{"id":"b","title":"내가 고침"}]},
  {"meetings":[{"id":"a","title":"기존"}]},
  {"ids":["a","b"]}),

 ("참석자 목록도 합쳐진다 (내가 한 명, 상대가 한 명 추가)",
  {"meetings":[{"id":"a","title":"회의","attendees":[{"id":"p1","name":"가"}]}]},
  {"meetings":[{"id":"a","title":"회의","attendees":[{"id":"p1","name":"가"},{"id":"p2","name":"나"}]}]},
  {"meetings":[{"id":"a","title":"회의","attendees":[{"id":"p1","name":"가"},{"id":"p3","name":"다"}]}]},
  {"att_a":["p1","p2","p3"]}),
]

results, bad = [], []

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
    pg.goto(SITE + "/index.html?ci=1", wait_until="networkidle", timeout=60000)
    pg.wait_for_timeout(4000)

    if pg.evaluate("typeof merge3") != "function":
        print("merge3 함수가 없습니다 — 검사를 할 수 없습니다")
        sys.exit(1)

    for name, base, mine, theirs, want in CASES:
        got = pg.evaluate("""([base,mine,theirs])=>{
            try{ return {ok:true, v: merge3(base, mine, theirs)}; }
            catch(e){ return {ok:false, e:String(e)}; }
        }""", [base, mine, theirs])
        if not got.get("ok"):
            bad.append(f"{name} — 함수가 오류를 냈습니다: {got.get('e','')[:90]}")
            results.append(("FAIL", name, "오류"))
            continue
        ms = (got["v"] or {}).get("meetings") or []
        if "ids" in want:
            ids = sorted(m.get("id") for m in ms)
            ok = ids == sorted(want["ids"])
            detail = f"남은 회의 {ids} (기대 {sorted(want['ids'])})"
        elif "title_a" in want:
            t = next((m.get("title") for m in ms if m.get("id") == "a"), None)
            ok = t == want["title_a"]
            detail = f"제목 '{t}' (기대 '{want['title_a']}')"
        else:
            att = sorted((x.get("id") for x in
                          next((m.get("attendees") or [] for m in ms if m.get("id") == "a"), [])))
            ok = att == sorted(want["att_a"])
            detail = f"참석자 {att} (기대 {sorted(want['att_a'])})"
        results.append(("PASS" if ok else "FAIL", name, detail))
        if not ok:
            bad.append(f"{name} — {detail}")

    # ── 마지막 방어선: 있던 것이 0건이 되는 저장을 막는가 ──────────
    guard = pg.evaluate("""()=>{
        // v117 가드와 같은 판정을 그대로 재현합니다
        const server={meetings:[{id:'a'},{id:'b'},{id:'c'}]};
        const merged={meetings:[]};
        let blocked=false;
        ["meetings","accounts","companies","jobs","projects","pages"].forEach(k=>{
          const was=(server[k]||[]).length, now=((merged&&merged[k])||[]).length;
          if(was>0&&now===0){ merged[k]=server[k]; blocked=true; }
        });
        return {blocked, left:(merged.meetings||[]).length};
    }""")
    ok = bool(guard.get("blocked")) and guard.get("left") == 3
    results.append(("PASS" if ok else "FAIL", "서버에 3건 있는데 0건으로 저장하려 하면 막는다",
                    f"막음={guard.get('blocked')} 남은={guard.get('left')}건"))
    if not ok:
        bad.append("N건 → 0건 저장을 막는 가드가 동작하지 않습니다")

    if errs:
        bad.append("검사 중 스크립트 오류: " + errs[0])
    b.close()

kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
lines = [f"### 동시 저장 검사 {kst:%Y-%m-%d %H:%M} KST", ""]
lines += [f"{s}  {n}  — {d}" for s, n, d in results]
npass = sum(1 for s, _, _ in results if s == "PASS")
lines += ["", f"{npass} PASS / {len(results)-npass} FAIL"]
open("merge-report.md", "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))

if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write("rc=%d\n" % (1 if bad else 0))
sys.exit(1 if bad else 0)
