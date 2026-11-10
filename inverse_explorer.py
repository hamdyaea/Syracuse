#!/usr/bin/env python3
"""Offline interactive inverse Collatz tree explorer; no third-party dependencies."""
import argparse
import json
from pathlib import Path
from inverse_tree import inverse_tree

HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Syracuse — Inverse Collatz Explorer</title>
<style>
:root{font-family:system-ui,sans-serif;color-scheme:dark}*{box-sizing:border-box}
body{margin:0;background:#081225;color:#e5f3ff}header{padding:18px 24px;background:#0f1e39;border-bottom:1px solid #2c4569}
h1{margin:0;font-size:1.45rem}p{color:#a8c1dc;margin:8px 0}
main{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px;padding:16px;max-width:1700px;margin:auto}
#stage{height:76vh;min-height:420px;border:1px solid #2b4262;border-radius:14px;overflow:hidden;position:relative;background:radial-gradient(ellipse,#152c49,#081225)}
svg{width:100%;height:100%;touch-action:none;cursor:grab}svg:active{cursor:grabbing}
aside{border:1px solid #2b4262;background:#11223a;border-radius:14px;padding:20px;overflow-wrap:anywhere}
label{display:block;margin-top:18px;color:#b7d4ed}input{width:100%;accent-color:#53d8ff}
button{border:1px solid #3788ae;border-radius:8px;background:#174f73;color:white;padding:10px;margin:6px 5px 6px 0;cursor:pointer}
.stat{border-bottom:1px solid #2d4463;padding:12px 0}.stat b{display:block;margin-top:5px;font-size:1.1rem}
#path{font-size:.9rem;line-height:1.6;max-height:240px;overflow:auto;word-break:break-word}
.node{cursor:pointer}.node circle{stroke:#7be1ff;stroke-width:1.6;fill:#17648c}.node.selected circle{fill:#f3a846;stroke:#fff}.node.path circle{stroke:#ffc76d;stroke-width:3}
.node text{fill:white;font:12px system-ui;pointer-events:none}.edge{stroke:#426e91;stroke-width:1.5}.edge.path{stroke:#ffca67;stroke-width:3}
@media(max-width:850px){main{grid-template-columns:1fr}#stage{height:55vh}}
</style></head><body><header><h1>Syracuse · Inverse Collatz Explorer</h1><p>Click a node to inspect its path to 1 · Drag to pan · Scroll to zoom · Animate the construction</p></header>
<main><div id="stage"><svg id="view" xmlns="http://www.w3.org/2000/svg" aria-label="Interactive inverse Collatz tree"></svg></div>
<aside><div class="stat">Nodes <b id="count"></b></div><div class="stat">Maximum depth <b id="depth"></b></div>
<div class="stat">Selected integer <b id="selected">1</b></div>
<label>Visible depth <span id="depthLabel"></span></label><input id="level" type="range" min="0" max="1" value="0">
<div><button id="animate">Animate</button><button id="all">Show all</button><button id="fit">Reset view</button></div>
<label>Path to 1</label><div id="path">1</div>
<p style="margin-top:22px;font-size:.85rem">Only finite inverse branches rooted at 1 are displayed. This does not establish convergence for all positive integers. The 1–2–4 cycle is not expanded repeatedly.</p></aside></main>
<script>
"use strict";
const nodes=__NODES__,svg=document.getElementById('view'),stage=document.getElementById('stage');
const maxDepth=Math.max(...nodes.map(n=>n.depth)),level=document.getElementById('level');
level.max=maxDepth;level.value=maxDepth;
document.getElementById('count').textContent=nodes.length.toLocaleString();
document.getElementById('depth').textContent=maxDepth;
const ns='http://www.w3.org/2000/svg',make=(tag,attrs={})=>{const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));return e};
const groups=new Map();nodes.forEach((n,i)=>{if(!groups.has(n.depth))groups.set(n.depth,[]);groups.get(n.depth).push(i)});
const width=1400,height=Math.max(400,120+maxDepth*110),coords=[];
for(const [depth,ids] of groups)ids.forEach((id,i)=>coords[id]=[width*(i+1)/(ids.length+1),80+depth*110]);
const root=make('g');svg.append(root);
const edges=[],dots=[];
nodes.forEach((n,i)=>{if(n.parent!==null){const [x,y]=coords[i],[px,py]=coords[n.parent];const e=make('line',{x1:px,y1:py,x2:x,y2:y,class:'edge'});root.append(e);edges[i]=e}});
nodes.forEach((n,i)=>{const [x,y]=coords[i],g=make('g',{class:'node',transform:'translate('+x+' '+y+')'});
const c=make('circle',{r:20}),t=make('text',{'text-anchor':'middle',dy:'.35em'});t.textContent=String(n.value);g.append(c,t);root.append(g);dots[i]=g;
g.addEventListener('click',e=>{e.stopPropagation();select(i)})});
let chosen=0,scale=1,tx=0,ty=0,drag=false,mx=0,my=0,timer=null;
function apply(){root.setAttribute('transform','translate('+tx+' '+ty+') scale('+scale+')')}
function fit(){const w=stage.clientWidth,h=stage.clientHeight;scale=Math.min(w/width,h/height)*.9;tx=(w-width*scale)/2;ty=(h-height*scale)/2;apply()}
function select(id){chosen=id;const chain=[];let k=id;while(k!==null){chain.push(k);k=nodes[k].parent}
const set=new Set(chain);dots.forEach((g,i)=>{g.classList.toggle('selected',i===id);g.classList.toggle('path',set.has(i))});
edges.forEach((e,i)=>{if(e)e.classList.toggle('path',set.has(i))});
document.getElementById('selected').textContent=nodes[id].value;
document.getElementById('path').textContent=chain.map(i=>nodes[i].value).join(' → ');
}
function render(){const depth=+level.value;document.getElementById('depthLabel').textContent=depth;
dots.forEach((g,i)=>g.style.display=nodes[i].depth<=depth?'':'none');
edges.forEach((e,i)=>{if(e)e.style.display=nodes[i].depth<=depth?'':'none'})}
function stop(){if(timer){clearInterval(timer);timer=null}}
document.getElementById('all').onclick=()=>{stop();level.value=maxDepth;render()};
document.getElementById('fit').onclick=fit;
document.getElementById('animate').onclick=()=>{stop();level.value=0;render();timer=setInterval(()=>{level.value=+level.value+1;render();if(+level.value>=maxDepth)stop()},500)};
level.oninput=()=>{stop();render()};
svg.addEventListener('pointerdown',e=>{drag=true;mx=e.clientX;my=e.clientY;svg.setPointerCapture(e.pointerId)});
svg.addEventListener('pointerup',()=>drag=false);
svg.addEventListener('pointermove',e=>{if(!drag)return;tx+=e.clientX-mx;ty+=e.clientY-my;mx=e.clientX;my=e.clientY;apply()});
svg.addEventListener('wheel',e=>{e.preventDefault();const r=svg.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top,old=scale;
scale=Math.min(8,Math.max(.03,scale*(e.deltaY<0?1.12:.89)));tx=x-(x-tx)*scale/old;ty=y-(y-ty)*scale/old;apply()},{passive:false});
window.addEventListener('resize',fit);fit();select(0);render();
</script></body></html>"""

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", type=int, default=12)
    parser.add_argument("--max-nodes", type=int, default=300)
    parser.add_argument("--output", default="inverse-tree-interactive.html")
    args = parser.parse_args()
    nodes = inverse_tree(args.depth, args.max_nodes)
    payload = json.dumps(nodes, separators=(",", ":")).replace("<", "\\u003c")
    Path(args.output).write_text(HTML.replace("__NODES__", payload), encoding="utf-8")
    print(f"Wrote {args.output} ({len(nodes)} nodes, max depth {max(n['depth'] for n in nodes)})")

if __name__ == "__main__":
    main()