# -*- coding: utf-8 -*-
"""보안 기본값 점검.

오늘(2026-10-18) 이런 일이 있었습니다. 역할·권한 검사 16건이 전부 통과하는데도
초대하지 않은 구글 계정으로 로그인이 됐습니다. OPEN_SIGNUP 이 true 라
allowedEmail() 이 어떤 이메일이든 통과시키고 있었고, 화면에서 회의만 가려질 뿐
로그인 자체는 막히지 않았습니다.

기존 검사가 못 잡은 이유: "보이는가"만 봤지 "들어올 수 있는가"를 안 봤습니다.
여기서는 설정값과 문지기를 직접 봅니다.
"""
import os, re, sys, random, string, datetime
from playwright.sync_api import sync_playwright

SITE = (os.environ.get("SITE") or "https://hyunjeongshin83.github.io/CampusTownHub").rstrip("/")
bad, notes = [], []

def rnd(n=8):
    return "".join(random.choice(string.ascii_lowercase) for _ in range(n))

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    pg.goto(SITE + "/index.html?ci=1", wait_until="networkidle", timeout=60000)
    pg.wait_for_timeout(4000)

    # ── 1. 가입 문이 열려 있지 않은지 ─────────────────────────
    opn = pg.evaluate("typeof OPEN_SIGNUP!=='undefined' ? OPEN_SIGNUP : 'none'")
    notes.append(f"OPEN_SIGNUP = {opn}")
    if opn is True:
        bad.append("OPEN_SIGNUP 이 true 입니다 — 초대하지 않은 아무 구글 계정이나 로그인됩니다")
    elif opn == "none":
        bad.append("OPEN_SIGNUP 전역이 없습니다 — 가입 정책을 확인할 수 없습니다")

    # ── 2. 문지기가 실제로 막는지 (초대 안 된 임의 계정) ──────
    out = pg.evaluate("""(e)=>{
        try{ return (typeof allowedEmail==='function') ? allowedEmail(e) : 'nofn'; }
        catch(err){ return 'err:'+err.message; }
    }""", f"{rnd()}@{rnd()}.invalid")
    notes.append(f"초대 안 된 임의 계정 통과 여부 = {out}")
    if out is True:
        bad.append("초대하지 않은 임의 계정이 allowedEmail() 을 통과합니다")
    elif out == "nofn":
        bad.append("allowedEmail() 이 없습니다 — 문지기가 사라졌습니다")

    # ── 3. 허용 도메인이 의도대로인지 ─────────────────────────
    doms = pg.evaluate("typeof ALLOWED_DOMAINS!=='undefined' ? ALLOWED_DOMAINS : null")
    notes.append(f"허용 도메인 = {doms}")
    if not doms:
        bad.append("ALLOWED_DOMAINS 가 비어 있습니다")
    elif any(d in ("gmail.com", "naver.com", "*") for d in doms):
        bad.append(f"허용 도메인에 공개 메일 도메인이 있습니다: {doms}")

    # ── 4. 숙명 계정은 들어올 수 있어야 한다 (너무 잠그지 않았는지) ──
    ok = pg.evaluate("""()=>{ try{ return allowedEmail('qa-'+Math.random().toString(36).slice(2)+'@sookmyung.ac.kr'); }
                             catch(e){ return 'err'; } }""")
    notes.append(f"숙명 계정 통과 여부 = {ok}")
    if ok is not True:
        bad.append("숙명(@sookmyung.ac.kr) 계정이 막혔습니다 — 너무 잠겼습니다")

    # ── 5. 배포본에 비밀값이 섞이지 않았는지 ──────────────────
    src = pg.content()
    # 화면 안내 문구에 "sk-ant-…" 같은 예시가 들어 있습니다. 실제 키 길이까지 봐야
    # 안내와 진짜 키를 구별할 수 있습니다 (2026-10-18 오탐 교정).
    for pat, what in [(r"sb_secret_[A-Za-z0-9_-]{15,}", "Supabase secret key"),
                      (r"github_pat_11[A-Za-z0-9_]{20,}", "GitHub 토큰"),
                      (r"KakaoAK\s+[A-Za-z0-9]{20,}", "카카오 REST/Admin 키"),
                      (r"sk-ant-[A-Za-z0-9_-]{30,}", "Anthropic API 키")]:
        if re.search(pat, src):
            bad.append(f"배포본에 {what} 가 들어 있습니다")
    notes.append("비밀값 4종 스캔 완료")

    if errs:
        bad.append("스크립트 오류 %d건: %s" % (len(errs), errs[0]))
    b.close()

kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
lines = [f"### 보안 기본값 점검 {kst:%Y-%m-%d %H:%M} KST", ""]
lines += (["**확인이 필요합니다**", ""] + [f"- {x}" for x in bad] + [""]) if bad else ["이상 없음", ""]
lines += ["<details><summary>점검 내역</summary>", ""] + [f"- {n}" for n in notes] + ["", "</details>"]
open("security-report.md", "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))

if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write("rc=%d\n" % (1 if bad else 0))
sys.exit(1 if bad else 0)
