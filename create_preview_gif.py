#!/usr/bin/env python3
"""Create a compact animated 3D Collatz preview for GitHub README (Pillow)."""
from math import cos, sin, log2, pi
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from visualize3d import trajectory

W,H=480,270
values=trajectory(837799,10000)
heights=[log2(n) for n in values]
maximum=max(heights)
coords=[]
for i,h in enumerate(heights):
    t=i/(len(values)-1)
    a=i*.19
    r=(.18+.42*.7)*(.35+.65*t)
    coords.append((r*cos(a),r*sin(a),(h/maximum-.5)*1.65))
frames=[]
font=ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf",17) if Path("/usr/share/fonts/TTF/DejaVuSans.ttf").exists() else ImageFont.load_default()
for frame in range(32):
    im=Image.new("RGB",(W,H),(8,18,37))
    draw=ImageDraw.Draw(im)
    angle=.25+frame*2*pi/32
    elevation=.35
    scale=110
    projected=[]
    for x,z,y in coords:
        xr=x*cos(angle)-z*sin(angle)
        zr=x*sin(angle)+z*cos(angle)
        projected.append((int(W/2+scale*xr),int(H/2-scale*(y*cos(elevation)-zr*sin(elevation)))))
    reveal=max(2,round(len(coords)*(frame+1)/32))
    draw.line(projected[:reveal],fill=(75,206,255),width=3,joint="curve")
    for i in range(0,reveal,12):
        px,py=projected[i]
        draw.ellipse((px-2,py-2,px+2,py+2),fill=(245,160,80))
    px,py=projected[reveal-1]
    draw.ellipse((px-5,py-5,px+5,py+5),fill=(255,255,255))
    draw.text((20,18),"SYRACUSE 3D  |  n = 837799",font=font,fill=(230,245,255))
    draw.text((20,H-36),f"Step {reveal-1} / 524   |   log2(height)",font=font,fill=(150,191,225))
    frames.append(im.quantize(colors=32,method=Image.Quantize.FASTOCTREE))
path=Path("docs/gallery/collatz-3d-preview.gif")
path.parent.mkdir(parents=True,exist_ok=True)
frames[0].save(path,save_all=True,append_images=frames[1:],duration=110,loop=0,optimize=True,disposal=2)
print(path,path.stat().st_size)