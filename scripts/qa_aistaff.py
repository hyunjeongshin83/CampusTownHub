# -*- coding: utf-8 -*-
"""AI 직원 동석 · 바깥 회의(구글 밋·줌) 점검.

중요 — 실제 에이전트 통화는 켜지 않습니다. ElevenLabs 통화는 대표님 크레딧을 쓰고,
유료 사용은 사전 승인 사항입니다. 그래서
  · SDK 가 CDN 에서 실제로 내려오는지는 진짜로 확인하고
  · 통화 연결·기록 배선은 가짜 startSession 으로 확인합니다.
"""
import os, sys, json
from playwright.sync_api import sync_playwright

URL = os.environ.get("HUB_URL", "http://127.0.0.1:8099/index.html")
bad = []

SETUP = """
url => {
  state.user = {role:'operator', name:'신현정', email:'qa@example.invalid', id:'u1'};
  state.meetings = [{id:'mx', title:'점검 회의', date:'2026-11-13', time:'16:00',
                     zoom:url, attendees:[{name:'신현정'}], jobs:[]}];
  state.currentMeetingId = 'mx'; syncCurrentMeeting();
  state.meeting.started = null; state.segments = [];
  document.body.insertAdjacentHTML('beforeend',
    '<div id="extBox"></div><div id="vFrame"></div><div id="vAfter"></div>'
    + '<div id="vTranscript"></div><span id="vSegCount"></span><span id="vMicState"></span>'
    + '<input id="vTypeInput"><button id="vTypeAdd"></button><button id="vMicBtn"></button>'
    + '<select id="vMicWho"></select><span id="vMicHint"></span><button id="vKakao"></button>'
    + '<button id="vGuess"></button><button id="vClear"></button>'
    + '<div id="panelHost"></div>');
  document.getElementById('panelHost').innerHTML = aiStaffPanelHTML();
  extRenderBox();
  const n = document.getElementById('elHow'); if (n) n.innerHTML = elHowToHTML();
  return true;
}
"""

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 950})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:150]))
    print("AI 직원·바깥 회의 점검 — %s" % URL)
    pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)

    # ── 1. 회의 앱 알아보기 ──
    print("── 회의 앱 알아보기 ──")
    cases = [
        ("https://meet.google.com/wbw-mvep-fkf", "구글 밋", "탭 오디오"),
        ("https://zoom.us/j/12345678", "줌", "컴퓨터 소리"),
        ("https://us02web.zoom.us/j/999", "줌", "컴퓨터 소리"),
        ("https://teams.microsoft.com/l/meetup-join/x", "팀즈", "컴퓨터 소리"),
        ("https://example.com/room/9", "외부 회의", "소리"),
    ]
    for url, want, howWant in cases:
        r = pg.evaluate("""u => { const a = meetApp(u);
            return a ? {name:a.name, how:a.how.join(' / '), note:a.note} : null; }""", url)
        if not r:
            bad.append("%s 를 알아보지 못했습니다" % url)
            continue
        ok = r["name"] == want and howWant in r["how"]
        print("  %-42s → %s %s" % (url[:42], r["name"], "" if ok else "!! 기대 " + want))
        if r["name"] != want:
            bad.append("%s 를 %s 가 아니라 %s 로 봤습니다" % (url, want, r["name"]))
        if howWant not in r["how"]:
            bad.append("%s 안내에 「%s」 가 없습니다: %s" % (r["name"], howWant, r["how"][:90]))
    # 줌은 화면 없이 소리만 되는 길이 있어야 합니다 (2026-11-12 줌 문서 확인)
    z = pg.evaluate("() => meetApp('https://zoom.us/j/1')")
    if "고급" not in " ".join(z["how"]):
        bad.append("줌 안내에 「고급」 탭 경로가 없습니다 — 화면 없이 소리만 공유하는 길입니다")
    else:
        print("  줌: 고급 → 컴퓨터 소리 (화면 없이 소리만) 안내 있음")

    # ── 2. 화면 ──
    print("── 화면 ──")
    pg.evaluate(SETUP, "https://meet.google.com/wbw-mvep-fkf")
    pg.wait_for_timeout(500)
    shown = pg.evaluate("""() => {
        const t = document.body.innerText;
        return {ext: t.includes('바깥 회의'), app: t.includes('구글 밋'),
                ai: t.includes('AI 직원 동석'),
                how: (document.getElementById("elHow")||{}).textContent||"",
                btns: [...document.querySelectorAll('#extBox button, #elPanel button')]
                        .map(b => b.textContent.trim()),
                hearOff: !document.getElementById('elHear').checked};
    }""")
    print("  바깥 회의 칸 %s · 앱 이름 %s · AI 직원 칸 %s" % (shown["ext"], shown["app"], shown["ai"]))
    print("  단추: %s" % ", ".join(shown["btns"]))
    for k, nm in (("ext", "바깥 회의 칸"), ("app", "앱 이름"), ("ai", "AI 직원 칸")):
        if not shown[k]:
            bad.append("%s 이 화면에 없습니다" % nm)
    if "탭 오디오" not in shown["how"]:
        bad.append("구글 밋 회의인데 「탭 오디오 공유」 안내가 안 나옵니다: %r" % shown["how"][:90])
    else:
        print("  소리 공유 안내    → 구글 밋 기준으로 나옴")
    if not shown["hearOff"]:
        bad.append("「들은 말도 넣기」가 기본 켜져 있습니다 — 같은 말이 두 번 적힙니다")

    # ── 3. 기록 배선 (가짜 통화) ──
    print("── 기록 배선 (가짜 통화 · 크레딧 안 씀) ──")
    rec = pg.evaluate("""async () => {
        const got = [];
        window.ElevenLabsClient = { Conversation: { startSession: async o => {
            window.__opt = o;
            return {endSession: async () => { got.push('end'); }, output: null};
        }}};
        await elStart();
        const o = window.__opt;
        o.onStatusChange({status:'connected'});
        o.onMessage({source:'ai', message:'MedIT 는 복약 관리 플랫폼입니다.'});
        o.onMessage({source:'user', message:'데이터는 어떻게 주시나요'});
        document.getElementById('elHear').checked = true;
        o.onMessage({source:'user', message:'가명화 후 제공 가능합니다'});
        o.onModeChange({mode:'speaking'});
        return {agentId: o.agentId, conn: o.connectionType,
                segs: state.segments.map(s => [s.who, s.text.slice(0,18), !!s.auto]),
                mode: (document.getElementById('elMode')||{}).textContent,
                msg: (document.getElementById('elMsg')||{}).textContent,
                pipe: (document.getElementById('elPipe')||{}).innerText};
    }""")
    print("  에이전트 id        → %s" % rec["agentId"])
    print("  연결 방식          → %s" % rec["conn"])
    for s in rec["segs"]:
        print("  회의록 ← %-26s %s" % (s[0], s[1]))
    if rec["agentId"] != "agent_9601m77503f9fjgry14bv8rjgbpj":
        bad.append("에이전트 id 가 다릅니다: %s" % rec["agentId"])
    whos = [s[0] for s in rec["segs"]]
    if "AI 직원" not in whos:
        bad.append("AI 직원이 한 말이 회의록에 안 들어갔습니다: %s" % whos)
    if len(rec["segs"]) != 2:
        bad.append("회의록에 %d건 들어갔습니다 — 기본 2건(AI 발언 1 + 체크 후 들은 말 1)이어야 합니다: %s"
                   % (len(rec["segs"]), rec["segs"]))
    if not all(s[2] for s in rec["segs"]):
        bad.append("AI 직원 기록이 자동(auto) 표시가 안 됐습니다")
    if rec["mode"] != "말하는 중":
        bad.append("말하는 중 표시가 안 바뀝니다: %r" % rec["mode"])
    if "동석" not in rec["msg"]:
        bad.append("연결 상태 문구가 안 바뀝니다: %r" % rec["msg"])
    # 통화에 안 들어간 상태면 「이 컴퓨터에서만 들립니다」 안내가 나와야 합니다
    if "컴퓨터에서만" not in rec["pipe"]:
        bad.append("허브 통화 밖인데 목소리 전달 안내가 안 나옵니다: %r" % rec["pipe"][:90])
    else:
        print("  목소리 경로 안내   → 통화 밖이라 소리 공유 안내로 넘어감")

    # ── 4. 동의 없이는 녹취가 시작되지 않아야 합니다 ──
    print("── 동의 ──")
    pre = pg.evaluate("""() => {
        let opened = 0, popped = 0;
        window.formModalP = async () => { opened++; return false; };   // 「취소」
        window.open = () => { popped++; return null; };
        try { localStorage.removeItem(extConsentKey()); } catch(e) {}
        return extJoin().then(() => ({opened, popped, started: !!state.meeting.started}));
    }""")
    print("  동의 창 %d번 · 회의 창 %d번 · 시작됨 %s" % (pre["opened"], pre["popped"], pre["started"]))
    if not pre["opened"]:
        bad.append("녹취 전에 동의를 묻지 않습니다 — 남의 말을 기록하는 일입니다")
    if pre["popped"]:
        bad.append("동의를 취소했는데 회의 창을 열었습니다")
    if pre["started"]:
        bad.append("동의를 취소했는데 회의가 시작됐습니다")

    # ── 5. 터치 44px·대비 (폭 3종) ──
    print("── 터치 크기·대비 ──")
    for w, label in [(390, "휴대폰 390"), (768, "태블릿 768"), (1280, "데스크톱 1280")]:
        pg.set_viewport_size({"width": w, "height": 900})
        pg.wait_for_timeout(250)
        r = pg.evaluate(r"""() => {
            const L = c => { c = c.map(x => x/255).map(x => x <= 0.03928 ? x/12.92
                : Math.pow((x+0.055)/1.055, 2.4));
                return 0.2126*c[0] + 0.7152*c[1] + 0.0722*c[2]; };
            const P = s => (s.match(/[0-9.]+/g) || [0,0,0]).slice(0,3).map(Number);
            const R = (a,b) => { const x = L(P(a)), y = L(P(b));
                return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05); };
            const scope = [...document.querySelectorAll('#extBox button, #elPanel button, #elPanel label')];
            const small = scope.filter(e => { const r = e.getBoundingClientRect();
                return r.width > 0 && (r.height < 44 || r.width < 44); })
                .map(e => (e.textContent.trim().slice(0,14)) + ' '
                     + Math.round(e.getBoundingClientRect().width) + 'x'
                     + Math.round(e.getBoundingClientRect().height));
            const cons = [...document.querySelectorAll('#extBox button, #elPanel button')].map(b => {
                const g = getComputedStyle(b);
                const bg = g.backgroundColor.includes('rgba(0, 0, 0, 0)') ? 'rgb(255,255,255)' : g.backgroundColor;
                return [b.textContent.trim().slice(0,12), +R(g.color, bg).toFixed(2)]; });
            const mini = [...document.querySelectorAll('#extBox .mini, #elPanel .mini')].slice(0,5)
                .map(e => +R(getComputedStyle(e).color, 'rgb(255,255,255)').toFixed(2));
            return {small, cons, mini,
                    over: document.documentElement.scrollWidth > window.innerWidth + 2};
        }""")
        low = [c for c in r["cons"] if c[1] < 4.5] + [x for x in r["mini"] if x < 4.5]
        if r["small"]:
            bad.append("%s: 44px 못 미침 — %s" % (label, ", ".join(r["small"])))
        if r["over"]:
            bad.append("%s: 가로로 넘칩니다" % label)
        if low:
            bad.append("%s: 대비 4.5:1 못 미침 — %s" % (label, low))
        print("  %-14s 44px %s · 넘침 %s · 단추 %s · 작은 글자 %s"
              % (label, "OK" if not r["small"] else "실패", "없음" if not r["over"] else "있음",
                 " ".join("%.2f" % c[1] for c in r["cons"]),
                 " ".join("%.2f" % x for x in r["mini"])))
    pg.set_viewport_size({"width": 1280, "height": 950})

    # ── 5b. 회의록으로 올라간 문장은 녹취에서 빈칸 (v164) ──
    #   전에는 녹취가 모든 문장을, 회의록이 그중 올라간 것을 또 보여 줘서 같은 말이 두 번 보였습니다.
    print("── 녹취 중복 ──")
    dedup = pg.evaluate("""() => {
        document.body.insertAdjacentHTML('beforeend',
          '<div id="transcript"></div><div id="liveDoc"></div><span id="segCount"></span>');
        state.segments = [];
        for (let i = 1; i <= 5; i++) state.segments.push(
          {text:'문장'+i, who:'신현정', time:'10:0'+i});
        state.liveDoc = {paras:['앞 3문장을 정리한 문단입니다.'], cursor:3};   // 3문장이 회의록으로 올라감
        SHOW_ALL_SEGS = false;
        renderTranscript();
        const box = document.getElementById('transcript');
        const t = box.innerText;
        const before = [1,2,3].filter(i => t.includes('문장'+i)).length;
        const after  = [4,5].filter(i => t.includes('문장'+i)).length;
        // 모두 보기로 되돌아오는지
        toggleAllSegs({preventDefault(){}});
        const t2 = document.getElementById('transcript').innerText;
        const allBack = [1,2,3,4,5].every(i => t2.includes('문장'+i));
        SHOW_ALL_SEGS = false;
        // 전부 올라간 경우 — 빈칸이어야 합니다
        state.liveDoc = {paras:['전부 정리됨'], cursor:5};
        renderTranscript();
        const t3 = document.getElementById('transcript').innerText;
        const emptied = ![1,2,3,4,5].some(i => t3.includes('문장'+i));
        return {before, after, allBack, emptied, note: t3.trim().slice(0,60)};
    }""")
    print("  올라간 3문장 중 보이는 것 %d개 · 안 올라간 2문장 중 %d개"
          % (dedup["before"], dedup["after"]))
    print("  전부 올라갔을 때   → %s" % ("빈칸 + 안내" if dedup["emptied"] else "아직 보입니다"))
    print("  [모두 보기]        → %s" % ("되돌아옴" if dedup["allBack"] else "안 됨"))
    if dedup["before"]:
        bad.append("회의록으로 올라간 문장이 녹취에 아직 %d개 보입니다 — 같은 말이 두 번 나옵니다" % dedup["before"])
    if dedup["after"] != 2:
        bad.append("아직 안 올라간 문장이 녹취에서 사라졌습니다 (%d/2)" % dedup["after"])
    if not dedup["emptied"]:
        bad.append("전부 회의록으로 올라갔는데 녹취가 비지 않았습니다")
    if not dedup["allBack"]:
        bad.append("[모두 보기] 로 되돌려도 안 보입니다")
    if "회의록" not in dedup["note"]:
        bad.append("빈칸만 보이고 어디로 갔는지 안 적혀 있습니다: %r" % dedup["note"])

    # ── 5c. 꼬마 아이콘 (v164) ──
    print("── 꼬마 아이콘 ──")
    kid = pg.evaluate("""() => {
        // 머리글은 로그인 전에는 숨어 있습니다 — 보이게 한 뒤 재야 뜻이 있습니다
        const app = document.getElementById('appMain');
        if (app) app.style.display = '';
        const gate = document.getElementById('gate'); if (gate) gate.style.display = 'none';
        const b = document.getElementById('kidBtn');
        if (!b) return {none:true};
        const r = b.getBoundingClientRect();
        const svg = b.querySelector('svg');
        return {w: Math.round(r.width), h: Math.round(r.height),
                title: b.getAttribute('title') || '',
                label: b.getAttribute('aria-label') || '',
                circles: svg ? svg.querySelectorAll('circle').length : 0,
                clickable: typeof window.kidClick === 'function'};
    }""")
    if kid.get("none"):
        bad.append("꼬마 아이콘(#kidBtn)이 머리글에 없습니다")
    else:
        print("  %dx%d · 곱슬 원 %d개 · 누름 %s" % (kid["w"], kid["h"], kid["circles"], kid["clickable"]))
        if kid["h"] < 44 or kid["w"] < 44:
            bad.append("꼬마 아이콘이 44px 못 미칩니다 (%dx%d)" % (kid["w"], kid["h"]))
        if not kid["label"]:
            bad.append("꼬마 아이콘에 이름(aria-label)이 없습니다 — 화면 읽어 주는 분이 못 씁니다")
        if not kid["clickable"]:
            bad.append("꼬마 아이콘을 눌러도 아무 일이 없습니다")
        if kid["circles"] < 9:
            bad.append("곱슬머리 원이 %d개뿐입니다 — 파마머리로 안 보입니다" % kid["circles"])

    # ── 6. 진짜 SDK 가 내려오는지 (통화는 안 켭니다) ──
    print("── SDK 내려받기 (통화 안 켬) ──")
    sdk = pg.evaluate("""async () => {
        delete window.ElevenLabsClient; delete window.ElevenLabs;
        try { await elLoad(); }
        catch (e) { return {ok:false, why:e.message}; }
        const C = elNS() && elNS().Conversation;
        return {ok: !!C, start: typeof (C && C.startSession)};
    }""")
    print("  @elevenlabs/client → %s (startSession: %s)"
          % ("받았습니다" if sdk.get("ok") else "실패: " + str(sdk.get("why")), sdk.get("start")))
    if not sdk.get("ok"):
        bad.append("AI 직원 SDK 를 받지 못합니다: %s" % sdk.get("why"))
    if sdk.get("start") != "function":
        bad.append("SDK 에 startSession 이 없습니다 — 판이 바뀐 것 같습니다 (%s)" % sdk.get("start"))

    if errs:
        real = [e for e in errs if "elevenlabs" not in e.lower()]
        if real:
            bad.append("자바스크립트 오류: " + " / ".join(real[:2]))
    ctx.close(); b.close()

print()
if bad:
    print("고칠 것 %d개" % len(bad))
    for x in bad: print("  · " + x)
    sys.exit(1)
print("AI 직원·바깥 회의: 기록 배선·동의·앱별 소리 경로가 다 맞습니다")
