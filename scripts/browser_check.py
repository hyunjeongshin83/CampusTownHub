# -*- coding: utf-8 -*-
"""Playwright로 실제 브라우저에서 허브를 열어 렌더링·콘솔 오류를 점검한다."""
import os, sys, json, datetime
from playwright.sync_api import sync_playwright

SITE = os.environ.get("SITE", "").rstrip("/")
problems, notes = [], []

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 900},
                    ignore_https_errors=bool(os.environ.get("IGNORE_CERT")))
    errs, console = [], []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: console.append(m.text) if m.type == "error" else None)

    pg.goto(SITE + "/index.html?ci=1", wait_until="networkidle", timeout=60000)
    pg.wait_for_timeout(6000)          # 부트·가드·자동점검이 도는 시간

    text = pg.inner_text("body")
    notes.append(f"렌더 글자수 {len(text):,}")
    if len(text) < 150:
        problems.append(f"화면이 비어 있습니다 (글자수 {len(text)})")
    if "로그인" not in text and "회의" not in text:
        problems.append("로그인 화면도 회의 목록도 렌더되지 않았습니다")

    build = pg.evaluate("typeof BUILD!=='undefined' ? String(BUILD) : ''")
    notes.append(f"실행된 BUILD {build or '확인 실패'}")
    if not build:
        problems.append("BUILD 전역이 없습니다 — 스크립트가 끝까지 실행되지 못했습니다")

    for fn in ["loadAll", "saveSession", "canView", "accessGuard", "forceResync",
               "mergeSave", "merge3Array", "refreshSbToken", "diagStatus", "opsPanel"]:
        if pg.evaluate(f"typeof {fn}") != "function":
            problems.append(f"함수 누락: {fn}")
    notes.append("핵심 함수 10종 정의 확인")

    if not pg.evaluate("!!document.getElementById('authArea')"):
        problems.append("로그인 영역(authArea)이 없습니다")
    if not pg.evaluate("!!document.getElementById('opsBtn')"):
        problems.append("운영 버튼(opsBtn)이 생성되지 않았습니다")

    bdate = pg.evaluate("typeof BUILD_DATE!=='undefined' ? BUILD_DATE : ''")
    notes.append(f"빌드 표기 v{build} ({bdate or '날짜 없음'})")
    if bdate and bdate < "2026-09-01":
        problems.append(f"BUILD_DATE가 낡았습니다: {bdate}")

    if errs:
        problems.append("스크립트 오류 " + str(len(errs)) + "건: " + " | ".join(errs[:3])[:300])
    else:
        notes.append("스크립트 오류 없음")
    real = [c for c in console if "favicon" not in c.lower() and "401" not in c]
    if real:
        notes.append("콘솔 경고 " + str(len(real)) + "건: " + real[0][:120])

    # 복구 도구도 실제로 열어본다
    pg.goto(SITE + "/recover.html?ci=1", wait_until="networkidle", timeout=45000)
    pg.wait_for_timeout(3000)
    rt = pg.inner_text("body")
    notes.append(f"복구 도구 렌더 {len(rt):,}자")
    if "서버 BUILD" not in rt:
        problems.append("복구 도구가 배포 상태를 표시하지 못했습니다")

    pg.screenshot(path="hub.png", full_page=False)
    b.close()

kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
lines = [f"### 브라우저 점검 {kst:%Y-%m-%d %H:%M} KST", ""]
lines += (["**확인이 필요합니다**", ""] + [f"- {x}" for x in problems] + [""]) if problems else ["이상 없음", ""]
lines += ["<details><summary>점검 내역</summary>", ""] + [f"- {n}" for n in notes] + ["", "</details>"]
open("browser-report.md", "w", encoding="utf-8").write("\n".join(lines))
with open(os.environ["GITHUB_OUTPUT"], "a") as f:
    f.write("bstatus=" + ("ok" if not problems else "ng") + "\n")
print("\n".join(lines))
