# -*- coding: utf-8 -*-
"""앱·탭 아이콘을 머리글의 허브 표시에서 만들어 냅니다.

손으로 그린 PNG 를 따로 두면 로고를 고칠 때마다 갈라집니다 — 한 군데(이 파일)에서
만들어 내고, 머리글 SVG 와 같은 색·같은 모양을 씁니다.

  python3 scripts/make_icons.py        아이콘 다시 만들기
  python3 scripts/make_icons.py --check  지금 파일과 다른지만 보기 (다르면 1)

작은 크기에서는 선이 사라집니다. 그래서 32px 짜리는 선을 굵게·점을 크게 한
간단한 판을 따로 씁니다 — 크롬 탭에서 뭉개지지 않게.
"""
import os, sys, hashlib, pathlib, tempfile
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 머리글과 같은 색 (WCAG 실측값은 index.html 의 .ct-mark 주석 참고)
C_MID   = "#0C7069"   # 가운데 허브 (--deep)
C_LINE  = "#5E9A94"
C_BLUE  = "#2F72C4"
C_AMBER = "#C8860D"
C_PURP  = "#6B4FC4"
C_CORAL = "#D2604A"


def glyph(line_w, node_r, mid_r):
    return f'''
  <g stroke="{C_LINE}" stroke-width="{line_w}" stroke-linecap="round">
    <line x1="24" y1="24" x2="12" y2="12"/><line x1="24" y1="24" x2="36" y2="12"/>
    <line x1="24" y1="24" x2="12" y2="36"/><line x1="24" y1="24" x2="36" y2="36"/>
  </g>
  <circle cx="12" cy="12" r="{node_r}" fill="{C_BLUE}"/>
  <circle cx="36" cy="12" r="{node_r}" fill="{C_AMBER}"/>
  <circle cx="12" cy="36" r="{node_r}" fill="{C_PURP}"/>
  <circle cx="36" cy="36" r="{node_r}" fill="{C_CORAL}"/>
  <circle cx="24" cy="24" r="{mid_r + 1.2}" fill="#FFFFFF"/>
  <circle cx="24" cy="24" r="{mid_r}" fill="{C_MID}"/>'''


def page(size, *, radius_pct, pad_pct, line_w, node_r, mid_r, bg="#FFFFFF"):
    """둥근 타일 위에 허브 표시. pad_pct 는 가장자리 여백(마스커블용)."""
    inner = 48 / (1 - 2 * pad_pct)
    off = (inner - 48) / 2
    r = radius_pct * inner
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
    html,body{{margin:0;padding:0;background:transparent}}
    svg{{display:block}}</style></head><body>
    <svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"
         viewBox="{-off} {-off} {inner} {inner}">
      <rect x="{-off}" y="{-off}" width="{inner}" height="{inner}" rx="{r}" fill="{bg}"/>
      {glyph(line_w, node_r, mid_r)}
    </svg></body></html>'''


# 크기마다 굵기를 달리합니다 — 작을수록 굵고 크게 그려야 보입니다
SPECS = [
    # 파일명,                크기, 모서리,  여백,   선,   점,   가운데,  바탕
    ("favicon-32.png",         32, 0.22, 0.02, 3.6, 6.4,  8.8, "#FFFFFF"),
    ("apple-touch-icon.png",  180, 0.22, 0.06, 2.8, 5.8,  8.6, "#FFFFFF"),
    ("icon-192.png",          192, 0.22, 0.06, 2.8, 5.8,  8.6, "#FFFFFF"),
    ("icon-512.png",          512, 0.22, 0.06, 2.6, 5.6,  8.4, "#FFFFFF"),
    # 마스커블: 안드로이드가 둘러 자르므로 여백을 크게 두고 바탕을 꽉 채웁니다
    ("icon-512-maskable.png", 512, 0.50, 0.18, 2.6, 5.6,  8.4, "#FFFFFF"),
]


def build(outdir):
    made = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, size, rad, pad, lw, nr, mr, bg in SPECS:
            html = page(size, radius_pct=rad, pad_pct=pad, line_w=lw, node_r=nr, mid_r=mr, bg=bg)
            pg = b.new_page(viewport={"width": size, "height": size},
                            device_scale_factor=1)
            pg.set_content(html, wait_until="load")
            pg.wait_for_timeout(120)
            out = outdir / name
            pg.locator("svg").screenshot(path=str(out), omit_background=True)
            pg.close()
            made[name] = hashlib.sha256(out.read_bytes()).hexdigest()[:12]
        b.close()
    return made


def main():
    check = "--check" in sys.argv
    if check:
        tmp = pathlib.Path(tempfile.mkdtemp())
        made = build(tmp)
        diff = []
        for name, h in made.items():
            cur = ROOT / name
            old = hashlib.sha256(cur.read_bytes()).hexdigest()[:12] if cur.exists() else "(없음)"
            if old != h:
                diff.append(f"{name}: 지금 {old} → 새로 만들면 {h}")
        if diff:
            print("아이콘이 로고와 갈라져 있습니다 — scripts/make_icons.py 로 다시 만드세요")
            for d in diff:
                print("  " + d)
            sys.exit(1)
        print("아이콘이 로고와 같습니다 (%d개)" % len(made))
        return
    made = build(ROOT)
    for name, h in made.items():
        print(f"  {name}  {(ROOT/name).stat().st_size:,}바이트  {h}")
    print("아이콘 %d개를 다시 만들었습니다" % len(made))


if __name__ == "__main__":
    main()
