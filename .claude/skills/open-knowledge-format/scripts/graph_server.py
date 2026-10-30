#!/usr/bin/env python3
"""Render an OKF vault as an interactive, live-updating graph in the browser.

Parses a vault into nodes (concept notes) and edges (resolvable internal links),
optionally filters to a query and its 1-hop neighbourhood, serves a self-contained
HTML page (no external assets, no dependencies), and opens a browser to it.

The server watches the vault for changes (a background mtime-scan thread) and pushes
updates to the open page over Server-Sent Events; the page merges them into the
running layout — so edits show up without a restart and without reshuffling. SSE is
used rather than WebSockets because the flow is one-way (server → page) and SSE
rides plain HTTP, keeping this stdlib-only. parse_frontmatter/trust_tier are reused
from validate_okf.py so degree/trust match the validator exactly.

Usage:
  python3 graph_server.py <vault-dir> [--query Q] [--host 127.0.0.1]
                          [--port 0] [--no-open] [--no-reserved] [--dump PATH]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from okf_graph import (  # noqa: E402
    build_graph, prune_reserved, vault_signature,
)


def apply_query(nodes, edges, query):
    if not query:
        for n in nodes.values():
            n["match"] = False
        return nodes, edges
    q = query.lower()
    matched = {rel for rel, n in nodes.items() if q in n["search"]}
    keep = set(matched)
    for a, b in edges:
        if a in matched:
            keep.add(b)
        if b in matched:
            keep.add(a)
    sub_nodes = {rel: n for rel, n in nodes.items() if rel in keep}
    for rel, n in sub_nodes.items():
        n["match"] = rel in matched
    sub_edges = [(a, b) for a, b in edges if a in keep and b in keep]
    return sub_nodes, sub_edges


def graph_payload(vault, query, no_reserved):
    """The JSON the page consumes — for both the initial render and SSE updates."""
    nodes, edges, stats = build_graph(vault)
    if no_reserved:
        nodes, edges, stats = prune_reserved(nodes, edges, stats)
    nodes, edges = apply_query(nodes, edges, query)
    payload_nodes = [{k: v for k, v in n.items() if k != "search"}
                     for n in nodes.values()]
    return {
        "vault": os.path.basename(vault.rstrip("/")) or vault,
        "query": query or "",
        "nodes": payload_nodes,
        "edges": [{"source": a, "target": b} for a, b in edges],
        "stats": dict(stats, shown_nodes=len(payload_nodes), shown_edges=len(edges)),
    }


def render_html(payload):
    data_json = json.dumps(payload, ensure_ascii=True).replace("</", "<\\/")
    return TEMPLATE.replace("/*__DATA__*/null", data_json)


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:,">
<title>OKF graph</title>
<style>
  :root{
    --ground:#14161b; --panel:#1c1f26; --line:#2a2e38;
    --ink:#e6e8ee; --muted:#8b91a0; --accent:#7ee0c0;
    --font-ui:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
    --font-mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
  }
  *{box-sizing:border-box}
  html,body{margin:0;height:100%;background:var(--ground);color:var(--ink);
    font-family:var(--font-ui);overflow:hidden}
  #stage{position:fixed;inset:0}
  svg{width:100%;height:100%;display:block;cursor:grab}
  svg.panning{cursor:grabbing}
  .edge{stroke:var(--line);stroke-width:1;fill:none}
  .edge.hot{stroke:var(--accent);stroke-width:1.6;opacity:.9}
  .node circle{stroke:var(--ground);stroke-width:1.5;cursor:pointer;
    transition:opacity .25s ease}
  .node.isolated circle{fill:none!important;stroke-width:1.5}
  .node text{font-family:var(--font-mono);font-size:11px;fill:var(--muted);
    pointer-events:none;transition:opacity .25s ease}
  .node.match circle{stroke:var(--accent);stroke-width:2}
  .node.match text{fill:var(--ink)}
  .node .ring{fill:none;stroke-width:1.5;pointer-events:none}
  .node.trust-human .ring{stroke:var(--accent)}
  .node.trust-machine .ring{stroke:var(--muted)}
  .node.stale .ring{stroke:#f6c177;stroke-dasharray:2 2}
  .node.deprecated{opacity:.45}
  .dim{opacity:.12}
  header{position:fixed;top:0;left:0;right:0;height:52px;display:flex;
    align-items:center;gap:16px;padding:0 18px;background:linear-gradient(
    180deg,rgba(20,22,27,.96),rgba(20,22,27,.7));backdrop-filter:blur(6px);
    border-bottom:1px solid var(--line);z-index:5}
  .brand{font-family:var(--font-mono);font-weight:600;letter-spacing:.04em}
  .brand .dot{color:var(--accent)}
  .live{width:7px;height:7px;border-radius:50%;background:var(--accent);
    box-shadow:0 0 0 0 var(--accent);opacity:.35;transition:opacity .2s}
  .live.on{opacity:1;animation:pulse 1s ease}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(126,224,192,.6)}100%{box-shadow:0 0 0 8px rgba(126,224,192,0)}}
  .lens{font-family:var(--font-mono);font-size:12px;color:var(--ink);
    background:var(--panel);border:1px solid var(--line);border-radius:999px;
    padding:4px 12px}
  .lens b{color:var(--accent)}
  .counts{margin-left:auto;display:flex;gap:14px;font-size:12px;color:var(--muted);
    font-family:var(--font-mono)}
  .counts b{color:var(--ink);font-weight:600}
  .search{width:170px;background:var(--panel);border:1px solid var(--line);
    color:var(--ink);border-radius:8px;padding:6px 10px;font-family:var(--font-mono);
    font-size:12px}
  .search:focus{outline:2px solid var(--accent);outline-offset:0;border-color:transparent}
  #legend{position:fixed;left:14px;bottom:14px;z-index:5;background:rgba(28,31,38,.9);
    border:1px solid var(--line);border-radius:10px;padding:10px 12px;max-width:240px;
    font-size:12px}
  #legend h4{margin:0 0 8px;font-size:11px;text-transform:uppercase;
    letter-spacing:.08em;color:var(--muted);font-weight:600}
  .leg{display:flex;align-items:center;gap:8px;padding:3px 4px;border-radius:6px;
    cursor:pointer;font-family:var(--font-mono)}
  .leg:hover{background:var(--panel)}
  .leg.off{opacity:.4}
  .leg .sw{width:10px;height:10px;border-radius:3px;flex:none}
  .leg .sw.ring-key{background:transparent;border-radius:50%}
  .leg .sw.ring-key.human{border:1.5px solid var(--accent)}
  .leg .sw.ring-key.machine{border:1.5px solid var(--muted)}
  .leg .n{margin-left:auto;color:var(--muted)}
  #panel{position:fixed;top:52px;right:0;bottom:0;width:340px;background:var(--panel);
    border-left:1px solid var(--line);padding:20px;overflow:auto;z-index:6;
    transform:translateX(101%);transition:transform .28s cubic-bezier(.2,.7,.2,1)}
  #panel.open{transform:none}
  #panel .type{font-family:var(--font-mono);font-size:11px;letter-spacing:.06em;
    text-transform:uppercase;color:var(--accent)}
  #panel h2{margin:6px 0 4px;font-size:19px;line-height:1.25}
  #panel .path{font-family:var(--font-mono);font-size:11px;color:var(--muted);
    word-break:break-all}
  #panel .desc{margin:14px 0;color:var(--ink);line-height:1.5}
  #panel .excerpt{color:var(--muted);line-height:1.55;font-size:13px}
  #panel .tags{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0}
  #panel .tag{font-family:var(--font-mono);font-size:11px;background:var(--ground);
    border:1px solid var(--line);border-radius:999px;padding:2px 8px;color:var(--muted)}
  #panel .meta{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}
  #panel .pill{font-family:var(--font-mono);font-size:11px;border:1px solid var(--line);
    border-radius:999px;padding:2px 8px;color:var(--muted)}
  #panel .pill.trust-human{color:var(--accent);border-color:var(--accent)}
  #panel .pill.trust-machine{color:var(--ink)}
  #panel .pill.stalep{color:#f6c177;border-color:#f6c177}
  #panel .prov{font-family:var(--font-mono);font-size:11px;color:var(--muted);
    margin:4px 0;word-break:break-all}
  #panel h5{margin:18px 0 6px;font-size:11px;text-transform:uppercase;
    letter-spacing:.08em;color:var(--muted)}
  #panel a.link{display:block;font-family:var(--font-mono);font-size:12px;
    color:var(--ink);text-decoration:none;padding:3px 0;cursor:pointer}
  #panel a.link:hover{color:var(--accent)}
  #panel .close{position:absolute;top:14px;right:14px;background:none;border:none;
    color:var(--muted);font-size:20px;cursor:pointer;line-height:1}
  #panel .close:hover{color:var(--ink)}
  .empty{position:fixed;inset:52px 0 0 0;display:flex;align-items:center;
    justify-content:center;color:var(--muted);font-family:var(--font-mono);
    text-align:center;padding:20px;pointer-events:none}
  @media (prefers-reduced-motion:reduce){
    .node circle,.node text,#panel{transition:none}
  }
</style>
</head>
<body>
<header>
  <span class="brand">okf<span class="dot">·</span>graph</span>
  <span class="live" id="live" title="live — updates as the vault changes"></span>
  <span class="lens" id="lens"></span>
  <input class="search" id="search" placeholder="filter…" aria-label="Filter nodes">
  <span class="counts" id="counts"></span>
</header>
<div id="stage"><svg id="svg" aria-label="Knowledge graph"></svg></div>
<div id="legend">
  <h4>Types</h4><div id="legend-items"></div>
  <h4 style="margin-top:12px">Trust ring</h4>
  <div class="leg" style="cursor:default"><span class="sw ring-key human"></span><span>human-reviewed</span></div>
  <div class="leg" style="cursor:default"><span class="sw ring-key machine"></span><span>machine-confirmed</span></div>
</div>
<div class="empty" id="empty"></div>
<aside id="panel" aria-live="polite"></aside>

<script>
const DATA = /*__DATA__*/null;
const SVG_NS = "http://www.w3.org/2000/svg";
const PALETTE = ["#6ea8fe","#7ee0c0","#f6c177","#e58a8a","#b18aff","#86d06a",
                 "#f29fd0","#6fd0e0","#c7d17e","#e0a06f"];
const RESERVED_COLOR = "#5b6270";
const reduce = matchMedia("(prefers-reduced-motion:reduce)").matches;

const svg = document.getElementById("svg");
const rootG = document.createElementNS(SVG_NS,"g"); svg.appendChild(rootG);
const edgeLayer = document.createElementNS(SVG_NS,"g"); rootG.appendChild(edgeLayer);
const nodeLayer = document.createElementNS(SVG_NS,"g"); rootG.appendChild(nodeLayer);

let W=innerWidth, H=innerHeight;
const N=[], E=[], byId=new Map(), adj=new Map();
const typeColor={}; let ci=0;
const hidden=new Set();
let AN=[], AE=[], labelMin=0, selected=null, lastStats={};
let scale=1, tx=0, ty=0, alpha=0, running=false, fitted=false;
let dragging=null, dragOff=null, panning=false, panStart=null;

function colorFor(t){ if(!(t in typeColor)){
    typeColor[t]=(t==="index"||t==="log")?RESERVED_COLOR:PALETTE[ci++%PALETTE.length]; }
  return typeColor[t]; }
const radius = n => n.reserved ? 5 : Math.max(4, Math.min(20, 4+Math.sqrt(n.degree)*3));
function esc(s){ return String(s).replace(/[&<>"]/g,c=>(
  {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
function labelVisible(n){ return n.match || n.degree>=labelMin; }

// --- node/edge lifecycle ----------------------------------------------------
function styleNode(n){
  const g=n.el, c=n.circle, r=radius(n);
  const cls=["node"];
  if(n.degree===0&&!n.reserved) cls.push("isolated");
  if(n.match) cls.push("match");
  if(!n.reserved&&n.trust==="human-reviewed") cls.push("trust-human");
  if(!n.reserved&&n.trust==="machine-confirmed") cls.push("trust-machine");
  if(n.stale) cls.push("stale");
  if(n.status==="deprecated") cls.push("deprecated");
  g.setAttribute("class",cls.join(" "));
  c.setAttribute("r",r);
  c.setAttribute("fill",colorFor(n.type));
  if(n.degree===0&&!n.reserved) c.setAttribute("stroke",colorFor(n.type));
  else c.removeAttribute("stroke");
  const wantRing=(!n.reserved&&n.trust!=="unverified")||n.stale;
  if(wantRing){ if(!n.ring){ n.ring=document.createElementNS(SVG_NS,"circle");
      n.ring.setAttribute("class","ring"); g.insertBefore(n.ring,c); }
    n.ring.setAttribute("r",r+3); }
  else if(n.ring){ n.ring.remove(); n.ring=null; }
  n.label.setAttribute("x",r+4);
  n.label.textContent = n.title.length>28 ? n.title.slice(0,27)+"…" : n.title;
}
function addNode(nd){
  const n={...nd, x:W/2+(Math.random()-0.5)*80, y:H/2+(Math.random()-0.5)*80, vx:0, vy:0, ring:null};
  const g=document.createElementNS(SVG_NS,"g");
  const c=document.createElementNS(SVG_NS,"circle");
  const label=document.createElementNS(SVG_NS,"text"); label.setAttribute("dy","0.32em");
  g.appendChild(c); g.appendChild(label); nodeLayer.appendChild(g);
  n.el=g; n.circle=c; n.label=label;
  g.addEventListener("pointerdown",ev=>startDrag(ev,n));
  g.addEventListener("click",ev=>{ev.stopPropagation(); select(n);});
  g.addEventListener("pointerenter",()=>{ n.label.style.display=""; });
  g.addEventListener("pointerleave",()=>{ if(!selected) n.label.style.display=labelVisible(n)?"":"none"; });
  N.push(n); byId.set(n.id,n); styleNode(n); return n;
}
function removeNode(n){ n.el.remove(); const i=N.indexOf(n); if(i>=0)N.splice(i,1); byId.delete(n.id); }
function addEdge(ed){ const s=byId.get(ed.source), t=byId.get(ed.target); if(!s||!t)return;
  const l=document.createElementNS(SVG_NS,"path"); l.setAttribute("class","edge"); edgeLayer.appendChild(l);
  E.push({s,t,el:l}); }
function removeEdge(e){ e.el.remove(); const i=E.indexOf(e); if(i>=0)E.splice(i,1); }
function rebuildAdj(){ adj.clear(); for(const n of N) adj.set(n.id,new Set());
  for(const e of E){ adj.get(e.s.id).add(e.t.id); adj.get(e.t.id).add(e.s.id); } }
function recomputeActive(){ AN=N.filter(n=>!hidden.has(n.type));
  AE=E.filter(e=>!hidden.has(e.s.type)&&!hidden.has(e.t.type)); }
function recomputeLabelMin(){ const d=N.map(n=>n.degree).sort((a,b)=>b-a);
  labelMin=d[Math.min(22,Math.max(0,d.length-1))]||0; }
function refreshLabels(){ for(const n of N) n.label.style.display=labelVisible(n)?"":"none"; }
function applyHiddenDisplay(){
  for(const n of N) n.el.style.display=hidden.has(n.type)?"none":"";
  for(const e of E) e.el.style.display=(hidden.has(e.s.type)||hidden.has(e.t.type))?"none":""; }

// --- the reconciler: merge a fresh payload into the running graph -----------
const EK = e => e.s.id+"\u001f"+e.t.id;
function applyData(data, opts){
  opts=opts||{};
  const newN=new Map(data.nodes.map(n=>[n.id,n]));
  const newEK=new Set(data.edges.map(e=>e.source+"\u001f"+e.target));
  for(const nd of data.nodes){
    const ex=byId.get(nd.id);
    if(ex){ const {x,y,vx,vy}=ex; Object.assign(ex,nd); ex.x=x;ex.y=y;ex.vx=vx;ex.vy=vy; styleNode(ex); }
    else addNode(nd);
  }
  for(const n of [...N]) if(!newN.has(n.id)){ if(selected===n) deselect(); removeNode(n); }
  const haveEK=new Set(E.map(EK));
  for(const ed of data.edges){ const k=ed.source+"\u001f"+ed.target;
    if(!haveEK.has(k)) addEdge(ed); }
  for(const e of [...E]) if(!newEK.has(EK(e))) removeEdge(e);
  rebuildAdj(); recomputeActive(); recomputeLabelMin(); applyHiddenDisplay();
  lastStats=data.stats;
  buildLegend(); updateHeader();
  document.getElementById("empty").textContent = N.length ? "" :
    (data.query ? `No notes match "${data.query}". Try a broader query.` : `This vault has no notes yet.`);
  if(selected && byId.has(selected.id)) select(selected);
  else { selected=null; document.getElementById("panel").classList.remove("open"); refreshLabels(); }
  if(opts.fit) fitted=false;
  kick();
}

// --- force simulation -------------------------------------------------------
const REP=11000, REST=110, SPRING=0.018, CENTER=0.00025, DAMP=0.86;
function forces(a1){
  for(const n of AN){ n.vx += (W/2-n.x)*CENTER*a1; n.vy += (H/2-n.y)*CENTER*a1; }
  for(let i=0;i<AN.length;i++) for(let j=i+1;j<AN.length;j++){
    const a=AN[i], b=AN[j]; let dx=a.x-b.x, dy=a.y-b.y;
    let d2=dx*dx+dy*dy||0.01; const d=Math.sqrt(d2); const rep=REP/d2*a1;
    dx/=d; dy/=d; a.vx+=dx*rep; a.vy+=dy*rep; b.vx-=dx*rep; b.vy-=dy*rep;
  }
  for(const e of AE){ let dx=e.t.x-e.s.x, dy=e.t.y-e.s.y;
    const d=Math.sqrt(dx*dx+dy*dy)||0.01; const f=(d-REST)*SPRING*a1;
    dx/=d; dy/=d; e.s.vx+=dx*f; e.s.vy+=dy*f; e.t.vx-=dx*f; e.t.vy-=dy*f; }
  for(const n of AN){ if(n===dragging)continue; n.x+=n.vx*=DAMP; n.y+=n.vy*=DAMP; }
}
function step(){ forces(alpha); alpha*=0.99; if(alpha<0.02) alpha=0; draw();
  if(alpha>0) requestAnimationFrame(step);
  else { running=false; if(!fitted){ fitted=true; fitView(); } } }
function kick(){ if(reduce){ for(let i=0;i<600;i++) forces(1); draw();
    if(!fitted){ fitted=true; fitView(); } return; }
  alpha=Math.max(alpha,0.6); if(!running){ running=true; requestAnimationFrame(step); } }
function draw(){
  for(const e of AE) e.el.setAttribute("d",`M${e.s.x},${e.s.y}L${e.t.x},${e.t.y}`);
  for(const n of AN) n.el.setAttribute("transform",`translate(${n.x},${n.y})`);
}

// --- pan / zoom / fit -------------------------------------------------------
function applyView(){ rootG.setAttribute("transform",`translate(${tx},${ty}) scale(${scale})`); }
function fitView(){
  if(!AN.length) return;
  let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
  for(const n of AN){ if(n.x<minX)minX=n.x; if(n.x>maxX)maxX=n.x;
    if(n.y<minY)minY=n.y; if(n.y>maxY)maxY=n.y; }
  const pad=90, topbar=60, gw=(maxX-minX)||1, gh=(maxY-minY)||1;
  scale=Math.min((W-2*pad)/gw,(H-topbar-2*pad)/gh,1.6);
  tx=W/2-(minX+maxX)/2*scale; ty=(H+topbar)/2-(minY+maxY)/2*scale; applyView();
}
svg.addEventListener("wheel",ev=>{ ev.preventDefault();
  const f=ev.deltaY<0?1.1:1/1.1; tx=ev.clientX-(ev.clientX-tx)*f; ty=ev.clientY-(ev.clientY-ty)*f;
  scale*=f; applyView(); },{passive:false});
svg.addEventListener("pointerdown",ev=>{ if(ev.target.closest(".node"))return;
  panning=true; svg.classList.add("panning"); panStart={x:ev.clientX-tx,y:ev.clientY-ty}; deselect(); });
addEventListener("pointermove",ev=>{ if(panning){ tx=ev.clientX-panStart.x; ty=ev.clientY-panStart.y; applyView(); }});
addEventListener("pointerup",()=>{ panning=false; svg.classList.remove("panning"); dragging=null; });

function startDrag(ev,n){ ev.stopPropagation(); dragging=n;
  const p=toWorld(ev.clientX,ev.clientY); dragOff={x:p.x-n.x,y:p.y-n.y}; }
addEventListener("pointermove",ev=>{ if(!dragging)return;
  const p=toWorld(ev.clientX,ev.clientY); dragging.x=p.x-dragOff.x; dragging.y=p.y-dragOff.y;
  dragging.vx=dragging.vy=0; kick(); });
function toWorld(cx,cy){ return {x:(cx-tx)/scale, y:(cy-ty)/scale}; }

// --- selection / panel ------------------------------------------------------
function select(n){
  selected=n; const nbrs=adj.get(n.id)||new Set();
  for(const m of N){ const on=m===n||nbrs.has(m.id);
    m.el.classList.toggle("dim",!on);
    m.label.style.display = on ? "" : (labelVisible(m)?"":"none"); }
  for(const e of E){ const on=e.s===n||e.t===n;
    e.el.classList.toggle("hot",on); e.el.classList.toggle("dim",!on); }
  showPanel(n);
}
function deselect(){ selected=null;
  for(const m of N) m.el.classList.remove("dim");
  for(const e of E){ e.el.classList.remove("hot"); e.el.classList.remove("dim"); }
  refreshLabels(); document.getElementById("panel").classList.remove("open");
}
svg.addEventListener("click",()=>deselect());
function showPanel(n){
  const outgoing=E.filter(e=>e.s===n).map(e=>e.t);
  const incoming=E.filter(e=>e.t===n).map(e=>e.s);
  const linkList=arr=>arr.length?arr.map(m=>`<a class="link" data-id="${esc(m.id)}">→ ${esc(m.title)}</a>`).join(""):`<div class="path">none</div>`;
  const tags=n.tags.length?`<div class="tags">${n.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join("")}</div>`:"";
  const tierLabel={"human-reviewed":"● human-reviewed","machine-confirmed":"◐ machine-confirmed","unverified":"○ unverified"}[n.trust]||"";
  const meta=n.reserved?"":`<div class="meta"><span class="pill trust-${esc(n.trust.split("-")[0])}">${tierLabel}</span>`+
    (n.status&&n.status!=="stable"?`<span class="pill">${esc(n.status)}</span>`:"")+
    (n.stale?`<span class="pill stalep">stale · ${esc(n.stale_after)}</span>`:"")+`</div>`;
  const prov=n.reserved?"":(`<div class="prov">links · in ${n.in_deg} · out ${n.out_deg}`+
    `${n.in_deg===0?" · unreferenced":""}${n.degree===0?" · isolated":""} `+
    `<span class="path">(concept-only; index links excluded)</span></div>`+
    (n.generated&&n.generated.by?`<div class="prov">generated · ${esc(n.generated.by)}${n.generated.at?" · "+esc(n.generated.at):""}</div>`:"")+
    (n.verified&&n.verified.length?`<div class="prov">verified · ${n.verified.map(v=>esc(v.by||"?")).join(", ")}</div>`:""));
  const srcBlock=(n.sources&&n.sources.length)?`<h5>Sources (${n.sources.length})</h5>`+
    n.sources.map(s=>`<div class="prov">${esc(s.title||s.resource||s.id||"source")}${s.resource?" — "+esc(s.resource):""}</div>`).join(""):"";
  const p=document.getElementById("panel");
  p.innerHTML=`<button class="close" aria-label="Close">×</button>`+
    `<div class="type">${esc(n.type)}</div><h2>${esc(n.title)}</h2>`+
    `<div class="path">${esc(n.id)}</div>`+meta+prov+
    (n.description?`<div class="desc">${esc(n.description)}</div>`:"")+tags+
    (n.excerpt?`<div class="excerpt">${esc(n.excerpt)}</div>`:"")+srcBlock+
    `<h5>Links out (${outgoing.length})</h5>${linkList(outgoing)}`+
    `<h5>Linked from (${incoming.length})</h5>${linkList(incoming)}`;
  p.classList.add("open");
  p.querySelector(".close").onclick=()=>deselect();
  p.querySelectorAll("a.link").forEach(a=>a.onclick=()=>{ const m=byId.get(a.dataset.id);
    if(m){ tx=W/2-m.x*scale; ty=H/2-m.y*scale; applyView(); select(m); }});
}

// --- header / legend / search ----------------------------------------------
function updateHeader(){
  document.getElementById("lens").innerHTML = DATA.query ? `lens <b>${esc(DATA.query)}</b>` : `full graph`;
  const s=lastStats;
  document.getElementById("counts").innerHTML =
    `<span><b id="shownCount">${AN.length}</b> shown</span>`+
    `<span><b>${s.concepts}</b> concepts</span>`+
    `<span><b>${s.links}</b> links</span>`+
    `<span><b>${s.unreferenced}</b> unreferenced</span>`+
    `<span><b>${s.isolated}</b> isolated</span>`+
    (s.broken?`<span><b>${s.broken}</b> broken</span>`:``);
}
function buildLegend(){
  const counts={}; for(const n of N) counts[n.type]=(counts[n.type]||0)+1;
  const box=document.getElementById("legend-items"); box.innerHTML="";
  for(const t of Object.keys(counts).sort()){
    const row=document.createElement("div"); row.className="leg"+(hidden.has(t)?" off":"");
    row.innerHTML=`<span class="sw" style="background:${colorFor(t)}"></span><span>${esc(t)}</span><span class="n">${counts[t]}</span>`;
    row.onclick=()=>{ if(hidden.has(t))hidden.delete(t); else hidden.add(t);
      row.classList.toggle("off"); applyTypeFilter(); };
    box.appendChild(row);
  }
}
function applyTypeFilter(){ applyHiddenDisplay(); recomputeActive();
  const sc=document.getElementById("shownCount"); if(sc) sc.textContent=AN.length;
  fitted=false; kick(); }
document.getElementById("search").addEventListener("input",e=>{
  const q=e.target.value.trim().toLowerCase();
  for(const n of N){ const hit=!q || n.title.toLowerCase().includes(q)
    || n.type.toLowerCase().includes(q) || n.id.toLowerCase().includes(q)
    || n.tags.join(" ").toLowerCase().includes(q);
    n.el.classList.toggle("dim", q && !hit);
    n.label.style.display = q ? (hit?"":"none") : (labelVisible(n)?"":"none"); }
});
addEventListener("resize",()=>{ W=innerWidth; H=innerHeight; });

// --- boot: render the baked-in payload, then stream live updates ------------
applyData(DATA, {fit:true});
function flashLive(){ const d=document.getElementById("live"); d.classList.remove("on");
  void d.offsetWidth; d.classList.add("on"); }
try{
  const es=new EventSource("/events");
  es.onmessage=ev=>{ try{ applyData(JSON.parse(ev.data)); flashLive(); }catch(_){} };
}catch(_){}
</script>
</body>
</html>
"""


# --- serving (ThreadingHTTPServer + SSE + mtime-watch thread) ----------------

def serve(host, port, vault, query, no_reserved, open_browser):
    import http.server
    import socketserver
    import threading
    import time
    import webbrowser

    def payload_bytes():
        return json.dumps(graph_payload(vault, query, no_reserved),
                          ensure_ascii=True).encode("utf-8")

    state = {"payload": payload_bytes()}
    page = render_html(json.loads(state["payload"]))
    page_bytes = page.encode("utf-8")
    cond = threading.Condition()
    version = {"v": 0}
    stop = threading.Event()

    def watcher():
        sig = vault_signature(vault)
        while not stop.wait(1.0):
            try:
                ns = vault_signature(vault)
            except OSError:
                continue
            if ns != sig:
                sig = ns
                try:
                    p = payload_bytes()
                except Exception:
                    continue
                with cond:
                    state["payload"] = p
                    version["v"] += 1
                    cond.notify_all()

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, body, ctype):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(page_bytes, "text/html; charset=utf-8")
            elif path == "/api/graph":
                self._send(state["payload"], "application/json")
            elif path == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                last = -1
                try:
                    while not stop.is_set():
                        with cond:
                            if version["v"] == last:
                                cond.wait(timeout=15)
                            cur, payload = version["v"], state["payload"]
                        if cur != last:
                            last = cur
                            self.wfile.write(b"data: " + payload + b"\n\n")
                        else:
                            self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
            else:
                self.send_error(404)

    socketserver.TCPServer.allow_reuse_address = True
    httpd = http.server.ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=watcher, daemon=True).start()
    bound_port = httpd.server_address[1]
    url = f"http://{host}:{bound_port}/"
    print(f"OKF graph server (live): {url}")
    print(f"  watching {vault} — edits update the open page. pid {os.getpid()}; Ctrl-C to stop.")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        stop.set()
        httpd.server_close()


def main():
    ap = argparse.ArgumentParser(description="Render an OKF vault as a live interactive graph.")
    ap.add_argument("vault")
    ap.add_argument("--query", default="")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--no-reserved", action="store_true",
                    help="exclude reserved index.md/log.md navigation files")
    ap.add_argument("--dump", help="write HTML to this path and exit (no server)")
    args = ap.parse_args()

    vault = os.path.abspath(args.vault)
    if not os.path.isdir(vault):
        print(f"error: not a directory: {vault}", file=sys.stderr)
        return 2

    payload = graph_payload(vault, args.query, args.no_reserved)
    if args.dump:
        with open(args.dump, "w", encoding="utf-8") as f:
            f.write(render_html(payload))
        print(f"wrote {args.dump} ({payload['stats']['concepts']} concepts, "
              f"{payload['stats']['shown_edges']} edges shown)")
        return 0

    serve(args.host, args.port, vault, args.query, args.no_reserved, not args.no_open)
    return 0


if __name__ == "__main__":
    sys.exit(main())
