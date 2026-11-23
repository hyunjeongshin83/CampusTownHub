# -*- coding: utf-8 -*-
"""참석자별 메일 모음 QA (v170).

회의 기록은 참석자 모두가 봅니다. 그래서 이 기능에서 제일 중요한 것은
「승인하지 않은 것은 어떤 경로로도 기록에 올라가지 않는다」입니다.
압축은 AI 가 하므로 스텁으로 대신하고, 거르는 쪽(연락처·날짜 없음·중복)과
승인 상태 기계는 제품이 그린 DOM·state 로 확인합니다.
"""
import sys, os, json
from playwright.sync_api import sync_playwright

SITE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
    "HUB_URL", "https://hyunjeongshin83.github.io/CampusTownHub/index.html")
bad = []

# AI 가 돌려줄 법한 것 — 일부러 더럽게 만들어 둡니다.
# 1·2번은 멀쩡, 3번은 이메일 주소가 섞임, 4번은 전화번호, 5번은 날짜 없음, 6번은 1번과 중복.
FAKE = json.dumps([
    {"date": "2026-11-12", "dir": "받음", "subject": "1차 미팅 정리",
     "gist": "병원 측은 주제가 정해지기 전에는 데이터를 내어줄 수 없다는 입장"},
    {"date": "2026-11-14", "dir": "보냄", "subject": "주제 회신",
     "gist": "MedIT 가 연구 주제를 한 장으로 정리해 보내기로 함"},
    {"date": "2026-11-15", "dir": "받음", "subject": "연락처",
     "gist": "회신은 manager@rndcircle.io 로 달라고 함"},
    {"date": "2026-11-16", "dir": "받음", "subject": "전화",
     "gist": "급하면 010-1234-5678 로 연락 달라고 함"},
    {"date": "", "dir": "받음", "subject": "날짜없음", "gist": "언젠가 회신하겠다고 함"},
    {"date": "2026-11-12", "dir": "받음", "subject": "중복",
     "gist": "병원 측은 주제가 정해지기 전에는 데이터를 내어줄 수 없다는 입장"},
], ensure_ascii=False)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(ignore_https_errors=True)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(SITE, wait_until="networkidle", timeout=90000)
    pg.wait_for_timeout(3000)
    print("BUILD", pg.evaluate("BUILD"), "· 로드 오류", errs or "없음", "\n")

    # ── 1. 압축이 무엇을 담고 무엇을 버리는가 ──
    print("── 압축해서 담기 ──")
    r = pg.evaluate("""async (fake) => {
        window.callClaude = async () => fake;
        state.mails = {};
        const r = await mailDigest('Manager@RnDcircle.IO ', '메일 원문'.repeat(20));
        const L = state.mails['manager@rndcircle.io'] || [];
        return {added: r.added, dropped: r.dropped, n: L.length,
                dates: L.map(x => x.date),
                approved: L.map(x => x.approved),
                gists: L.map(x => x.gist).join(' || ')};
    }""", FAKE)
    print("  담김 %d건 · 버림 %d건" % (r["added"], r["dropped"]))
    print("  날짜 순서 → %s" % r["dates"])
    print("  승인 상태 → %s" % r["approved"])
    if r["added"] != 2:
        bad.append("담긴 건수가 2가 아닙니다 (%d) — 연락처·날짜없음·중복이 걸러져야 합니다" % r["added"])
    if "@" in r["gists"]:
        bad.append("이메일 주소가 섞인 줄이 담겼습니다: %s" % r["gists"])
    if "010-" in r["gists"]:
        bad.append("전화번호가 섞인 줄이 담겼습니다: %s" % r["gists"])
    if r["dates"] != sorted(r["dates"]):
        bad.append("날짜순으로 정렬되지 않았습니다: %s" % r["dates"])
    if any(a is not None for a in r["approved"]):
        bad.append("담자마자 승인/미승인이 정해져 있습니다 — 기본은 대기여야 합니다: %s" % r["approved"])

    # ── 2. 승인하지 않은 것은 기록에 올라가면 안 된다 ──
    print("── 승인 안 한 것은 안 올라가야 합니다 ──")
    g = pg.evaluate("""async () => {
        state.notes = {};
        state.attendees = [{name:'알앤디써클', email:'manager@rndcircle.io'}];
        state.meetings = [{id:'mm1', title:'QA 메일 회의', attendees:state.attendees}];
        state.meeting = state.meetings[0];
        window.toast = () => {};
        window.scheduleSave = () => {};
        await mailsToNotes('manager@rndcircle.io');     // 아직 아무것도 승인 안 함
        return {notes: JSON.stringify(state.notes)};
    }""")
    print("  승인 0건으로 눌렀을 때 기록 → %s" % g["notes"])
    if "rndcircle" in g["notes"] or "병원" in g["notes"]:
        bad.append("승인하지 않았는데 기록에 들어갔습니다: %s" % g["notes"])

    # ── 3. 승인한 것만 올라가는가 ──
    one = pg.evaluate("""async () => {
        const L = state.mails['manager@rndcircle.io'];
        await mailSetApproved('manager@rndcircle.io', L[0].id, true);   // 첫째만 승인
        await mailSetApproved('manager@rndcircle.io', L[1].id, false);  // 둘째는 미승인
        await mailsToNotes('manager@rndcircle.io');
        const t = String((state.notes||{}).mails||'');
        return {text: t, has0: t.indexOf(L[0].gist) >= 0, has1: t.indexOf(L[1].gist) >= 0,
                counts: mailCounts('manager@rndcircle.io')};
    }""")
    print("  승인 1 · 미승인 1 → 기록에 담긴 것:")
    for ln in [l for l in one["text"].split("\n") if l.strip()]:
        print("     %s" % ln)
    print("  집계 → %s" % one["counts"])
    if not one["has0"]:
        bad.append("승인한 줄이 기록에 없습니다")
    if one["has1"]:
        bad.append("미승인한 줄이 기록에 올라갔습니다 — 가장 큰 문제입니다")
    if one["counts"]["ok"] != 1 or one["counts"]["no"] != 1 or one["counts"]["wait"] != 0:
        bad.append("승인 집계가 틀립니다: %s" % one["counts"])

    # ── 4. 같은 단추를 다시 누르면 대기로 돌아가는가 ──
    tog = pg.evaluate("""async () => {
        const L = state.mails['manager@rndcircle.io'];
        await mailSetApproved('manager@rndcircle.io', L[0].id, true);   // 승인 → 다시 승인 = 해제
        return {after: L[0].approved, counts: mailCounts('manager@rndcircle.io')};
    }""")
    print("  승인된 것을 다시 누름 → %s" % ("대기로 돌아감" if tog["after"] is None else tog["after"]))
    if tog["after"] is not None:
        bad.append("승인을 취소할 수 없습니다 (%s)" % tog["after"])

    # ── 5. 두 번 담아도 중복이 쌓이지 않는가 ──
    dup = pg.evaluate("""async (fake) => {
        window.callClaude = async () => fake;
        const before = state.mails['manager@rndcircle.io'].length;
        const r = await mailDigest('manager@rndcircle.io', '메일 원문'.repeat(20));
        return {before, after: state.mails['manager@rndcircle.io'].length, added: r.added};
    }""", FAKE)
    print("  같은 메일을 또 담기 → %d건 → %d건 (새로 담김 %d)" % (dup["before"], dup["after"], dup["added"]))
    if dup["after"] != dup["before"]:
        bad.append("같은 메일을 또 담으면 줄이 늘어납니다 (%d → %d)" % (dup["before"], dup["after"]))

    # ── 6. 화면에 그려지는가 · 44px ──
    print("── 화면 ──")
    for w, label in ((390, "휴대폰 390"), (768, "태블릿 768"), (1280, "데스크톱 1280")):
        pg.set_viewport_size({"width": w, "height": 900})
        v = pg.evaluate("""() => {
            document.body.insertAdjacentHTML('beforeend', '<div id="atList"></div>');
            MAIL_OPEN = 'manager@rndcircle.io';
            renderAtList();
            const small = [...document.querySelectorAll('#mailPanel button')]
                .filter(b => { const r = b.getBoundingClientRect();
                               return r.width > 0 && (r.height < 44 || r.width < 44); })
                .map(b => b.textContent.trim() + ':' + Math.round(b.getBoundingClientRect().width)
                          + 'x' + Math.round(b.getBoundingClientRect().height));
            const chip = document.querySelector('.chip .mailb');
            const panel = document.getElementById('mailPanel');
            const over = document.documentElement.scrollWidth > document.documentElement.clientWidth;
            const host = document.getElementById('atList');
            if (host) host.remove();
            return {panel: !!panel, chip: chip ? chip.textContent.trim() : '없음', small, over};
        }""")
        print("  %-14s 패널 %s · 칩 %r · 44px %s · 가로넘침 %s"
              % (label, "있음" if v["panel"] else "없음", v["chip"],
                 "OK" if not v["small"] else v["small"], "있음" if v["over"] else "없음"))
        if not v["panel"]:
            bad.append("%s: 메일 패널이 안 그려집니다" % label)
        if v["small"]:
            bad.append("%s: 메일 패널 단추가 44px 못 미침 — %s" % (label, v["small"]))
        if v["over"]:
            bad.append("%s: 메일 패널에서 가로 스크롤이 생깁니다" % label)
        if v["chip"] == "없음":
            bad.append("%s: 참석자 칩에 메일 배지가 없습니다" % label)

    b.close()

print()
if bad:
    print("고칠 것 %d개" % len(bad))
    for x in bad:
        print("  · %s" % x)
    sys.exit(1)
print("메일 모음: 승인한 것만 올라가고, 연락처는 걸러지고, 중복도 안 쌓입니다")
