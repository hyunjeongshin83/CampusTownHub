# -*- coding: utf-8 -*-
"""보고서 서식 점검 — AI 보고서가 읽을 수 있는 모양으로 그려지는지.

2026-10-19 대표님: 「보고서를 조금 더 보기 쉽게 작성해줄 수 있나요」
그때 mdToHtml 은 제목과 「· 」만 그려서, 표를 써도 파이프 문자가 그대로 보이고
긴 보고서는 글자 벽이 됐습니다.

표·굵게·우선순위 칩·강조 상자가 실제로 그려지는지 매번 확인합니다 —
렌더러가 조용히 退化하면 보고서가 다시 글자 벽이 됩니다.
"""
import os, sys, functools, pathlib
print = functools.partial(print, flush=True)
from playwright.sync_api import sync_playwright

SAMPLE = """# MedIT × 약학대학 — 고령화 Age-Tech 1회 회의 보고서

## 한눈에

| | |
|---|---|
| 결정된 방향 | 의사·약사의 판단 영역은 넘지 않고, 디지털 리터러시를 보조하는 **서포트 도구**로 범위를 정함 |
| 서비스의 핵심 | 제형 추천과 **개인 맞춤화**로 차별화해 약국의 빠른 도입을 유도 |
| 데이터의 벽 | 병원별 표준화가 각각이고 기관 간 교류가 막혀 있음 |
| 가장 급한 다음 일 | 약학정보원 이미지 데이터의 활용 가능 범위 확인 |

## 개요

백신 접종 앱의 국내·해외 사례를 비교해 최적 모델과 요구사항을 도출했다. 상용화를 전제로 사용성과 유효성을 점검했다. 데이터 출처와 법적 검토가 최대 제약으로 확인됐다.

## 0. 논의의 큰 그림

범위와 경계를 먼저 합의했다.

- 상용화 전제의 개발 — 의료인의 상호작용을 **보완**하는 기술
- 약사 방문 시 복약지도료·검사·처치로 이어질 때 수가가 발생

> 의사·약사의 판단 범주는 넘어오지 않도록 한다. 서포트(디지털 리터러시) 수준까지.

## 2. 데이터

출처와 벽을 네 축으로 정리했다.

| 축 | 내용 |
|---|---|
| 출처 | 건강검진 센터, 병원, 약학정보원, 신평원, 온누리·휴베이스 |
| 모이는 곳 | 의약품안전관리원 (개인 매칭 없음) |
| 표준화의 벽 | 고려대·연세대·서울대가 **각각** 표준화 사업을 함 |
| 스스로 만들기 | 랜덤 데이터·패턴 추출 연구로 자체 생성 |

## 3. 법률 검토

| 쟁점 | 왜 걸리는가 | 확인할 곳 |
|---|---|---|
| [최우선] 데이터로 영업 | 병원 지적자산이라 수익 창출에 동의가 필요 | 병원 산학협력단 |
| [높음] 조제 허가 범위 | **정제만** 가능, 액제 제외 | 식약처 위탁사업 기준 |
| [보통] 외국인 약 판매 | 보험료·인증 체계가 다름 | 건강보험심사평가원 |

## 5. 다음 할 일

| 우선순위 | 할 일 | 왜 | 누가·어디 |
|---|---|---|---|
| [최우선] | 약학정보원 이미지 데이터 활용 범위 확인 | 색깔 대조표 기능의 전제 | 약학정보원 |
| [높음] | 신평원 기관 프로젝트 제안 준비 | 11~12월 일정 | MedIT |
| [보통] | 고령 친화 약국·경로당 조사 | 용산구 대한노인회 연계 | MedIT |

## 더 알아볼 것

- 네이버 헬스케어 백데이터를 연구용으로 받을 수 있는가
- 병원 간 데이터 교류 불가(성모 → 중앙의료원)를 우회할 합법적 경로가 있는가
"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 900, "height": 1200})
    errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)[:150]))
    pg.goto((os.environ.get("SITE") or "http://localhost:8099").rstrip("/")+"/index.html?ci=1", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(4000)

    pg.evaluate("""(sample)=>{
      state.user={role:'operator',name:'QA',email:'qa@example.invalid',id:'q'};
      state.records=[{id:'rr1',title:'MedIT × 약학대학 (2026.07.10) — 고령화 Age-Tech',
        dt:'2026. 7. 14. 오후 4:18:33', place:'', attendees:[{name:'ㄱ'},{name:'ㄴ'},{name:'ㄷ'}],
        report:sample, reportAt:'2026. 10. 19. 오후 3:40'}];
      showReport('rr1');
    }""", SAMPLE)
    pg.wait_for_timeout(1200)

    info = pg.evaluate("""()=>{
      const m=document.getElementById('reportModal'); if(!m) return null;
      return {tables:m.querySelectorAll('table').length,
              chips:[...m.querySelectorAll('span')].filter(s=>/최우선|높음|보통/.test(s.textContent)&&s.style.borderRadius).length,
              bold:m.querySelectorAll('b').length,
              quote:[...m.querySelectorAll('div')].filter(d=>d.style.borderLeft).length,
              text:(m.innerText||'').length};
    }""")
    print("표", info and info["tables"], "· 우선순위 칩", info and info["chips"],
          "· 굵게", info and info["bold"], "· 강조상자", info and info["quote"])
    if not info: sys.exit("보고서 창이 안 떴습니다")
    bad=[]
    if info["tables"] < 4: bad.append(f"표가 {info['tables']}개만 그려졌습니다 (4개여야)")
    if info["chips"] < 5: bad.append(f"우선순위 칩이 {info['chips']}개입니다 (6개여야)")
    if info["bold"] < 4: bad.append(f"굵게가 {info['bold']}개입니다")
    if info["quote"] < 1: bad.append("강조 상자가 안 그려졌습니다")

    try:
        pg.locator("#reportModal > div").screenshot(path="report-sample.png")
    except Exception:
        pass
    if errs: bad.append("스크립트 오류: "+errs[0])
    b.close()

import datetime
kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
lines = [f"### 보고서 서식 점검 {kst:%Y-%m-%d %H:%M} KST", ""]
lines += (["**살펴볼 것**", ""] + [f"- {x}" for x in bad] + [""]) if bad else ["이상 없음", ""]
lines += ["<details><summary>그려진 것</summary>", "",
          f"- 표 {info['tables']}개 · 우선순위 칩 {info['chips']}개 · 굵게 {info['bold']}개 · 강조 상자 {info['quote']}개",
          "", "</details>"]
open("report-format.md","w",encoding="utf-8").write("\n".join(lines))
print()
print("\n".join(lines))
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write("rc=%d\n" % (1 if bad else 0))
sys.exit(1 if bad else 0)
