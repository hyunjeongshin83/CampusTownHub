# -*- coding: utf-8 -*-
"""AI 준비 상태 점검 — 「AI 회의록이 안 켜진다」를 사람이 묻기 전에 잡습니다.

2026-10-19 에 실제로 있던 일: 교수님께 보여 드릴 AI 회의록이 안 되는데
화면에는 "AI 키 필요 (sk-ant-…)" 창이 떴습니다. 서버에는 열쇠가 멀쩡히 있었고
막고 있던 것은 로그인 하나였습니다. 원인을 잘못 가리키면 없는 문제를 고치게 됩니다.

여기서 보는 것 (열쇠 값은 절대 읽지 않습니다 — 있는지 없는지만):
  · 프록시 함수가 살아 있는가
  · 서버에 ANTHROPIC_API_KEY 가 들어 있는가
  · 쓰는 모델이 아직 살아 있는 이름인가 (은퇴한 이름이면 호출이 전부 실패합니다)
  · 앱이 부르는 함수 이름과 실제로 배포된 이름이 맞는가
"""
import os, re, sys, json, datetime, urllib.request, urllib.error

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(HERE, "index.html")

findings, notes = [], []
html = open(PAGE, encoding="utf-8").read()

# 앱이 들고 있는 값 — 하드코딩하지 않고 화면 파일에서 읽습니다
m = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', html)
url = m.group(1).rstrip("/") if m else ""
m = re.search(r'SUPABASE_ANON_KEY\s*=\s*"([^"]+)"', html)
anon = m.group(1) if m else ""
m = re.search(r'AI_PROXY_NAMES\s*=\s*\[([^\]]+)\]', html)
names = re.findall(r'"([^"]+)"', m.group(1)) if m else []
models = re.findall(r'AI_MODEL(?:_CHEAP)?\s*=\s*"([^"]+)"', html)

if not url or not anon:
    findings.append("화면 파일에서 Supabase 주소·공개키를 찾지 못했습니다")
if not names:
    findings.append("AI_PROXY_NAMES 를 찾지 못했습니다 — AI 경로가 비어 있습니다")

alive, has_key, served_models = [], [], set()
for fn in names:
    body = json.dumps({"ping": True}).encode()
    req = urllib.request.Request(
        url + "/functions/v1/" + fn, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + anon, "apikey": anon})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        findings.append(f"[{fn}] 응답 {e.code} — 배포 상태를 확인해 주세요")
        continue
    except Exception as e:
        findings.append(f"[{fn}] 연결 실패 — {str(e)[:70]}")
        continue
    if not d.get("ok"):
        notes.append(f"[{fn}] 는 상태 확인(ping)을 모르는 옛 판입니다 — 다시 배포하면 원인을 말해 줍니다")
        continue
    alive.append(fn)
    has_key.append(bool(d.get("hasKey")))
    served_models |= set(d.get("models") or [])

if names and not alive:
    findings.append("살아 있는 AI 프록시가 없습니다 — AI 회의록·AI 정리가 전부 멈춥니다")
elif alive and not any(has_key):
    findings.append("프록시는 살아 있지만 서버에 ANTHROPIC_API_KEY 가 없습니다 "
                    "— Supabase → Edge Functions → Secrets 에 넣어 주세요")
elif alive and not all(has_key):
    findings.append("일부 프록시에만 열쇠가 있습니다 — 없는 쪽으로 넘어가면 실패합니다: "
                    + ", ".join(f for f, k in zip(alive, has_key) if not k))

# 은퇴한 모델 이름을 쓰고 있지 않은지 — 앱과 서버 양쪽
RETIRED = {"claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-opus-4-1-20250805",
           "claude-3-7-sonnet-20250219", "claude-3-5-haiku-20241022", "claude-3-haiku-20240307",
           "claude-3-5-sonnet-20241022", "claude-3-opus-20240229"}
for mo in set(models) | served_models:
    if mo in RETIRED:
        findings.append(f"은퇴한 모델 이름을 쓰고 있습니다: {mo} — 호출이 전부 실패합니다")

if served_models and models and not (set(models) & served_models):
    notes.append("앱이 고른 모델(" + ", ".join(sorted(set(models))) +
                 ")과 서버가 허용한 모델(" + ", ".join(sorted(served_models)) +
                 ")이 겹치지 않습니다 — 서버 기본값으로 돌아갑니다")

notes.append(f"살아 있는 프록시 {len(alive)}/{len(names)}개" + (" · 열쇠 있음" if any(has_key) else ""))
notes.append("앱이 고른 모델: " + (", ".join(sorted(set(models))) or "(없음)"))

kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
lines = [f"### AI 준비 상태 {kst:%Y-%m-%d %H:%M} KST", ""]
lines += (["**살펴볼 것**", ""] + [f"- {x}" for x in findings] + [""]) if findings else ["이상 없음", ""]
lines += ["<details><summary>자세히</summary>", ""] + [f"- {n}" for n in notes] + ["", "</details>"]
open(os.path.join(HERE, "ai-report.md"), "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))

if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write("rc=%d\n" % (1 if findings else 0))
sys.exit(1 if findings else 0)
