"""A local web console for MatyOS — designed for a working mathematician *and* a
curious non-specialist. Zero runtime dependencies (Python stdlib only).

Run ``matyos-ui`` and open http://localhost:8000 .

Three tabs, each with plain-language help:
  * **Explore** — paste a number sequence; MatyOS reports an honest verdict.
  * **Graph patterns** — the classified conjecture shortlist (candidate/derived/
    known), with a live **Prove** button for the ones mathlib can check.
  * **Hard problems** — the four famous conjectures, honestly: state / verify a
    finite range / and a clear statement of what MatyOS cannot do.

The server is threaded so a slow proof never freezes the page. Nothing here ever
reports a famous conjecture as solved.
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
            base = files("matyos") / "assets"
            target = base
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
    it (so the UI knows when to offer a live Prove button). Computed once."""
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
<style>
 :root{
   --bg:#f4f6fa;--surface:#fff;--ink:#0f172a;--muted:#64748b;--line:#e6e9ef;
   --brand:#4f46e5;--brand-d:#4338ca;--brand-soft:#eef2ff;
   --known:#15803d;--known-bg:#e9f6ee;--derived:#2563eb;--derived-bg:#eaf1fe;
   --candidate:#ea580c;--candidate-bg:#fdf0e7;--ok:#16a34a;--bad:#dc2626;
   --mono:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
   --sans:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
   --shadow:0 1px 2px rgba(15,23,42,.04),0 4px 16px rgba(15,23,42,.06)}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
   font-size:14.5px;line-height:1.55;-webkit-font-smoothing:antialiased}
 code,.mono{font-family:var(--mono)}
 header{background:linear-gradient(180deg,#fff, #fbfcfe);border-bottom:1px solid var(--line)}
 .wrap{max-width:1000px;margin:0 auto;padding:0 24px}
 .top{display:flex;align-items:center;gap:12px;padding:20px 0 6px}
 .logo{width:38px;height:38px;object-fit:contain}
 .logo.lfallback{width:34px;height:34px;border-radius:9px;background:var(--brand);color:#fff;
   display:grid;place-items:center;font-weight:700;font-size:18px}
 h1{font-size:19px;margin:0;font-weight:700;letter-spacing:-.01em}
 .pill{font-size:11px;font-weight:600;color:var(--brand-d);background:var(--brand-soft);
   padding:3px 9px;border-radius:999px}
 .tag{color:var(--muted);padding:0 0 16px;max-width:70ch;font-size:13.5px}
 nav{display:flex;gap:4px;padding-bottom:0}
 nav button{font-family:inherit;font-size:14px;font-weight:600;color:var(--muted);
   background:none;border:0;border-bottom:2px solid transparent;padding:10px 14px;cursor:pointer}
 nav button.on{color:var(--brand-d);border-bottom-color:var(--brand)}
 main{max-width:1000px;margin:0 auto;padding:24px}
 .panel{display:none}.panel.on{display:block;animation:f .2s ease}
 @keyframes f{from{opacity:.4;transform:translateY(3px)}to{opacity:1;transform:none}}
 .card{background:var(--surface);border:1px solid var(--line);border-radius:14px;
   box-shadow:var(--shadow);padding:20px 22px;margin-bottom:18px}
 .card h2{font-size:15.5px;margin:0 0 4px}
 .lead{color:var(--muted);font-size:13.5px;margin:0 0 16px}
 .row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
 input[type=text],input[type=number]{font-family:var(--mono);font-size:14px;
   padding:10px 12px;border:1px solid var(--line);border-radius:9px;background:#fbfcfe;flex:1;min-width:220px}
 input:focus{outline:2px solid var(--brand-soft);border-color:var(--brand)}
 button.go{font-family:inherit;font-size:14px;font-weight:600;background:var(--brand);
   color:#fff;border:0;border-radius:9px;padding:10px 18px;cursor:pointer;white-space:nowrap}
 button.go:hover{background:var(--brand-d)}button.go:disabled{opacity:.5;cursor:default}
 button.ghost{background:#fff;color:var(--brand-d);border:1px solid var(--line)}
 .chips{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0 0}
 .chip{font-size:12.5px;font-family:var(--mono);background:#f1f3f9;border:1px solid var(--line);
   border-radius:999px;padding:4px 11px;cursor:pointer;color:var(--ink)}
 .chip:hover{background:var(--brand-soft)}
 .verdict{margin-top:14px;display:grid;gap:10px}
 .vitem{border:1px solid var(--line);border-left:4px solid var(--muted);border-radius:10px;padding:12px 14px;background:#fbfcfe}
 .vitem.found{border-left-color:var(--ok)}.vitem.mystery{border-left-color:var(--candidate)}
 .vitem.none{border-left-color:var(--muted)}
 .vitem .big{font-size:15px;font-weight:600}
 .tags{display:flex;gap:16px;flex-wrap:wrap;margin:2px 0 14px}
 .legend{font-size:12.5px;color:var(--muted);display:flex;gap:14px;flex-wrap:wrap;margin-top:4px}
 .lg{display:inline-flex;align-items:center;gap:6px}
 .dot{width:9px;height:9px;border-radius:3px;display:inline-block}
 .stat{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:8px}
 .tile{flex:1;min-width:120px;border:1px solid var(--line);border-radius:11px;padding:12px 14px;background:#fbfcfe}
 .tile .n{font-size:24px;font-weight:700;font-variant-numeric:tabular-nums}
 .tile .l{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
 table{width:100%;border-collapse:collapse;margin-top:6px}
 td,th{padding:9px 8px;text-align:left;border-bottom:1px solid var(--line);vertical-align:middle}
 th{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;font-weight:600}
 td.ineq{font-family:var(--mono);font-size:13px}
 .badge{font-size:11px;font-weight:700;padding:2px 9px;border-radius:999px;white-space:nowrap}
 .badge.known{color:var(--known);background:var(--known-bg)}
 .badge.derived{color:var(--derived);background:var(--derived-bg)}
 .badge.candidate{color:var(--candidate);background:var(--candidate-bg)}
 .prv{font-size:12px;font-weight:600;padding:5px 11px;border-radius:8px;border:1px solid var(--line);
   background:#fff;color:var(--brand-d);cursor:pointer}
 .prv:hover{background:var(--brand-soft)}.prv:disabled{opacity:.45;cursor:default}
 .presult{font-size:12px;margin-top:4px;font-family:var(--mono)}
 .ok{color:var(--ok)}.bad{color:var(--bad)}
 .prob{border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:14px;background:#fbfcfe}
 .prob h3{margin:0 0 2px;font-size:15px}
 .mathline{margin:8px 0 10px;overflow-x:auto;color:var(--ink)}
 td.ineq .katex{font-size:1.05em}
 .prob .can{color:var(--known);font-size:13px}.prob .cant{color:var(--bad);font-size:13px}
 details{margin-top:10px}summary{cursor:pointer;color:var(--brand-d);font-size:13px;font-weight:600}
 pre{background:#0f172a;color:#e2e8f0;padding:12px 14px;border-radius:9px;overflow:auto;
   font-family:var(--mono);font-size:12px;line-height:1.5}
 .banner{background:var(--candidate-bg);border:1px solid #f3d6c2;color:#9a3d12;
   padding:11px 14px;border-radius:10px;font-size:13px;margin-bottom:16px}
 .spin{display:inline-block;width:13px;height:13px;border:2px solid var(--line);
   border-top-color:var(--brand);border-radius:50%;animation:sp .7s linear infinite;vertical-align:-2px}
 @keyframes sp{to{transform:rotate(360deg)}}
 .help dt{font-weight:600;margin-top:12px}.help dd{margin:2px 0 0;color:var(--muted)}
 .hero{padding:26px 0 6px}
 .htag{font-size:16px;color:var(--ink);max-width:60ch;margin:10px 0 2px;font-weight:500;line-height:1.5}
 .badges{display:flex;gap:7px;flex-wrap:wrap;margin:14px 0 4px;align-items:center}
 .bdg{font-size:11.5px;font-weight:600;padding:3px 9px;border-radius:999px;border:1px solid var(--line);color:var(--muted);background:#fff}
 .bdg.v{color:var(--brand-d);background:var(--brand-soft);border-color:transparent}
 .bdg.warn{color:var(--candidate);background:var(--candidate-bg);border-color:transparent}
 .links{display:flex;gap:14px;font-size:13px;font-weight:600}
 .links a{color:var(--brand-d);text-decoration:none}.links a:hover{text-decoration:underline}
 .parts{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:4px 0 18px}
 .part{border:1px solid var(--line);border-radius:12px;padding:16px;background:#fbfcfe}
 .part h3{margin:0 0 4px;font-size:14.5px}.part p{margin:0;font-size:13px;color:var(--muted)}
 .real{display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 4px}
 .rl{flex:1;min-width:150px;border-radius:10px;padding:12px 14px;border:1px solid var(--line)}
 .rl b{font-size:13.5px}.rl span{font-size:12.5px;color:var(--muted);display:block;margin-top:2px}
 .rl.t{background:var(--known-bg)}.rl.r{background:var(--candidate-bg)}.rl.f{background:#fdeaea}
 .flow{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:8px}
 .step{display:flex;flex-direction:column;align-items:center;gap:6px;min-width:96px;
   border:1px solid var(--line);border-radius:11px;padding:12px 10px;background:#fff;flex:1}
 .step img{width:38px;height:38px}.step b{font-size:13px}.step span{font-size:11.5px;color:var(--muted);text-align:center}
 .arrow{color:var(--muted);font-size:20px}
 footer{border-top:1px solid var(--line);margin-top:10px;background:#fff}
 footer .wrap{padding:18px 24px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;
   color:var(--muted);font-size:12.5px}
 footer a{color:var(--brand-d);text-decoration:none}
 @media(max-width:640px){.top{flex-wrap:wrap}.parts{grid-template-columns:1fr}.flow{flex-direction:column}.arrow{transform:rotate(90deg)}}
</style></head><body>
<header><div class="wrap">
  <div class="top hero"><img class="logo" src="/logo.png" alt="MatyOS" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'logo lfallback',textContent:'M'}))"><h1>MatyOS</h1><span class="pill">research console</span></div>
  <p class="htag">The scientific method as software — a trusted substrate any AI model plugs into to do science honestly. It finds small true patterns, checks them, and proves the easy ones; it <b>does not</b> solve famous open problems, and it says so.</p>
  <div class="badges">
    <span class="bdg v">v{{VERSION}}</span>
    <span class="bdg">sound kernel</span>
    <span class="bdg warn">early · honest</span>
    <span class="bdg">MIT</span>
    <span class="links" style="margin-left:auto">
      <a href="https://github.com/MatyOS-Project/MatyOS" target="_blank" rel="noopener">GitHub</a>
      <a href="https://pypi.org/project/matyos/" target="_blank" rel="noopener">PyPI</a>
    </span>
  </div>
  <nav>
    <button class="on" data-tab="explore">Explore a sequence</button>
    <button data-tab="graph">Graph patterns</button>
    <button data-tab="problems">Hard problems</button>
    <button data-tab="how">How it works</button>
    <button data-tab="help">What is this?</button>
  </nav>
</div></header>
<main>

<section class="panel on" id="explore">
  <div class="card">
    <h2>Give MatyOS a number sequence</h2>
    <p class="lead">Type the first several terms of an integer sequence. MatyOS looks for a hidden pattern and tells you honestly: a real formula, a “mystery” constant, or nothing — it never makes one up.</p>
    <div class="row">
      <input type="text" id="seq" value="0, 1, 1, 2, 3, 5, 8, 13, 21, 34" placeholder="e.g. 2, 4, 6, 8, 10">
      <button class="go" id="discBtn" onclick="discover()">Discover</button>
    </div>
    <div class="chips">
      <span class="chip" onclick="setSeq('0,1,1,2,3,5,8,13,21,34')">Fibonacci</span>
      <span class="chip" onclick="setSeq('2,3,5,7,11,13,17,19,23,29')">Primes</span>
      <span class="chip" onclick="setSeq('1,4,9,16,25,36,49')">Squares</span>
      <span class="chip" onclick="setSeq('1,3,4,7,11,18,29,47')">Lucas</span>
    </div>
    <div class="verdict" id="disc"></div>
  </div>
</section>

<section class="panel" id="graph">
  <div class="card">
    <h2>Graph patterns MatyOS found</h2>
    <p class="lead">Each row is a rule of the form “quantity A is never bigger than quantity B”, tested on many graphs. MatyOS sorts them by how well it understands them.</p>
    <div class="stat" id="stat"></div>
    <div class="legend">
      <span class="lg"><span class="dot" style="background:var(--candidate)"></span><b>candidate</b> — MatyOS can’t explain it yet (a lead worth a look)</span>
      <span class="lg"><span class="dot" style="background:var(--derived)"></span><b>derived</b> — follows from rules it knows</span>
      <span class="lg"><span class="dot" style="background:var(--known)"></span><b>known</b> — an established theorem</span>
    </div>
    <details style="margin-top:10px"><summary>Symbol key</summary>
      <div id="symkey" class="legend" style="margin-top:8px"></div></details>
    <div id="conj" style="margin-top:12px">Loading…</div>
  </div>
</section>

<section class="panel" id="problems">
  <div class="card">
    <h2>Famous unsolved problems — the honest view</h2>
    <div class="banner">MatyOS can <b>state</b> these precisely and <b>check them on many numbers</b>, but it <b>cannot prove</b> them — and it will never say it did. Checking a range is evidence, not a proof.</div>
    <div id="probs">Loading…</div>
  </div>
</section>

<section class="panel" id="how">
  <div class="card">
    <h2>Three parts</h2>
    <p class="lead">MatyOS lends any model the discipline of the scientific method: the model brings the ideas, MatyOS brings the rigour.</p>
    <div class="parts">
      <div class="part"><h3>Discovery engine</h3><p>Hunts for new patterns — cross-domain transfer, PSLQ closed-form detection with a significance gate, live OEIS prior-art checks — keeping only the surprising and not-already-known.</p></div>
      <div class="part"><h3>Trusted verifier</h3><p>A small dependently-typed kernel in the tradition of Lean, Coq and Agda. Every proof, however produced, reduces to a term the tiny trusted kernel checks. Nothing is “assumed proven”.</p></div>
      <div class="part"><h3>MCP substrate</h3><p><code>pip install "matyos[mcp]"</code> and any model can call MatyOS to verify closed forms, check OEIS, check proofs, and run the discovery loop.</p></div>
    </div>
  </div>
  <div class="card">
    <h2>The <code>realistic</code> idea — uncertainty is first-class</h2>
    <p class="lead">Real work (especially an LLM’s) is full of plausible-but-unproven steps. MatyOS uses a three-valued logic so conjecture and certainty never get confused.</p>
    <div class="real">
      <div class="rl t"><b>TRUE</b><span>proven — the kernel checked a term</span></div>
      <div class="rl r"><b>REALISTIC</b><span>found and stable, but unproven — a conjecture</span></div>
      <div class="rl f"><b>FALSE</b><span>refuted by a counterexample</span></div>
    </div>
  </div>
  <div class="card">
    <h2>The scientific-method workflow</h2>
    <p class="lead">A MatyOS project moves a claim from a guess to a checked result — each stage its own file type.</p>
    <div class="flow">
      <div class="step"><img src="/assets/icons/hyp.svg" alt=""><b>.hyp</b><span>hypothesis</span></div>
      <span class="arrow">→</span>
      <div class="step"><img src="/assets/icons/thm.svg" alt=""><b>.thm</b><span>theorem stated</span></div>
      <span class="arrow">→</span>
      <div class="step"><img src="/assets/icons/test.svg" alt=""><b>.test</b><span>tested / tried to refute</span></div>
      <span class="arrow">→</span>
      <div class="step"><img src="/assets/icons/prf.svg" alt=""><b>.prf</b><span>proof, kernel-checked</span></div>
    </div>
  </div>
</section>

<section class="panel" id="help">
  <div class="card">
    <h2>What is MatyOS, in plain words?</h2>
    <dl class="help">
      <dt>What it does</dt><dd>Looks for patterns in numbers and in graphs (dots joined by lines), then checks whether each pattern is really true.</dd>
      <dt>Why “honest”?</dt><dd>It labels everything: a real formula, a known result, a mystery, or “no pattern”. It refuses to invent an answer, and it never claims to solve a famous problem.</dd>
      <dt>“candidate / derived / known”</dt><dd><b>Known</b> = a proven theorem. <b>Derived</b> = follows from things it knows. <b>Candidate</b> = it holds on every test but MatyOS can’t explain it — that’s where something new could hide.</dd>
      <dt>The “Prove” button</dt><dd>Sends the rule to Lean, a real proof-checking program, with the mathlib library. If Lean accepts a proof, you get a green ✓ and the theorem it used. If not, it honestly says “open”.</dd>
      <dt>The “Verify” button</dt><dd>Checks a famous conjecture on every number up to a limit you choose. Green means no counterexample was found in that range — still not a proof.</dd>
    </dl>
  </div>
</section>

</main>
<footer><div class="wrap">
  <span>MatyOS v{{VERSION}} · the scientific method as software · sound kernel, honest labels</span>
  <span><a href="https://github.com/MatyOS-Project/MatyOS" target="_blank" rel="noopener">GitHub</a> · <a href="https://pypi.org/project/matyos/" target="_blank" rel="noopener">PyPI</a> · <code>pip install "matyos[mcp]"</code></span>
</div></footer>
<script>
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
async function jget(u){return (await fetch(u)).json()}
async function jpost(u,o){return (await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)})).json()}
$$('nav button').forEach(b=>b.onclick=()=>{
  $$('nav button').forEach(x=>x.classList.toggle('on',x===b));
  $$('.panel').forEach(p=>p.classList.toggle('on',p.id===b.dataset.tab));
});
function setSeq(s){$('#seq').value=s.split(',').join(', ')}

// invariant name -> LaTeX symbol (as a function of the graph G)
const SYM={order:'n',size:'m',max_degree:'\\Delta',min_degree:'\\delta',avg_degree:'\\bar d',
 triangles:'t',diameter:'\\operatorname{diam}',radius:'r',independence_number:'\\alpha',
 clique_number:'\\omega',chromatic_number:'\\chi',vertex_cover_number:'\\tau',
 domination_number:'\\gamma',matching_number:'\\nu',vertex_connectivity:'\\kappa',
 edge_connectivity:'\\lambda',degeneracy:'\\operatorname{degen}',girth:'g',
 average_eccentricity:'\\overline{\\operatorname{ecc}}',average_distance:'\\mu',
 total_domination_number:'\\gamma_t',edge_cover_number:'\\rho',spectral_radius:'\\lambda_1',
 energy:'\\mathcal{E}',algebraic_connectivity:'a',laplacian_spectral_radius:'\\mu_1'};
function symTex(name){const s=SYM[name]||name.replace(/_/g,'\\_');return (name==='order'||name==='size')?s:s+'(G)';}
function kx(t,disp){try{return katex.renderToString(t,{throwOnError:false,displayMode:!!disp});}catch(e){return t;}}
function ruleTex(stmt){const p=stmt.split(' <= ');return kx(symTex(p[0])+' \\le '+symTex(p[1]));}
function cfTex(cf){if(!cf)return '';let s=cf
   .replace(/sqrt(\d+)/g,'\\sqrt{$1}').replace(/\bpi\b/g,'\\pi').replace(/\^(\d+)/g,'^{$1}')
   .replace(/\bln(\d+)/g,'\\ln $1').replace(/\bzeta(\d+)/g,'\\zeta($1)')
   .replace(/\bgamma\b/g,'\\gamma').replace(/\bcatalan\b/g,'\\mathrm{G}');
 return kx(s);}

async function discover(){
  const btn=$('#discBtn'); btn.disabled=true;
  const seq=$('#seq').value.split(',').map(s=>parseInt(s.trim())).filter(x=>!isNaN(x));
  $('#disc').innerHTML='<div class="lead"><span class="spin"></span> Searching…</div>';
  try{
    const d=await jpost('/api/discover',{seq});
    if(!d.candidates||!d.candidates.length){
      $('#disc').innerHTML='<div class="vitem none"><div class="big">No formula found</div><div class="lead" style="margin:0">Often the honest answer — many sequences have no closed form.</div></div>';
    }else{
      $('#disc').innerHTML=d.candidates.map(r=>{
        const cf=r.closed_form||''; const lab=(r.label&&r.label.status)||'';
        const known=r.verification&&r.verification.prior_art;
        let cls='none',big='No formula for this one';
        if(cf){cls='found';big='Formula: '+cfTex(cf)}
        else if(lab.includes('mystery')){cls='mystery';big='Stable “mystery” value (no known formula)'}
        return `<div class="vitem ${cls}"><div class="big">${big}</div>`+
          `<div class="lead" style="margin:2px 0 0">honest label: <b>${lab||'—'}</b>${known?(' · already known: '+known):''}</div></div>`;
      }).join('');
    }
  }catch(e){$('#disc').innerHTML='<div class="vitem bad">error: '+e+'</div>'}
  btn.disabled=false;
}

(async()=>{
  const c=(await jget('/api/conjectures')).conjectures;
  const by=n=>c.filter(x=>x.novelty===n).length;
  $('#stat').innerHTML=[['candidate','candidate'],['derived','derived'],['known','known']]
    .map(([k])=>`<div class="tile"><div class="n" style="color:var(--${k})">${by(k)}</div><div class="l">${k}</div></div>`).join('');
  let h='<table><tr><th>rule (A ≤ B)</th><th>status</th><th>held / tight</th><th>check with Lean</th></tr>';
  for(const r of c){
    h+=`<tr><td class="ineq" title="${r.statement}">${ruleTex(r.statement)}</td>`+
       `<td><span class="badge ${r.novelty}">${r.novelty}</span></td>`+
       `<td class="mono">${r.held_on} / ${r.tight_on}</td>`+
       `<td><button class="prv" onclick="prove(this,'${r.statement}',${r.mathlib_ready?1:0})">Prove</button><div class="presult"></div></td></tr>`;
  }
  $('#conj').innerHTML=h+'</table>';
  const used=new Set(); c.forEach(r=>r.statement.split(' <= ').forEach(x=>used.add(x)));
  $('#symkey').innerHTML=[...used].sort().map(n=>
    `<span class="lg">${kx(symTex(n))}<span style="color:var(--muted)">= ${n.replace(/_/g,' ')}</span></span>`).join('');
  const p=(await jget('/api/problems')).problems;
  const MATH={goldbach:'\\forall\\,n>2\\ \\text{even},\\ \\exists\\,p,q\\ \\text{prime}:\\ n=p+q',
    twin_primes:'\\forall\\,N,\\ \\exists\\,p>N:\\ p\\ \\text{and}\\ p+2\\ \\text{prime}',
    collatz:'\\forall\\,n>0,\\ \\exists\\,k:\\ C^{k}(n)=1\\quad(C:\\text{ }n\\mapsto n/2\\text{ or }3n+1)',
    riemann:'\\zeta(s)=0,\\ 0<\\Re(s)<1\\ \\Rightarrow\\ \\Re(s)=\\tfrac12'};
  $('#probs').innerHTML=p.map(x=>{
    const fin=x.finite_checkable;
    return `<div class="prob"><h3>${x.name}</h3>`+
      (MATH[x.key]?`<div class="mathline">${kx(MATH[x.key],true)}</div>`:'')+
      `<div class="can">✓ MatyOS can: ${x.matyos_can.join(', ')}.</div>`+
      `<div class="cant">✗ Cannot: ${x.matyos_cannot}.</div>`+
      (fin?`<div class="row" style="margin-top:10px"><input type="number" id="n_${x.key}" value="1000" min="4" style="max-width:130px">`+
        `<button class="prv" onclick="verify('${x.key}',this)">Verify up to N</button><span class="presult" id="v_${x.key}"></span></div>`:
        `<div class="lead" style="margin:8px 0 0">No finite check settles this one${x.key==='riemann'?' (needs the zeta function)':' (it asserts infinitely many cases)'}.</div>`)+
      `<details><summary>Formal Lean statement</summary><pre>${x.lean_statement.replace(/</g,'&lt;')}</pre></details></div>`;
  }).join('');
})();

async function prove(btn,stmt,ready){
  const out=btn.nextElementSibling;
  if(!ready){ out.innerHTML='<span style="color:var(--muted)">— can’t check yet: uses an invariant mathlib doesn’t define</span>'; return; }
  btn.disabled=true;
  out.innerHTML='<span class="spin"></span> proving with Lean… (up to ~2 min)';
  try{
    const r=await jpost('/api/prove',{statement:stmt});
    if(r.status==='proved') out.innerHTML='<span class="ok">✓ proved'+(r.lemma?(' via '+r.lemma):(' by '+r.tactic))+'</span>';
    else if(r.status==='open') out.innerHTML='<span>— open (automation didn’t close it; a human proof is needed)</span>';
    else out.innerHTML='<span class="bad">'+(r.note||r.status)+'</span>';
  }catch(e){out.innerHTML='<span class="bad">error: '+e+'</span>'}
  btn.disabled=false;
}
async function verify(key,btn){
  const out=$('#v_'+key); const n=parseInt($('#n_'+key).value)||1000;
  btn.disabled=true; out.innerHTML='<span class="spin"></span> checking…';
  try{
    const r=await jpost('/api/verify_finite',{problem:key,upto:n});
    if(r.error){out.innerHTML='<span class="bad">'+r.error+'</span>'}
    else out.innerHTML=r.holds?`<span class="ok">✓ holds for all up to ${r.checked_up_to} — evidence, not a proof</span>`:
      `<span class="bad">counterexample at ${r.counterexample}!</span>`;
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
            page = _PAGE.replace("{{VERSION}}", matyos.__version__)
            return self._send(200, page, "text/html; charset=utf-8")
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
                payload = self._body()
                seq = [int(x) for x in payload.get("seq", [])]
                if len(seq) < 4:
                    return self._send(200, json.dumps({"candidates": [], "note": "give at least 4 integers"}))
                from matyos.discovery.objects import Sequence
                from matyos.discovery.engine import DiscoveryEngine
                recs = DiscoveryEngine(min_score=0.0).records([Sequence.of(seq, name="ui")])
                return self._send(200, json.dumps({"candidates": recs[:5]}))
            if self.path == "/api/prove":
                stmt_text = self._body().get("statement", "")
                from matyos.discovery import lean
                gs = lean.graph_statement(stmt_text)
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
        except Exception as e:                # a bad request must never crash the server
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
