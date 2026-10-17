# -*- coding: utf-8 -*-
"""모션캠 QA — 합성 얼굴로 고개 돌리기·끄덕임·말하기를 만들어 실제로 돌린다.

실존 인물의 얼굴을 쓰지 않는다. 매 실행마다 코드로 그린다.
가짜 카메라(--use-file-for-fake-video-capture)로 브라우저에 주입해,
출력 캔버스가 실제로 변하는지 확인한다.
"""
import os, sys, math, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SITE=os.environ.get("SITE","https://hyunjeongshin83.github.io/CampusTownHub")+"/motioncam.html"
W,H,FPS=320,240,30
SC=W/640.0

def draw_face(yaw=0.0, nod=0.0, mouth=0.0, skin=(232,198,174), hair=(58,44,38)):
    im=Image.new("RGB",(W,H),(198,208,210)); d=ImageDraw.Draw(im)
    s=lambda v:int(v*SC)
    cx=W//2+s(yaw*46); cy=H//2+s(nod*34)+s(6)
    sx=1.0-abs(yaw)*0.22
    fw,fh=s(116*sx),s(140)
    d.ellipse([cx-s(52),cy+s(88),cx+s(52),cy+s(240)],fill=tuple(max(0,c-18) for c in skin))
    d.ellipse([cx-fw,cy-fh-s(18),cx+fw,cy+fh-s(12)],fill=skin)
    d.pieslice([cx-fw-s(6),cy-fh-s(32),cx+fw+s(6),cy+s(50)],180,360,fill=hair)
    for sg in (-1,1):
        ex=cx+sg*(fw+s(13))
        if (sg>0 and yaw<0.5) or (sg<0 and yaw>-0.5):
            d.ellipse([ex-s(13),cy-s(30),ex+s(13),cy+s(34)],fill=skin)
    eo=s(52*sx)
    d.line([cx-eo-s(26),cy-s(54),cx-eo+s(22),cy-s(62)],fill=hair,width=max(2,s(9)))
    d.line([cx+eo-s(22),cy-s(62),cx+eo+s(26),cy-s(54)],fill=hair,width=max(2,s(9)))
    for sg in (-1,1):
        exx=cx+sg*eo; ew=s(29*sx)
        d.ellipse([exx-ew,cy-s(32),exx+ew,cy+s(4)],fill=(252,252,250))
        ir=s(13*sx); gz=exx+s(yaw*5)
        d.ellipse([gz-ir,cy-s(26),gz+ir,cy+s(2)],fill=(74,56,42))
        d.ellipse([gz-s(6*sx),cy-s(18),gz+s(6*sx),cy-s(6)],fill=(18,14,12))
        d.arc([exx-ew,cy-s(34),exx+ew,cy+s(6)],180,360,fill=(96,74,60),width=max(1,s(4)))
    nx=cx+s(yaw*9)
    d.polygon([(nx,cy-s(24)),(nx-s(17*sx),cy+s(44)),(nx+s(17*sx),cy+s(44))],
              fill=tuple(max(0,c-14) for c in skin))
    mw=s(43*sx); mh=s(16)+s(mouth*30); mxx=cx+s(yaw*7)
    d.ellipse([mxx-mw,cy+s(66),mxx+mw,cy+s(66)+mh*2],fill=(176,96,96))
    if mouth>0.25: d.ellipse([mxx-mw+s(9),cy+s(72),mxx+mw-s(9),cy+s(60)+mh*2],fill=(92,38,40))
    return im.filter(ImageFilter.GaussianBlur(1.0))

def rgb2yuv(im):
    a=np.asarray(im,dtype=np.float32); R,G,B=a[:,:,0],a[:,:,1],a[:,:,2]
    Y=(0.257*R+0.504*G+0.098*B+16).clip(0,255).astype(np.uint8)
    U=(-0.148*R-0.291*G+0.439*B+128).clip(0,255).astype(np.uint8)
    V=(0.439*R-0.368*G-0.071*B+128).clip(0,255).astype(np.uint8)
    return Y,U[::2,::2],V[::2,::2]

def build(tmp):
    frames=[]
    def seg(n,f):
        for i in range(n): frames.append(f(i/max(1,n-1)))
    seg(15, lambda t:(0,0,0))
    seg(20, lambda t:( math.sin(t*math.pi)*0.95,0,0))
    seg(20, lambda t:(-math.sin(t*math.pi)*0.95,0,0))
    seg(18, lambda t:(0, math.sin(t*math.pi*2)*0.85,0))
    seg(20, lambda t:(0,0,(math.sin(t*math.pi*3)+1)/2))
    y4m=os.path.join(tmp,"motion.y4m"); png=os.path.join(tmp,"face.png")
    with open(y4m,"wb") as f:
        f.write(f"YUV4MPEG2 W{W} H{H} F{FPS}:1 Ip A1:1 C420\n".encode())
        for (yw,nd,mo) in frames:
            Y,U,V=rgb2yuv(draw_face(yw,nd,mo))
            f.write(b"FRAME\n"); f.write(Y.tobytes()); f.write(U.tobytes()); f.write(V.tobytes())
    draw_face(0,0,0).save(png)
    return y4m,png,len(frames)

def main():
    from playwright.sync_api import sync_playwright
    tmp=tempfile.mkdtemp()
    y4m,png,nf=build(tmp)
    print(f"합성 영상 {nf}프레임 · {W}x{H}")
    ok=ng=0
    def t(n,g,w):
        nonlocal ok,ng
        p=(g==w); ok+=p; ng+=(not p)
        print(("PASS  " if p else "FAIL  ")+n+f"   got={g} want={w}")
    with sync_playwright() as p:
        b=p.chromium.launch(args=["--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream", f"--use-file-for-fake-video-capture={y4m}"])
        pg=b.new_page(permissions=["camera"])
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(SITE, wait_until="networkidle", timeout=90000); pg.wait_for_timeout(2500)
        t("시작 전 [시작] 버튼 비활성", pg.is_disabled("#go"), True)
        pg.set_input_files("#pick", png)
        for _ in range(50):
            pg.wait_for_timeout(500)
            if not pg.is_disabled("#go"): break
        m=pg.inner_text("#msg")
        print("  기준 사진:", m)
        t("합성 얼굴 인식 성공", "등록 완료" in m, True)
        if pg.is_disabled("#go"):
            print("\n0 PASS / 1 FAIL"); b.close(); return 1
        pg.click("#go"); pg.wait_for_timeout(2500)
        seen=[]
        for _ in range(12):
            pg.wait_for_timeout(400)
            seen.append(pg.evaluate("""()=>{const c=document.getElementById('out');
              const x=c.getContext('2d');
              const d=x.getImageData(Math.floor(c.width*.35),Math.floor(c.height*.45),
                                     Math.floor(c.width*.3),Math.floor(c.height*.2)).data;
              let s=0,bad=0; for(let k=0;k<d.length;k+=4*7){ s+=d[k]+d[k+1]+d[k+2];
                if(!isFinite(d[k]))bad++; } return {s,bad};}"""))
        uniq=len({x["s"] for x in seen})
        t("출력이 프레임마다 변함 (모션 반영)", uniq>=4, True)
        t("비정상 픽셀 없음", sum(x["bad"] for x in seen), 0)
        t("스크립트 오류 없음", len(errs), 0)
        if errs: print("  오류:", errs[:2])
        print(f"\n{ok} PASS / {ng} FAIL")
        b.close()
    return 1 if ng else 0

if __name__=="__main__":
    sys.exit(main())
