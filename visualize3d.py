#!/usr/bin/env python3
"""Standalone animated Collatz 3D explorer (no Python dependencies)."""
import argparse
import html
import json
from pathlib import Path

def trajectory(start: int, max_steps: int):
    if start <= 0 or max_steps < 1:
        raise ValueError("start and max-steps must be positive")
    values = [start]
    n = start
    for _ in range(max_steps):
        if n == 1:
            break
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        values.append(n)
    return values

TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Syracuse — Collatz 3D Explorer</title>
<style>
:root{color-scheme:dark;font-family:system-ui,sans-serif}*{box-sizing:border-box}
body{margin:0;background:#080e20;color:#e8f0ff}
header{padding:20px 26px;border-bottom:1px solid #253552;background:#0d1931}
h1{margin:0;font-size:1.4rem}p{color:#a7b9d8;margin:7px 0}
main{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:18px;padding:18px;max-width:1600px;margin:auto}
canvas{display:block;width:100%;height:min(74vh,760px);min-height:400px;border:1px solid #263b61;border-radius:14px;background:radial-gradient(ellipse at 50% 45%,#15274a,#080e20)}
aside{background:#111e36;border:1px solid #263b61;border-radius:14px;padding:20px}
button,input{accent-color:#57d7ff}button{background:#195b86;border:1px solid #3a94c2;color:white;border-radius:8px;padding:10px 14px;cursor:pointer;margin:4px}
label{display:block;margin-top:18px;font-size:.9rem;color:#bcd0ed}input{width:100%}
.stat{padding:10px 0;border-bottom:1px solid #263b61}.stat strong{display:block;font-size:1.1rem;overflow-wrap:anywhere}
small{color:#8da7cc}a{color:#72d9ff}
@media(max-width:850px){main{grid-template-columns:1fr}canvas{height:55vh;min-height:300px}}
</style></head><body>
<header><h1>Syracuse · Animated 3D Trajectory</h1><p>Interactive logarithmic visualization · Drag to rotate · Wheel to zoom · No external libraries</p></header>
<main><canvas id="scene"></canvas><aside>
<div class="stat"><small>Starting integer</small><strong id="start"></strong></div>
<div class="stat"><small>Steps shown</small><strong id="steps"></strong></div>
<div class="stat"><small>Maximum value</small><strong id="peak"></strong></div>
<div class="stat"><small>Convergence</small><strong id="status"></strong></div>
<label>Playback</label><button id="play">Pause</button><button id="reset">Restart</button>
<label>Playback speed</label><input id="speed" type="range" min="1" max="100" value="20">
<label>3D spiral width</label><input id="radius" type="range" min="1" max="100" value="42">
<label>Camera elevation</label><input id="elevation" type="range" min="-80" max="80" value="22">
<p style="margin-top:22px"><small>Height is log₂(n), not n. Spiral coordinates are a visual embedding, not a mathematical proof or a physical 3D orbit.</small></p>
</aside></main>
<script>
"use strict";
const raw=__DATA__;
const values=raw.values.map(x=>BigInt(x));
const log2big=n=>{if(n<=0n)return 0;const b=n.toString(2);return b.length-1+Math.log2(parseInt(b.slice(0,Math.min(52,b.length)),2)/2**(Math.min(52,b.length)-1))};
const heights=values.map(log2big),maxHeight=Math.max(1,...heights);
const canvas=document.getElementById('scene'),ctx=canvas.getContext('2d');
let angle=.4,elev=.38,zoom=1,playing=true,shown=1,last=0,drag=false,lastX=0,lastY=0;
document.getElementById('start').textContent=raw.values[0];
document.getElementById('steps').textContent=(values.length-1).toLocaleString();
document.getElementById('peak').textContent=raw.peak;
document.getElementById('status').textContent=raw.converged?'Reached 1':'Step limit reached';
document.getElementById('play').onclick=()=>{playing=!playing;document.getElementById('play').textContent=playing?'Pause':'Play'};
document.getElementById('reset').onclick=()=>{shown=1;playing=true;document.getElementById('play').textContent='Pause'};
canvas.addEventListener('pointerdown',e=>{drag=true;lastX=e.clientX;lastY=e.clientY;canvas.setPointerCapture(e.pointerId)});
canvas.addEventListener('pointerup',()=>drag=false);
canvas.addEventListener('pointermove',e=>{if(drag){angle+=(e.clientX-lastX)*.009;elev=Math.max(-1.4,Math.min(1.4,elev+(e.clientY-lastY)*.008));lastX=e.clientX;lastY=e.clientY}});
canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.3,Math.min(4,zoom*(e.deltaY>0?.9:1.1)))},{passive:false});
const palette=t=>{let hue=195+140*t;return 'hsl('+hue+',90%,65%)'};
function draw(time){
const dpr=Math.min(2,window.devicePixelRatio||1),w=canvas.clientWidth,h=canvas.clientHeight;
if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr)}
ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
if(playing&&time-last>30){shown=Math.min(values.length,shown+Math.max(1,Math.round(+document.getElementById('speed').value/5)));last=time;if(shown>=values.length){playing=false;document.getElementById('play').textContent='Play'}}
const rad=+document.getElementById('radius').value/100;
const cx=w/2,cy=h*.53,scale=Math.min(w,h)*.39*zoom;
const point=i=>{
const t=i/Math.max(1,values.length-1),a=i*.19,r=(.18+rad*.7)*(0.35+0.65*t);
const x=r*Math.cos(a),z=r*Math.sin(a),y=(heights[i]/maxHeight-.5)*1.65;
const xr=x*Math.cos(angle)-z*Math.sin(angle),zr=x*Math.sin(angle)+z*Math.cos(angle);
return [cx+scale*xr,cy-scale*(y*Math.cos(elev)-zr*Math.sin(elev))];
};
ctx.lineWidth=1.6;ctx.beginPath();
for(let i=0;i<shown;i++){const [x,y]=point(i);if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y)}
ctx.strokeStyle='#56d9ff';ctx.shadowColor='#27bbff';ctx.shadowBlur=8;ctx.stroke();ctx.shadowBlur=0;
for(let i=0;i<shown;i+=Math.max(1,Math.floor(shown/150))){const [x,y]=point(i);ctx.fillStyle=palette(i/values.length);ctx.beginPath();ctx.arc(x,y,2.5,0,Math.PI*2);ctx.fill()}
const [x,y]=point(shown-1);ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fill();
ctx.fillStyle='#b6d2ed';ctx.font='13px system-ui';ctx.fillText('Step '+(shown-1)+' / '+(values.length-1),20,28);
if(!drag)angle+=.0016;
requestAnimationFrame(draw);
}
requestAnimationFrame(draw);
</script></body></html>
"""

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number", type=int)
    parser.add_argument("--max-steps", type=int, default=10000)
    parser.add_argument("--output", default="syracuse-3d.html")
    args = parser.parse_args()
    values = trajectory(args.number, args.max_steps)
    payload = {"values": [str(n) for n in values], "peak": str(max(values)), "converged": values[-1] == 1}
    # Avoid inserting raw untrusted text into JavaScript/HTML.
    encoded = json.dumps(payload).replace("<", "\\u003c")
    output = Path(args.output)
    output.write_text(TEMPLATE.replace("__DATA__", encoded), encoding="utf-8")
    print(f"Wrote {output} ({len(values)-1} steps, converged={payload['converged']})")

if __name__ == "__main__":
    main()