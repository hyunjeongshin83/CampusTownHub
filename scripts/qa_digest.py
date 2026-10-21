# -*- coding: utf-8 -*-
"""자료 「한 장 보기」가 실제로 문서를 접어 주는지 봅니다.

실험 코드·내용·결과가 섞인 긴 문서(MD · Word)를 넣고 이것들을 봅니다.
  · Word(.docx) 를 뜯어 제목·표·그림까지 읽어 내는가
  · 코드 울타리·표·숫자·그림을 각각 제대로 떼어 내는가
  · 문서 안에 박힌 그림만 그리고, 바깥 주소 그림은 링크로만 두는가 (연구 자료 추적 방지)
  · 화면에 그림·숫자·표·코드·원문이 다 나오는가

AI 는 부르지 않습니다 — 요금이 들고, 접는 부분(파싱·화면)이 이 점검의 대상입니다.
AI 가 막혀도 그림·숫자·원문이 보여야 하므로 그 상태를 그대로 점검합니다.
"""
import os, sys, json, base64, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIX = ROOT / "scripts" / "fixtures"
URL = os.environ.get("HUB_URL", "http://127.0.0.1:8099/index.html")
bad = []


def main():
    md = (FIX / "experiment.md").read_text(encoding="utf-8")
    docx_b64 = base64.b64encode((FIX / "report.docx").read_bytes()).decode()

    print("한 장 보기 점검 — %s" % URL)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(URL, wait_until="load")
        pg.wait_for_timeout(1500)

        # ── 1. MD 쪼개기 ──
        print("── MD 쪼개기 ──")
        d = pg.evaluate("md => { const x = splitDoc(md); return {title:x.title, imgs:x.imgs.length,"
                        "links:x.links.length, codes:x.codes.map(c=>c.lang), tables:x.tables.length,"
                        "facts:x.facts.length, body:x.body.length,"
                        "imgok:x.imgs.every(g=>/^data:image\\//.test(g.src))}; }", md)
        print("  제목: %s" % d["title"])
        print("  그림 %d장 · 바깥 링크 %d개 · 코드 %s · 표 %d개 · 숫자줄 %d줄"
              % (d["imgs"], d["links"], d["codes"], d["tables"], d["facts"]))
        if "MDX-114" not in d["title"]:
            bad.append("제목을 못 뽑았습니다: %r" % d["title"])
        if d["imgs"] != 2:
            bad.append("박힌 그림은 2장인데 %d장으로 읽었습니다" % d["imgs"])
        if d["links"] != 1:
            bad.append("바깥 주소 그림은 1개인데 %d개로 읽었습니다" % d["links"])
        if sorted(d["codes"]) != ["python", "r"]:
            bad.append("코드 울타리를 python·r 로 못 읽었습니다: %s" % d["codes"])
        if d["tables"] != 1:
            bad.append("표는 1개인데 %d개로 읽었습니다" % d["tables"])
        if d["facts"] < 5:
            bad.append("숫자가 든 줄을 %d줄만 뽑았습니다 — 결과를 놓치고 있습니다" % d["facts"])
        if not d["imgok"]:
            bad.append("그림 목록에 data:image 가 아닌 것이 섞였습니다")
        # base64 가 본문에 남아 글자 벽이 되지 않았는지
        if d["body"] > 6000:
            bad.append("본문에 그림 데이터가 남아 있습니다 (%d자) — 요약이 흐려집니다" % d["body"])
        else:
            print("  본문 %d자 (그림 데이터는 빠졌습니다)" % d["body"])

        # ── 2. AI 에게 보낼 글에 base64 가 섞이지 않았는지 ──
        pr = pg.evaluate("md => { const x = splitDoc(md); return digestPrompt(x); }", md)
        if "base64" in pr:
            bad.append("AI 에게 보내는 글에 그림 데이터(base64)가 섞여 있습니다 — 토큰만 태웁니다")
        for must in ["IC50", "[그림 1]", "```python", "용량 (µM)"]:
            if must not in pr:
                bad.append("AI 에게 보내는 글에 %r 이 빠졌습니다" % must)
        print("  AI 입력 %d자 · 그림은 [그림 N] 으로 바뀜 · 코드·표 포함" % len(pr))

        # ── 3. Word(.docx) 뜯기 ──
        print("── Word 뜯기 ──")
        dx = pg.evaluate("""async b64 => {
            const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
            const md = await docxToMarkdown(bin.buffer);
            const x = splitDoc(md);
            return {md: md.length, title: x.title, imgs: x.imgs.length,
                    tables: x.tables.length, facts: x.facts.length,
                    heads: (md.match(/^#+ /gm) || []).length,
                    hasIC: md.includes("34.8"), tbl: x.tables[0] || ""};
        }""", docx_b64)
        print("  제목: %s" % dx["title"])
        print("  제목줄 %d개 · 그림 %d장 · 표 %d개 · 숫자줄 %d줄"
              % (dx["heads"], dx["imgs"], dx["tables"], dx["facts"]))
        if "MDX-114" not in dx["title"]:
            bad.append("Word 제목을 못 뽑았습니다: %r" % dx["title"])
        if dx["imgs"] != 1:
            bad.append("Word 안의 그림은 1장인데 %d장으로 읽었습니다" % dx["imgs"])
        if dx["tables"] != 1:
            bad.append("Word 안의 표는 1개인데 %d개로 읽었습니다" % dx["tables"])
        if not dx["hasIC"]:
            bad.append("Word 본문의 숫자(34.8)를 못 읽었습니다")
        if dx["heads"] < 4:
            bad.append("Word 의 제목 단계를 %d개만 읽었습니다" % dx["heads"])
        if "IC50" not in dx["tbl"]:
            bad.append("Word 표 내용을 못 읽었습니다: %r" % dx["tbl"][:120])

        # ── 4. 화면 ──
        print("── 화면 ──")
        pg.evaluate("""md => {
            const doc = splitDoc(md);
            DIGESTS["t.md"] = {doc, md:null, at:Date.now()};
            digestModal("t.md");
            renderDigest("t.md", doc, null);
        }""", md)
        pg.wait_for_timeout(500)
        shown = pg.evaluate("""() => {
            const b = document.getElementById("dgBody");
            const imgs = [...b.querySelectorAll("img")];
            return {
              imgs: imgs.length,
              broken: imgs.filter(i => i.complete && i.naturalWidth === 0).length,
              ext: [...b.querySelectorAll("a[target=_blank]")].length,
              pre: b.querySelectorAll("pre").length,
              tbl: b.querySelectorAll("table").length,
              details: b.querySelectorAll("details").length,
              text: b.innerText.slice(0, 4000),
              datauri: b.innerText.includes("base64")
            };
        }""")
        print("  그림 %d장 (깨진 것 %d) · 바깥 링크 %d · 코드칸 %d · 표 %d · 접은 칸 %d"
              % (shown["imgs"], shown["broken"], shown["ext"], shown["pre"], shown["tbl"], shown["details"]))
        if shown["imgs"] < 2:
            bad.append("화면에 그림이 %d장만 나옵니다 (2장이어야 합니다)" % shown["imgs"])
        if shown["broken"]:
            bad.append("화면의 그림 %d장이 깨져 있습니다" % shown["broken"])
        if not shown["ext"]:
            bad.append("바깥 주소 그림이 링크로도 안 보입니다")
        if shown["pre"] < 2:
            bad.append("코드가 %d덩이만 보입니다 (2덩이여야 합니다)" % shown["pre"])
        if not shown["tbl"]:
            bad.append("표가 화면에 안 그려집니다")
        if shown["datauri"]:
            bad.append("화면 글자에 base64 가 그대로 보입니다 — 글자 벽이 됩니다")
        for must in ["그림", "숫자", "표", "코드", "원문 보기"]:
            if must not in shown["text"]:
                bad.append("화면에 「%s」 묶음이 없습니다" % must)

        # ── 4b. AI 요약이 들어왔을 때의 화면 ──
        #   AI 호출 자체는 하지 않습니다(요금·로그인). 대신 AI 가 돌려줄 모양의 글을
        #   넣어 화면이 표·칩·굵게까지 제대로 그리는지 봅니다.
        sample = ("## 한눈에\n"
                  "- MDX-114 를 HepG2 에 0.1~100 µM 로 24시간 처리해 생존율을 재었습니다.\n"
                  "- **IC50 34.8 µM** 로, 2차 실험(52 µM)보다 낮게 나왔습니다.\n\n"
                  "## 숫자\n\n| 항목 | 값 |\n| --- | --- |\n| IC50 | 34.8 µM (95% CI 29.1~41.6) |\n"
                  "| 회귀 r2 | 0.947 |\n| p | 2.3e-07 |\n| n | 조건당 6 |\n\n"
                  "## 무엇을 했는지\n- CCK-8 흡광 450nm, one-way ANOVA + Tukey\n"
                  "- python: 대조군 평균으로 정규화한 뒤 log10(용량)에 선형회귀\n"
                  "- R(drc): 4-parameter logistic 으로 IC50 재계산\n\n"
                  "## 그림이 말하는 것\n- [그림 1] 10 µM 부터 곡선이 꺾입니다.\n\n"
                  "## 짚어 볼 것\n- [최우선] 100 µM 에서 DMSO 가 0.5% 를 넘는데 용매 대조가 없습니다.\n"
                  "- [높음] 세포주가 HepG2 하나뿐입니다.\n")
        pg.evaluate("""a => { const doc = splitDoc(a.md); renderDigest("t.md", doc, a.sum); }""",
                    {"md": md, "sum": sample})
        pg.wait_for_timeout(400)
        ai = pg.evaluate("""() => { const b = document.getElementById("dgBody");
            return {tbl: b.querySelectorAll("table").length,
                    chips: [...b.querySelectorAll("span")].filter(s =>
                       getComputedStyle(s).borderRadius.startsWith("999")).length,
                    bold: b.querySelectorAll("b").length,
                    h: [...b.querySelectorAll("h1,h2,h3,h4")].map(x => x.innerText.trim()),
                    md: b.innerText.includes("##") || b.innerText.includes("**")}; }""")
        print("── AI 요약이 들어온 화면 ──")
        print("  제목 묶음: %s" % " · ".join(ai["h"][:6]))
        print("  표 %d개 · 우선순위 칩 %d개 · 굵게 %d개" % (ai["tbl"], ai["chips"], ai["bold"]))
        if ai["md"]:
            bad.append("요약이 Markdown 기호(## 또는 **) 그대로 보입니다 — 안 그려집니다")
        if ai["tbl"] < 2:
            bad.append("요약의 숫자 표가 안 그려집니다 (표 %d개)" % ai["tbl"])
        if ai["chips"] < 2:
            bad.append("[최우선]·[높음] 표시가 칩으로 안 그려집니다 (%d개)" % ai["chips"])
        if "한눈에" not in " ".join(ai["h"]):
            bad.append("「한눈에」 제목이 안 보입니다: %s" % ai["h"])

        # ── 4c. 터치 44px · 대비 · 넘침 (폭 3종) ──
        #   저장소 규칙: 색 대비는 WCAG 상대휘도로 계산해 수치를 남깁니다. 눈대중 금지.
        print("── 터치 크기·대비 (폭 3종) ──")
        for w, label in [(390, "휴대폰 390"), (768, "태블릿 768"), (1280, "데스크톱 1280")]:
            pg.set_viewport_size({"width": w, "height": 860})
            pg.wait_for_timeout(300)
            r = pg.evaluate(r"""() => {
                const L = c => { c = c.map(x => x/255).map(x => x <= 0.03928 ? x/12.92
                    : Math.pow((x+0.055)/1.055, 2.4));
                    return 0.2126*c[0] + 0.7152*c[1] + 0.0722*c[2]; };
                const P = s => (s.match(/[0-9.]+/g) || [0,0,0]).slice(0,3).map(Number);
                const R = (a,b) => { const x = L(P(a)), y = L(P(b));
                    return (Math.max(x,y)+0.05) / (Math.min(x,y)+0.05); };
                const m = document.getElementById("dgModal");
                const card = m.firstElementChild, body = document.getElementById("dgBody");
                const small = [...m.querySelectorAll("button")].filter(b => {
                    const r = b.getBoundingClientRect();
                    return r.width > 0 && (r.height < 44 || r.width < 44);
                }).map(b => b.textContent.trim() + " " + Math.round(b.getBoundingClientRect().width)
                       + "x" + Math.round(b.getBoundingClientRect().height));
                const cons = [...m.querySelectorAll("button")].map(b => {
                    const g = getComputedStyle(b);
                    const bg = g.backgroundColor.includes("rgba(0, 0, 0, 0)") ? "rgb(255,255,255)"
                             : g.backgroundColor;
                    return [b.textContent.trim(), +R(g.color, bg).toFixed(2)];
                });
                const mini = [...body.querySelectorAll(".mini")].slice(0,4).map(e =>
                    +R(getComputedStyle(e).color, "rgb(255,255,255)").toFixed(2));
                return {small, cons, mini,
                        over: card.scrollWidth > card.clientWidth + 2
                              || document.documentElement.scrollWidth > window.innerWidth + 2,
                        imgFit: [...body.querySelectorAll("img")].every(i =>
                              i.getBoundingClientRect().right <= window.innerWidth + 2)};
            }""")
            low = [c for c in r["cons"] if c[1] < 4.5] + [x for x in r["mini"] if x < 4.5]
            if r["small"]:
                bad.append("%s: 44px 못 미치는 단추 — %s" % (label, ", ".join(r["small"])))
            if r["over"]:
                bad.append("%s: 한 장 보기 창이 화면을 넘칩니다" % label)
            if not r["imgFit"]:
                bad.append("%s: 그림이 화면 밖으로 삐져나갑니다" % label)
            if low:
                bad.append("%s: 대비 4.5:1 못 미침 — %s" % (label, low))
            print("  %-14s 44px %s · 넘침 %s · 단추 대비 %s · 작은 글자 %s"
                  % (label, "OK" if not r["small"] else "실패",
                     "없음" if not r["over"] else "있음",
                     " ".join("%.2f" % c[1] for c in r["cons"]),
                     " ".join("%.2f" % x for x in r["mini"])))
        pg.set_viewport_size({"width": 1280, "height": 900})

        # ── 5. 바깥 그림을 <img> 로 그리지 않는지 (추적 방지) ──
        leak = pg.evaluate("""() => {
            const h = mdToHtml('![x](https://example.com/t.png)\\n\\n![y](data:image/png;base64,iVBORw0KGgo=)');
            return {extImg: /<img[^>]+https?:/.test(h), dataImg: /<img[^>]+data:image/.test(h),
                    js: /<img[^>]+javascript:/i.test(mdToHtml('![x](javascript:alert(1))'))};
        }""")
        if leak["extImg"]:
            bad.append("바깥 주소 그림을 <img> 로 그립니다 — 누가 언제 열었는지 그 서버에 남습니다")
        if not leak["dataImg"]:
            bad.append("문서에 박힌 그림을 <img> 로 안 그립니다")
        if leak["js"]:
            bad.append("javascript: 주소가 <img> 로 들어갑니다")
        if not leak["extImg"] and leak["dataImg"] and not leak["js"]:
            print("  박힌 그림만 그림 · 바깥 주소와 javascript: 는 안 그림")

        if errs:
            bad.append("자바스크립트 오류: " + " / ".join(errs[:3]))
        b.close()

    print()
    if bad:
        print("고칠 것 %d개" % len(bad))
        for x in bad:
            print("  · " + x)
        sys.exit(1)
    print("한 장 보기: MD·Word 를 접어 그림·숫자·표·코드까지 한 화면에 보여 줍니다")


if __name__ == "__main__":
    main()
