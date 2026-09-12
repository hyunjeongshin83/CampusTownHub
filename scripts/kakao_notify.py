# -*- coding: utf-8 -*-
"""이상 발생 시 카카오톡 '나에게 보내기'로 알린다.

필요한 저장소 시크릿 (둘 다 없으면 조용히 건너뛴다):
  KAKAO_REST_KEY       카카오 앱의 REST API 키
  KAKAO_REFRESH_TOKEN  talk_message 동의를 받은 리프레시 토큰
"""
import os, json, sys, urllib.parse, urllib.request, urllib.error

REST = os.environ.get("KAKAO_REST_KEY", "").strip()
REFRESH = os.environ.get("KAKAO_REFRESH_TOKEN", "").strip()
SITE = os.environ.get("SITE", "").rstrip("/")
ISSUE = os.environ.get("ISSUE_URL", "").strip()

if not REST or not REFRESH:
    print("카카오 시크릿 미설정 — 알림을 건너뜁니다 (KAKAO_REST_KEY / KAKAO_REFRESH_TOKEN)")
    sys.exit(0)

def post(url, data, headers=None):
    body = urllib.parse.urlencode(data).encode()
    h = {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")

# 1) 리프레시 토큰 → 액세스 토큰
st, tok = post("https://kauth.kakao.com/oauth/token", {
    "grant_type": "refresh_token", "client_id": REST, "refresh_token": REFRESH})
if st != 200 or "access_token" not in tok:
    print(f"토큰 갱신 실패 ({st}): {tok}")
    sys.exit(0)                      # 알림 실패로 워크플로를 깨뜨리지 않는다
if tok.get("refresh_token"):
    print("::warning::카카오가 새 리프레시 토큰을 발급했습니다. "
          "KAKAO_REFRESH_TOKEN 시크릿을 갱신해 주세요 (미갱신 시 약 2개월 뒤 알림이 멈춥니다).")

# 2) 점검 결과 요약
try:
    report = open("watch-report.md", encoding="utf-8").read()
except Exception:
    report = ""
problems = [l.lstrip("- ").strip() for l in report.splitlines()
            if l.startswith("- ") and "<" not in l]
head = "[캠퍼스타운 허브] 자동점검 이상 감지"
lines = [head, ""]
for p in problems[:4]:
    lines.append("· " + p)
if ISSUE:
    lines += ["", "이슈: " + ISSUE]
lines += ["", "사이트: " + SITE.replace("https://", "")]
text = "\n".join(lines)[:190]          # 카카오 텍스트 템플릿 상한

# 3) 나에게 보내기
st, res = post("https://kapi.kakao.com/v2/api/talk/memo/default/send",
    {"template_object": json.dumps({
        "object_type": "text", "text": text,
        "link": {"web_url": ISSUE or SITE, "mobile_web_url": ISSUE or SITE},
        "button_title": "확인하기"}, ensure_ascii=False)},
    {"Authorization": "Bearer " + tok["access_token"]})
print(("카톡 발송 성공" if st == 200 else f"카톡 발송 실패 ({st}): {res}"))
