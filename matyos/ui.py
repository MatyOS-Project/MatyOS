"""The MatyOS research console — a local web app for a working mathematician and a
curious non-specialist alike. Zero runtime dependencies (Python stdlib only).

Run ``matyos-ui`` and open http://localhost:8000 .

An app shell (sidebar + views): an Overview landing, an Explore console for number
sequences, the classified Graph-patterns shortlist with a live Lean **Prove**
button, a Hard-problems workbench (state / verify-finite / and a clear statement of
what MatyOS cannot do), and a How-it-works page. The server is threaded so a slow
proof never freezes the page. Nothing here ever reports a famous conjecture solved.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---- cached, deterministic data ------------------------------------------------

_CONJ_CACHE: list | None = None
_ASSET_CACHE: dict = {}


def _asset(rel: str) -> bytes | None:
    """Read a packaged asset under matyos/assets/ (e.g. 'logo.png', 'icons/hyp.svg')."""
    if rel not in _ASSET_CACHE:
        try:
            from importlib.resources import files
            target = files("matyos") / "assets"
            for part in rel.split("/"):
                target = target / part
            _ASSET_CACHE[rel] = target.read_bytes()
        except Exception:
            _ASSET_CACHE[rel] = b""
    return _ASSET_CACHE[rel] or None


def _logo_bytes() -> bytes | None:
    """The MatyOS mark (kept for backward compatibility)."""
    return _asset("logo.png")


def _conjectures() -> list:
    """Classified graph conjectures, each annotated with whether mathlib can check
    it (so the UI knows when a live Prove button will actually run). Computed once."""
    global _CONJ_CACHE
    if _CONJ_CACHE is None:
        from matyos.discovery import graph as g
        from matyos.discovery import lean
        rows = g.classified_search()
        for r in rows:
            r["mathlib_ready"] = lean.graph_statement(r["statement"])["mathlib_ready"]
        _CONJ_CACHE = rows
    return _CONJ_CACHE


# ---- the page ------------------------------------------------------------------

_PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MatyOS — research console</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
<style>
 :root{--bg:#f5f7fb;--surface:#fff;--ink:#0e1526;--muted:#64708a;--line:#e7eaf1;
  --brand:#4f46e5;--brand-d:#4338ca;--brand-soft:#eef2ff;--sidebar:#0d1424;--sidebar-2:#111a2e;
  --known:#12805c;--known-bg:#e6f6ef;--derived:#2563eb;--derived-bg:#e9f1fe;
  --candidate:#e0620d;--candidate-bg:#fdefe4;--ok:#12805c;--bad:#dc2626;
  --mono:'JetBrains Mono',ui-monospace,Menlo,monospace;--sans:'Inter',-apple-system,'Segoe UI',Roboto,sans-serif;
  --sh:0 1px 2px rgba(14,21,38,.04),0 6px 22px rgba(14,21,38,.07)}
 *{box-sizing:border-box}html,body{margin:0}
 body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:14.5px;line-height:1.55;-webkit-font-smoothing:antialiased}
 code,.mono{font-family:var(--mono)}
 .app{display:grid;grid-template-columns:250px 1fr;min-height:100vh}
 /* sidebar */
 .side{background:linear-gradient(180deg,var(--sidebar),var(--sidebar-2));color:#c3ccdd;
   position:sticky;top:0;height:100vh;display:flex;flex-direction:column;padding:18px 14px;gap:6px}
 .brand{display:flex;align-items:center;gap:11px;padding:6px 8px 14px}
 .brand .mark{width:38px;height:38px;border-radius:10px;background:#fff;display:grid;place-items:center;flex:none}
 .brand .mark img{width:28px;height:28px}
 .brand b{font-size:17px;color:#fff;font-weight:700;display:block;letter-spacing:-.01em}
 .brand small{font-size:11px;color:#8896b3}
 .side nav{display:flex;flex-direction:column;gap:3px;margin-top:6px}
 .side nav button{display:flex;align-items:center;gap:10px;width:100%;text-align:left;
   font:600 13.5px var(--sans);color:#aeb9d1;background:none;border:0;border-radius:9px;padding:10px 11px;cursor:pointer}
 .side nav button:hover{background:rgba(255,255,255,.06);color:#fff}
 .side nav button.on{background:var(--brand);color:#fff}
 .side nav button .i{width:18px;text-align:center;opacity:.9}
 .side-foot{margin-top:auto;padding:12px 8px 4px;font-size:12px;color:#8896b3;border-top:1px solid rgba(255,255,255,.08)}
 .side-foot a{color:#c3ccdd;text-decoration:none}.side-foot a:hover{color:#fff}
 .vpill{display:inline-block;background:rgba(255,255,255,.1);color:#dbe2f0;border-radius:999px;padding:2px 9px;font-weight:600;margin-bottom:8px}
 /* main */
 .content{min-width:0}
 .topbar{position:sticky;top:0;z-index:5;background:rgba(245,247,251,.85);backdrop-filter:blur(8px);
   border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px;padding:14px 30px}
 .topbar h2{font-size:16px;margin:0;font-weight:700}
 .pill{font-size:11.5px;font-weight:600;padding:3px 10px;border-radius:999px;background:var(--brand-soft);color:var(--brand-d)}
 .pill.honest{background:var(--candidate-bg);color:var(--candidate);margin-left:auto}
 .views{padding:26px 30px 60px;max-width:1080px}
 .view{display:none}.view.on{display:block;animation:f .25s ease}
 @keyframes f{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
 @media(prefers-reduced-motion){.view.on{animation:none}}
 /* hero */
 .hero{display:grid;grid-template-columns:1.25fr .75fr;gap:28px;align-items:center;
   background:linear-gradient(135deg,#111a2e,#1f2b4d);color:#eaeefb;border-radius:20px;padding:38px 36px;box-shadow:var(--sh)}
 .eyebrow{font-size:11.5px;font-weight:700;letter-spacing:.14em;color:#8fa0d8}
 .hero h1{font-size:38px;line-height:1.08;margin:10px 0 12px;font-weight:800;letter-spacing:-.02em;color:#fff;text-wrap:balance}
 .hero p{color:#c3cbe6;font-size:14.5px;max-width:52ch;margin:0 0 20px}
 .cta{display:flex;gap:10px;flex-wrap:wrap}
 .go{font:600 14px var(--sans);background:var(--brand);color:#fff;border:0;border-radius:10px;padding:11px 20px;cursor:pointer;text-decoration:none;display:inline-block}
 .go:hover{background:#5b52ff}.go.ghost{background:rgba(255,255,255,.08);color:#fff;border:1px solid rgba(255,255,255,.18)}
 .go.sm{padding:6px 12px;font-size:12.5px}
 .hero-art{display:grid;place-items:center}
 .orb{width:200px;height:200px;border-radius:50%;background:radial-gradient(circle at 34% 30%,#3a4a86,#0d1424 72%);
   display:grid;place-items:center;box-shadow:inset 0 0 40px rgba(120,140,220,.35),0 12px 40px rgba(0,0,0,.35)}
 .orb img{width:104px;height:104px;filter:invert(1)}
 .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:20px 0}
 .stat{background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:16px 18px;box-shadow:var(--sh)}
 .stat .n{font-size:26px;font-weight:800;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
 .stat .l{font-size:12px;color:var(--muted);margin-top:2px}
 .feat{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:8px}
 .fcard{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px 20px;box-shadow:var(--sh)}
 .fcard .ic{width:34px;height:34px;border-radius:9px;background:var(--brand-soft);color:var(--brand-d);display:grid;place-items:center;font-size:17px;margin-bottom:10px}
 .fcard h3{margin:0 0 5px;font-size:14.5px}.fcard p{margin:0;font-size:13px;color:var(--muted)}
 /* generic cards */
 .card{background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:var(--sh);padding:22px 24px;margin-bottom:18px}
 .card h2{font-size:16px;margin:0 0 4px}.lead{color:var(--muted);font-size:13.5px;margin:0 0 16px}
 .row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
 input[type=text],input[type=number]{font-family:var(--mono);font-size:14px;padding:11px 13px;border:1px solid var(--line);border-radius:10px;background:#fbfcff;flex:1;min-width:220px}
 input:focus{outline:2px solid var(--brand-soft);border-color:var(--brand)}
 .chips{display:flex;gap:7px;flex-wrap:wrap;margin:11px 0 0}
 .chip{font:500 12.5px var(--mono);background:#eef1f8;border:1px solid var(--line);border-radius:999px;padding:5px 12px;cursor:pointer}
 .chip:hover{background:var(--brand-soft)}
 .verdict{margin-top:15px;display:grid;gap:10px}
 .vitem{border:1px solid var(--line);border-left:4px solid var(--muted);border-radius:11px;padding:13px 15px;background:#fbfcff}
 .vitem.found{border-left-color:var(--ok)}.vitem.mystery{border-left-color:var(--candidate)}
 .vitem .big{font-size:15px;font-weight:600}
 .legend{font-size:12.5px;color:var(--muted);display:flex;gap:16px;flex-wrap:wrap;margin-top:8px}
 .lg{display:inline-flex;align-items:center;gap:6px}.dot{width:9px;height:9px;border-radius:3px}
 table{width:100%;border-collapse:collapse;margin-top:10px}
 td,th{padding:10px 8px;text-align:left;border-bottom:1px solid var(--line);vertical-align:middle}
 th{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;font-weight:600}
 td.ineq .katex{font-size:1.06em}
 .badge{font-size:11px;font-weight:700;padding:2px 9px;border-radius:999px;white-space:nowrap}
 .badge.known{color:var(--known);background:var(--known-bg)}.badge.derived{color:var(--derived);background:var(--derived-bg)}
 .badge.candidate{color:var(--candidate);background:var(--candidate-bg)}
 .prv{font:600 12px var(--sans);padding:6px 12px;border-radius:8px;border:1px solid var(--line);background:#fff;color:var(--brand-d);cursor:pointer}
 .prv:hover{background:var(--brand-soft)}.prv:disabled{opacity:.5}
 .presult{font-size:12px;margin-top:4px;font-family:var(--mono)}.ok{color:var(--ok)}.bad{color:var(--bad)}
 .prob{border:1px solid var(--line);border-radius:13px;padding:17px 19px;margin-bottom:14px;background:#fbfcff}
 .prob h3{margin:0 0 4px;font-size:15px}.prob .can{color:var(--known);font-size:13px}.prob .cant{color:var(--bad);font-size:13px}
 .mathline{margin:9px 0 10px;overflow-x:auto}
 details{margin-top:10px}summary{cursor:pointer;color:var(--brand-d);font-size:13px;font-weight:600}
 pre{background:#0d1424;color:#e2e8f0;padding:13px 15px;border-radius:10px;overflow:auto;font-family:var(--mono);font-size:12px;line-height:1.5}
 .real{display:flex;gap:10px;flex-wrap:wrap}.rl{flex:1;min-width:150px;border-radius:11px;padding:13px 15px;border:1px solid var(--line)}
 .rl b{font-size:13.5px}.rl span{font-size:12.5px;color:var(--muted);display:block;margin-top:3px}
 .rl.t{background:var(--known-bg)}.rl.r{background:var(--candidate-bg)}.rl.f{background:#fdeaea}
 .flow{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:10px}
 .step{display:flex;flex-direction:column;align-items:center;gap:7px;border:1px solid var(--line);border-radius:12px;padding:14px 12px;background:#fff;flex:1;min-width:100px}
 .step img{width:40px;height:40px}.step b{font-size:13px}.step span{font-size:11.5px;color:var(--muted);text-align:center}
 .arrow{color:var(--muted);font-size:20px}
 .spin{display:inline-block;width:13px;height:13px;border:2px solid var(--line);border-top-color:var(--brand);border-radius:50%;animation:sp .7s linear infinite;vertical-align:-2px}
 @keyframes sp{to{transform:rotate(360deg)}}
 .help dt{font-weight:600;margin-top:12px}.help dd{margin:2px 0 0;color:var(--muted)}
 @media(max-width:860px){.app{grid-template-columns:1fr}.side{position:static;height:auto;flex-direction:row;flex-wrap:wrap;align-items:center}
   .side nav{flex-direction:row;flex-wrap:wrap;margin:0}.side-foot{display:none}.brand{padding:6px}
   .hero{grid-template-columns:1fr}.hero-art{display:none}.stats,.feat{grid-template-columns:1fr 1fr}}
</style></head><body>
<div class="app">
 <aside class="side">
   <div class="brand"><div class="mark"><img src="/logo.png" alt="" onerror="this.style.display='none'"></div>
     <div><b>MatyOS</b><small>research console</small></div></div>
   <nav>
     <button class="on" data-view="overview"><span class="i">◇</span> Overview</button>
     <button data-view="explore"><span class="i">∿</span> Explore a sequence</button>
     <button data-view="graph"><span class="i">▦</span> Graph patterns</button>
     <button data-view="problems"><span class="i">★</span> Hard problems</button>
     <button data-view="how"><span class="i">❍</span> How it works</button>
     <button data-view="help"><span class="i">?</span> What is this?</button>
   </nav>
   <div class="side-foot"><span class="vpill">v{{VERSION}}</span><br>
     <a href="https://github.com/MatyOS-Project/MatyOS" target="_blank" rel="noopener">GitHub</a> ·
     <a href="https://pypi.org/project/matyos/" target="_blank" rel="noopener">PyPI</a></div>
 </aside>
 <div class="content">
   <div class="topbar"><h2 id="crumb">Overview</h2><span class="pill honest">honest · never fakes a proof</span></div>
   <div class="views">

   <section class="view on" id="overview">
     <div class="hero">
       <div class="hero-txt">
         <div class="eyebrow">MATHEMATICAL DISCOVERY, HONESTLY</div>
         <h1>The scientific method, as software.</h1>
         <p>MatyOS lends any AI model the discipline of real science — hypothesize, test, try to refute, prove — with every claim checked by a small trusted kernel. It finds small true patterns and proves the easy ones. It does <b>not</b> solve famous open problems, and it says so.</p>
         <div class="cta"><button class="go" onclick="showView('explore')">Open the console →</button>
           <a class="go ghost" href="https://github.com/MatyOS-Project/MatyOS" target="_blank" rel="noopener">View on GitHub</a></div>
       </div>
       <div class="hero-art"><div class="orb"><img src="/logo.png" alt="MatyOS"></div></div>
     </div>
     <div class="stats" id="stats">
       <div class="stat"><div class="n">—</div><div class="l">known bounds</div></div>
       <div class="stat"><div class="n">—</div><div class="l">open candidates</div></div>
       <div class="stat"><div class="n">20</div><div class="l">graph invariants</div></div>
       <div class="stat"><div class="n">Lean</div><div class="l">proof-checked</div></div>
     </div>
     <div class="feat">
       <div class="fcard"><div class="ic">∿</div><h3>Discovery engine</h3><p>Cross-domain transfer, PSLQ closed-form detection with a significance gate, live OEIS prior-art checks — keeping only the surprising and not-already-known.</p></div>
       <div class="fcard"><div class="ic">✓</div><h3>Trusted verifier</h3><p>A small dependently-typed kernel in the Lean/Coq/Agda tradition. Every proof reduces to a term the tiny trusted kernel checks. Nothing is “assumed proven”.</p></div>
       <div class="fcard"><div class="ic">⧉</div><h3>MCP substrate</h3><p><code>pip install "matyos[mcp]"</code> and any model can call MatyOS to verify closed forms, check OEIS, check proofs, and run the discovery loop.</p></div>
     </div>
   </section>

   <section class="view" id="explore">
     <div class="card">
       <h2>Give MatyOS a number sequence</h2>
       <p class="lead">Type the first several terms of an integer sequence. MatyOS looks for a hidden pattern and tells you honestly: a real formula, a “mystery” constant, or nothing — it never makes one up.</p>
       <div class="row"><input type="text" id="seq" value="0, 1, 1, 2, 3, 5, 8, 13, 21, 34">
         <button class="go" id="discBtn" onclick="discover()">Discover</button></div>
       <div class="chips">
         <span class="chip" onclick="setSeq('0,1,1,2,3,5,8,13,21,34')">Fibonacci</span>
         <span class="chip" onclick="setSeq('2,3,5,7,11,13,17,19,23,29')">Primes</span>
         <span class="chip" onclick="setSeq('1,4,9,16,25,36,49')">Squares</span>
         <span class="chip" onclick="setSeq('1,3,4,7,11,18,29,47')">Lucas</span></div>
       <div class="verdict" id="disc"></div>
     </div>
   </section>

   <section class="view" id="graph">
     <div class="card">
       <h2>Graph patterns MatyOS found</h2>
       <p class="lead">Each row is a rule “quantity A is never bigger than quantity B”, tested on many graphs and sorted by how well MatyOS understands it.</p>
       <div class="stats" id="gstat" style="margin:0 0 14px"></div>
       <div class="legend">
         <span class="lg"><span class="dot" style="background:var(--candidate)"></span><b>candidate</b> — can’t explain it yet</span>
         <span class="lg"><span class="dot" style="background:var(--derived)"></span><b>derived</b> — follows from known rules</span>
         <span class="lg"><span class="dot" style="background:var(--known)"></span><b>known</b> — an established theorem</span></div>
       <details style="margin-top:10px"><summary>Symbol key</summary><div id="symkey" class="legend" style="margin-top:8px"></div></details>
       <div id="conj" style="margin-top:12px">Loading…</div>
     </div>
   </section>

   <section class="view" id="problems">
     <div class="card">
       <h2>Famous unsolved problems — the honest view</h2>
       <div class="vitem mystery" style="margin-bottom:16px">MatyOS can <b>state</b> these precisely and <b>check them on many numbers</b>, but it <b>cannot prove</b> them — and it will never say it did. Checking a range is evidence, not a proof.</div>
       <div id="probs">Loading…</div>
     </div>
   </section>

   <section class="view" id="how">
     <div class="card"><h2>The <code>realistic</code> idea — uncertainty is first-class</h2>
       <p class="lead">Real work (especially an LLM’s) is full of plausible-but-unproven steps. MatyOS uses a three-valued logic so conjecture and certainty never get confused.</p>
       <div class="real"><div class="rl t"><b>TRUE</b><span>proven — the kernel checked a term</span></div>
         <div class="rl r"><b>REALISTIC</b><span>found and stable, but unproven — a conjecture</span></div>
         <div class="rl f"><b>FALSE</b><span>refuted by a counterexample</span></div></div></div>
     <div class="card"><h2>The scientific-method workflow</h2>
       <p class="lead">A MatyOS project moves a claim from a guess to a checked result — each stage its own file type.</p>
       <div class="flow">
         <div class="step"><img src="/assets/icons/hyp.svg" alt=""><b>.hyp</b><span>hypothesis</span></div><span class="arrow">→</span>
         <div class="step"><img src="/assets/icons/thm.svg" alt=""><b>.thm</b><span>theorem stated</span></div><span class="arrow">→</span>
         <div class="step"><img src="/assets/icons/test.svg" alt=""><b>.test</b><span>tested / refuted</span></div><span class="arrow">→</span>
         <div class="step"><img src="/assets/icons/prf.svg" alt=""><b>.prf</b><span>proof, kernel-checked</span></div></div></div>
   </section>

   <section class="view" id="help">
     <div class="card"><h2>What is MatyOS, in plain words?</h2>
       <dl class="help">
         <dt>What it does</dt><dd>Looks for patterns in numbers and in graphs, then checks whether each is really true.</dd>
         <dt>Why “honest”?</dt><dd>It labels everything — real formula, known result, mystery, or “no pattern” — and refuses to invent an answer or claim a famous problem is solved.</dd>
         <dt>candidate / derived / known</dt><dd><b>Known</b> = a proven theorem. <b>Derived</b> = follows from things it knows. <b>Candidate</b> = holds on every test but MatyOS can’t explain it — where something new could hide.</dd>
         <dt>The Prove button</dt><dd>Sends a rule to Lean (a real proof-checker) with the mathlib library; a green ✓ names the theorem it used, otherwise it honestly says “open”.</dd>
         <dt>The Verify button</dt><dd>Checks a famous conjecture on every number up to a limit — green means no counterexample in that range. Still not a proof.</dd></dl></div>
   </section>

   </div>
 </div>
</div>
<script>
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
async function jget(u){return (await fetch(u)).json()}
async function jpost(u,o){return (await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)})).json()}
const CRUMB={overview:'Overview',explore:'Explore a sequence',graph:'Graph patterns',problems:'Hard problems',how:'How it works',help:'What is this?'};
function showView(v){$$('.side nav button').forEach(b=>b.classList.toggle('on',b.dataset.view===v));
  $$('.view').forEach(p=>p.classList.toggle('on',p.id===v));$('#crumb').textContent=CRUMB[v]||'';window.scrollTo(0,0);}
$$('.side nav button').forEach(b=>b.onclick=()=>showView(b.dataset.view));
function setSeq(s){$('#seq').value=s.split(',').join(', ')}

const SYM={order:'n',size:'m',max_degree:'\\Delta',min_degree:'\\delta',avg_degree:'\\bar d',triangles:'t',
 diameter:'\\operatorname{diam}',radius:'r',independence_number:'\\alpha',clique_number:'\\omega',
 chromatic_number:'\\chi',vertex_cover_number:'\\tau',domination_number:'\\gamma',matching_number:'\\nu',
 vertex_connectivity:'\\kappa',edge_connectivity:'\\lambda',degeneracy:'\\operatorname{degen}',girth:'g',
 average_eccentricity:'\\overline{\\operatorname{ecc}}',average_distance:'\\mu',total_domination_number:'\\gamma_t',
 edge_cover_number:'\\rho',spectral_radius:'\\lambda_1',energy:'\\mathcal{E}',algebraic_connectivity:'a',laplacian_spectral_radius:'\\mu_1'};
function symTex(n){const s=SYM[n]||n.replace(/_/g,'\\_');return (n==='order'||n==='size')?s:s+'(G)';}
function kx(t,d){try{return katex.renderToString(t,{throwOnError:false,displayMode:!!d});}catch(e){return t;}}
function ruleTex(st){const p=st.split(' <= ');return kx(symTex(p[0])+' \\le '+symTex(p[1]));}
function cfTex(cf){if(!cf)return '';let s=cf.replace(/sqrt(\d+)/g,'\\sqrt{$1}').replace(/\bpi\b/g,'\\pi')
  .replace(/\^(\d+)/g,'^{$1}').replace(/\bln(\d+)/g,'\\ln $1').replace(/\bzeta(\d+)/g,'\\zeta($1)')
  .replace(/\bgamma\b/g,'\\gamma').replace(/\bcatalan\b/g,'\\mathrm{G}');return kx(s);}

async function discover(){
  const btn=$('#discBtn');btn.disabled=true;
  const seq=$('#seq').value.split(',').map(s=>parseInt(s.trim())).filter(x=>!isNaN(x));
  $('#disc').innerHTML='<div class="lead"><span class="spin"></span> Searching…</div>';
  try{const d=await jpost('/api/discover',{seq});
    if(!d.candidates||!d.candidates.length){$('#disc').innerHTML='<div class="vitem"><div class="big">No formula found</div><div class="lead" style="margin:0">Often the honest answer — many sequences have no closed form.</div></div>';}
    else{$('#disc').innerHTML=d.candidates.map(r=>{const cf=r.closed_form||'';const lab=(r.label&&r.label.status)||'';
      const known=r.verification&&r.verification.prior_art;let cls='',big='No formula for this one';
      if(cf){cls='found';big='Formula: '+cfTex(cf)}else if(lab.includes('mystery')){cls='mystery';big='Stable “mystery” value (no known formula)'}
      return `<div class="vitem ${cls}"><div class="big">${big}</div><div class="lead" style="margin:2px 0 0">honest label: <b>${lab||'—'}</b>${known?(' · already known: '+known):''}</div></div>`;}).join('');}
  }catch(e){$('#disc').innerHTML='<div class="vitem bad">error: '+e+'</div>'}
  btn.disabled=false;
}

(async()=>{
  const c=(await jget('/api/conjectures')).conjectures;
  const by=n=>c.filter(x=>x.novelty===n).length;
  $('#stats').children[0].querySelector('.n').textContent=by('known');
  $('#stats').children[1].querySelector('.n').textContent=by('candidate');
  $('#gstat').innerHTML=[['candidate',by('candidate')],['derived',by('derived')],['known',by('known')],['total',c.length]]
    .map(([k,v])=>`<div class="stat"><div class="n" style="color:${k==='total'?'var(--ink)':'var(--'+k+')'}">${v}</div><div class="l">${k}</div></div>`).join('');
  let h='<table><tr><th>rule (A ≤ B)</th><th>status</th><th>held / tight</th><th>check with Lean</th></tr>';
  for(const r of c){h+=`<tr><td class="ineq" title="${r.statement}">${ruleTex(r.statement)}</td>`+
    `<td><span class="badge ${r.novelty}">${r.novelty}</span></td><td class="mono">${r.held_on} / ${r.tight_on}</td>`+
    `<td><button class="prv" onclick="prove(this,'${r.statement}',${r.mathlib_ready?1:0})">Prove</button><div class="presult"></div></td></tr>`;}
  $('#conj').innerHTML=h+'</table>';
  const used=new Set();c.forEach(r=>r.statement.split(' <= ').forEach(x=>used.add(x)));
  $('#symkey').innerHTML=[...used].sort().map(n=>`<span class="lg">${kx(symTex(n))}<span style="color:var(--muted)">= ${n.replace(/_/g,' ')}</span></span>`).join('');
  const MATH={goldbach:'\\forall\\,n>2\\ \\text{even},\\ \\exists\\,p,q\\ \\text{prime}:\\ n=p+q',
    twin_primes:'\\forall\\,N,\\ \\exists\\,p>N:\\ p\\ \\text{and}\\ p+2\\ \\text{prime}',
    collatz:'\\forall\\,n>0,\\ \\exists\\,k:\\ C^{k}(n)=1',
    riemann:'\\zeta(s)=0,\\ 0<\\Re(s)<1\\ \\Rightarrow\\ \\Re(s)=\\tfrac12'};
  const p=(await jget('/api/problems')).problems;
  $('#probs').innerHTML=p.map(x=>`<div class="prob"><h3>${x.name}</h3>`+
    (MATH[x.key]?`<div class="mathline">${kx(MATH[x.key],true)}</div>`:'')+
    `<div class="can">✓ MatyOS can: ${x.matyos_can.join(', ')}.</div><div class="cant">✗ Cannot: ${x.matyos_cannot}.</div>`+
    (x.finite_checkable?`<div class="row" style="margin-top:10px"><input type="number" id="n_${x.key}" value="1000" min="4" style="max-width:130px">`+
      `<button class="prv" onclick="verify('${x.key}',this)">Verify up to N</button><span class="presult" id="v_${x.key}"></span></div>`:
      `<div class="lead" style="margin:8px 0 0">No finite check settles this${x.key==='riemann'?' (needs the zeta function)':' (it asserts infinitely many cases)'}.</div>`)+
    `<details><summary>Formal Lean statement</summary><pre>${x.lean_statement.replace(/</g,'&lt;')}</pre></details></div>`).join('');
})();

async function prove(btn,stmt,ready){
  const out=btn.nextElementSibling;
  if(!ready){out.innerHTML='<span style="color:var(--muted)">— can’t check yet: uses an invariant mathlib doesn’t define</span>';return;}
  btn.disabled=true;out.innerHTML='<span class="spin"></span> proving with Lean… (up to ~2 min)';
  try{const r=await jpost('/api/prove',{statement:stmt});
    if(r.status==='proved')out.innerHTML='<span class="ok">✓ proved'+(r.lemma?(' via '+r.lemma):(' by '+r.tactic))+'</span>';
    else if(r.status==='open')out.innerHTML='<span>— open (automation didn’t close it; a human proof is needed)</span>';
    else out.innerHTML='<span class="bad">'+(r.note||r.status)+'</span>';
  }catch(e){out.innerHTML='<span class="bad">error: '+e+'</span>'}
  btn.disabled=false;
}
async function verify(key,btn){
  const out=$('#v_'+key),n=parseInt($('#n_'+key).value)||1000;btn.disabled=true;out.innerHTML='<span class="spin"></span> checking…';
  try{const r=await jpost('/api/verify_finite',{problem:key,upto:n});
    if(r.error)out.innerHTML='<span class="bad">'+r.error+'</span>';
    else out.innerHTML=r.holds?`<span class="ok">✓ holds for all up to ${r.checked_up_to} — evidence, not a proof</span>`:`<span class="bad">counterexample at ${r.counterexample}!</span>`;
  }catch(e){out.innerHTML='<span class="bad">error: '+e+'</span>'}
  btn.disabled=false;
}
</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            import matyos
            return self._send(200, _PAGE.replace("{{VERSION}}", matyos.__version__),
                              "text/html; charset=utf-8")
        if self.path == "/logo.png":
            png = _asset("logo.png")
            return self._send(200 if png else 404, png or b"", "image/png")
        if self.path.startswith("/assets/"):
            rel = self.path[len("/assets/"):].split("?")[0]
            if ".." in rel or rel.startswith("/"):
                return self._send(404, json.dumps({"error": "bad path"}))
            data = _asset(rel)
            ct = "image/svg+xml" if rel.endswith(".svg") else "image/png"
            return self._send(200 if data else 404, data or b"", ct)
        if self.path == "/api/conjectures":
            return self._send(200, json.dumps({"conjectures": _conjectures()}))
        if self.path == "/api/problems":
            from matyos.problems import famous as F
            probs = []
            for k in F.REGISTRY:
                s = F.status(k)
                s["key"] = k
                s["finite_checkable"] = k in ("goldbach", "collatz")
                probs.append(s)
            return self._send(200, json.dumps({"problems": probs}))
        return self._send(404, json.dumps({"error": "not found"}))

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_POST(self):
        try:
            if self.path == "/api/discover":
                seq = [int(x) for x in self._body().get("seq", [])]
                if len(seq) < 4:
                    return self._send(200, json.dumps({"candidates": [], "note": "give at least 4 integers"}))
                from matyos.discovery.objects import Sequence
                from matyos.discovery.engine import DiscoveryEngine
                recs = DiscoveryEngine(min_score=0.0).records([Sequence.of(seq, name="ui")])
                return self._send(200, json.dumps({"candidates": recs[:5]}))
            if self.path == "/api/prove":
                from matyos.discovery import lean
                gs = lean.graph_statement(self._body().get("statement", ""))
                if not gs["mathlib_ready"]:
                    return self._send(200, json.dumps({"status": "unavailable",
                                      "note": "this rule's invariants are not in mathlib yet"}))
                return self._send(200, json.dumps(lean.try_prove(gs["lean_statement"], timeout=150)))
            if self.path == "/api/verify_finite":
                p = self._body()
                from matyos.problems import famous as F
                try:
                    ev = F.verify_finite(p.get("problem", ""), int(p.get("upto", 1000)))
                    return self._send(200, json.dumps({"holds": ev.holds,
                                      "checked_up_to": ev.checked_up_to, "counterexample": ev.counterexample}))
                except (ValueError, KeyError) as e:
                    return self._send(200, json.dumps({"error": str(e)}))
            return self._send(404, json.dumps({"error": "not found"}))
        except Exception as e:
            return self._send(200, json.dumps({"error": str(e)}))


def serve(port: int = 8000, host: str = "127.0.0.1") -> None:
    httpd = ThreadingHTTPServer((host, port), _Handler)
    print(f"MatyOS research console → http://{host}:{port}  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="MatyOS local research console")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    serve(args.port, args.host)


if __name__ == "__main__":
    main()
