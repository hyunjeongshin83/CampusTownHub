# -*- coding: utf-8 -*-
"""허브 자동 점검 — 사이트·배포·DB 접근을 확인하고 이상을 보고한다."""
import os, re, json, urllib.request, urllib.error, datetime

SITE = os.environ.get("SITE", "").rstrip("/")
SB_URL = os.environ.get("SB_URL", "").rstrip("/")
SB_ANON = os.environ.get("SB_ANON", "")
KST = datetime.timezone(datetime.timedelta(hours=9))

problems, notes = [], []

def get(url, headers=None, timeout=25):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()

# 1. 사이트가 살아 있는가
build = None
try:
    st, raw = get(SITE + "/index.html")
    txt = raw.decode("utf-8", "replace")
    m = re.search(r"const BUILD=(\d+)", txt)
    build = m.group(1) if m else None
    if st != 200:
        problems.append(f"사이트 응답 코드 {st}")
    if not build:
        problems.append("BUILD 번호를 찾지 못했습니다 — 파일이 손상되었을 수 있습니다")
    if not txt.rstrip().endswith("</html>"):
        problems.append("index.html이 </html> 없이 끝납니다 — 전송이 잘렸습니다")
    if len(raw) < 400_000:
        problems.append(f"index.html 크기 이상: {len(raw):,} B")
    notes.append(f"사이트 HTTP {st} · BUILD {build} · {len(raw):,} B")
except Exception as e:
    problems.append(f"사이트 접속 실패: {e}")

# 2. 복구 도구가 살아 있는가
try:
    st, _ = get(SITE + "/recover.html")
    if st != 200:
        problems.append(f"recover.html 응답 {st}")
    notes.append(f"복구 도구 HTTP {st}")
except Exception as e:
    problems.append(f"recover.html 접속 실패: {e}")

# 3. DB REST가 응답하는가 (anon 자격 — RLS로 0건인 것은 정상)
if SB_URL and SB_ANON:
    try:
        h = {"apikey": SB_ANON, "Authorization": "Bearer " + SB_ANON}
        st, raw = get(SB_URL + "/rest/v1/hub_state?select=key&limit=1", h)
        if st != 200:
            problems.append(f"Supabase REST 응답 {st}")
        notes.append(f"Supabase REST HTTP {st} (anon 조회 {len(json.loads(raw))}건 — RLS 정상 동작)")
    except Exception as e:
        problems.append(f"Supabase 접속 실패: {e}")
else:
    notes.append("Supabase 점검 건너뜀 — SB_ANON_KEY 시크릿 미설정")

now = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
status = "ok" if not problems else "ng"

lines = [f"### 자동 점검 {now}", ""]
if problems:
    lines += ["**확인이 필요합니다**", ""] + [f"- {p}" for p in problems] + [""]
else:
    lines += ["이상 없음", ""]
lines += ["<details><summary>점검 내역</summary>", ""] + [f"- {n}" for n in notes] + ["", "</details>"]
open("watch-report.md", "w", encoding="utf-8").write("\n".join(lines))

with open(os.environ["GITHUB_OUTPUT"], "a") as f:
    f.write(f"status={status}\n")
    f.write(f"build={build}\n")

print("\n".join(lines))
