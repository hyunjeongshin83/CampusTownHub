# -*- coding: utf-8 -*-
"""역할별 QA — 임의 생성 계정 4명으로 실제 화면을 그려 검사한다.

원칙
  · 실존 인물의 이름·이메일을 쓰지 않는다. 매 실행마다 새로 만든다.
  · 도메인은 .invalid (RFC 2606) — 실수로 메일이 나갈 수 없다.
  · 권한 판정식을 테스트에 복사하지 않는다. 제품이 그린 DOM만 본다.
    (복사하면 제품이 망가져도 테스트는 통과한다 — 실제로 그런 적이 있다)

변종 검증: 수정 3건을 하나씩 되돌린 변종에서 모두 실패하는 것을 확인했다.
"""
import sys, os, uuid
from playwright.sync_api import sync_playwright
SITE=sys.argv[1] if len(sys.argv)>1 else os.environ.get("SITE","https://hyunjeongshin83.github.io/CampusTownHub")+"/index.html"
S=uuid.uuid4().hex[:6]
HOST={"role":"host","name":f"큐에이개최자{S}","email":f"qa-host-{S}@qa.invalid","id":f"qa1-{S}"}
ATT ={"role":"guest","name":f"큐에이참석{S}","email":f"qa-att-{S}@qa.invalid","id":f"qa2-{S}"}
OUT ={"role":"guest","name":f"큐에이외부{S}","email":f"qa-out-{S}@qa.invalid","id":f"qa3-{S}"}
OPS ={"role":"operator","name":f"큐에이운영{S}","email":f"qa-ops-{S}@qa.invalid","id":f"qa4-{S}"}
MS=[
 {"id":f"qam1-{S}","title":"QA 회의 A 개최자소유","host":HOST["name"],"date":"2026-11-01","time":"10:00","company":f"큐에이컴퍼니{S}",
  "attendees":[{"name":HOST["name"],"email":HOST["email"]},{"name":ATT["name"],"email":ATT["email"]}]},
 {"id":f"qam2-{S}","title":"QA 회의 B 타인소유","host":f"다른개최자{S}","date":"2026-11-02","time":"11:00","company":f"큐에이컴퍼니{S}",
  "attendees":[{"name":HOST["name"],"email":HOST["email"]}]},
 {"id":f"qam3-{S}","title":"QA 회의 C 옛문자열","host":HOST["name"],"date":"2026-11-03","time":"12:00","company":f"큐에이컴퍼니{S}",
  "attendees":[ATT["email"]]},
]
ok=ng=0; fails=[]
def t(n,g,w):
    global ok,ng
    p=(g==w); ok+=p; ng+=(not p)
    print(("PASS  " if p else "FAIL  ")+n+f"   got={g} want={w}")
    if not p: fails.append(n)

with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(ignore_https_errors=True)
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(SITE, wait_until="networkidle", timeout=60000); pg.wait_for_timeout(3000)
    print("BUILD", pg.evaluate("BUILD"), "· 로드 오류", errs or "없음", "\n")

    def render(u):
        """실제 렌더러를 호출하고 DOM에서 결과를 읽는다"""
        return pg.evaluate("""([u,ms])=>{
            state.user=u; state.meetings=ms; state.accounts=state.accounts||[];
            if(typeof CURRENT_CONN!=="undefined") CURRENT_CONN=null;
            // 커넥션을 앱의 그룹 키로 직접 선택한 뒤 회의 목록을 그린다
            const vis=ms.filter(canView);
            const gs=(typeof connGroups==="function")?connGroups(vis):[];
            CURRENT_CONN = gs.length? gs[0].key : null;
            showMeetingList();
            const cards=[...document.querySelectorAll('.mcard2')];
            return cards.map(c=>({
              title:(c.querySelector('h4')||{}).textContent||'',
              edit: !!c.querySelector('.mc-edit'),
              del:  !!c.querySelector('.mc-del'),
              enter:!!c.querySelector('.mc-enter')
            })).filter(x=>x.title.indexOf('QA 회의')===0);
        }""",[u,MS])

    r=render(HOST)
    t("개최자: 초대된 회의 3건 보임", len(r), 3)
    byT={x["title"]:x for x in r}
    t("개최자: 자기 회의 A 에 [수정] 있음", byT.get("QA 회의 A 개최자소유",{}).get("edit"), True)
    t("개최자: 자기 회의 A 에 [삭제] 있음", byT.get("QA 회의 A 개최자소유",{}).get("del"), True)
    t("개최자: 남의 회의 B 에 [수정] 없음", byT.get("QA 회의 B 타인소유",{}).get("edit"), False)
    t("개최자: 남의 회의 B 에 [삭제] 없음", byT.get("QA 회의 B 타인소유",{}).get("del"), False)
    t("개최자: 모든 카드에 [입장] 있음", all(x["enter"] for x in r), True)

    r=render(ATT)
    t("참석자: A·C 2건 보임", len(r), 2)
    t("참석자: 옛 문자열 회의 C 보임", any(x["title"]=="QA 회의 C 옛문자열" for x in r), True)
    t("참석자: [수정] 버튼 없음", any(x["edit"] for x in r), False)
    t("참석자: [삭제] 버튼 없음", any(x["del"] for x in r), False)

    r=render(OUT)
    t("미초대: 0건", len(r), 0)

    r=render(OPS)
    t("운영자: 전체 3건", len(r), 3)
    t("운영자: 전체 [수정] 가능", all(x["edit"] for x in r), True)

    g=pg.evaluate("""([u,ms])=>{state.meetings=ms;
        state.accounts=[{id:'noemail',name:'이메일없음',role:'guest'}];
        try{ return {ok:true, r:invitedRole(u.email)}; }catch(e){ return {ok:false, err:e.message}; }}""",[ATT,MS])
    t("이메일 없는 계정 섞여도 로그인 판정 동작", g["ok"], True)
    if g["ok"]: t("초대된 QA 참석자 → guest", g["r"], "guest")

    t("렌더 중 스크립트 오류 없음", len(errs), 0)
    print(f"\n{ok} PASS / {ng} FAIL")
    for f in fails: print("  실패:", f)
    b.close()
sys.exit(1 if ng else 0)
