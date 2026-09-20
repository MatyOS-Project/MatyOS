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


_LAB_BATTERY = None


def _lab_battery():
    """A fixed, diverse battery of connected graphs the Lab probes a hypothesis on:
    the canonical sample plus seeded random graphs. Deterministic → reproducible."""
    global _LAB_BATTERY
    if _LAB_BATTERY is None:
        import random
        from matyos.discovery import graph as g
        random.seed(17)
        bat = list(g.sample_graphs())

        def rc(n):
            v = list(range(n)); random.shuffle(v); e = set()
            for i in range(1, n):
                e.add((v[i], v[random.randrange(i)]))
            for _ in range(random.randint(0, n)):
                a, b = random.sample(range(n), 2); e.add((a, b))
            return g.Graph.of(n, list(e), f"rand{n}")

        for n in range(4, 11):
            bat += [rc(n) for _ in range(14)]
        _LAB_BATTERY = [x for x in bat if g.is_connected(x)]
    return _LAB_BATTERY


def _lab_probe(a: str, b: str) -> dict:
    """Run the hypothesis  a(G) <= b(G)  over the battery: does it hold, is it tight,
    a counterexample if not, and its novelty label. This is the Lab's 'Probe' stage."""
    from matyos.discovery import graph as g, known, lean
    inv = g.all_invariants()
    if a not in inv or b not in inv or a == b:
        return {"error": "pick two different invariants"}
    fa, fb = inv[a], inv[b]
    viol = 0; witness = None; tight = 0
    for gr in _lab_battery():
        va, vb = float(fa(gr)), float(fb(gr))
        if va > vb + 1e-9:
            viol += 1
            if witness is None:
                witness = {"graph": gr.name, "a": round(va, 3), "b": round(vb, 3)}
        elif abs(va - vb) <= 1e-9:
            tight += 1
    holds = viol == 0
    stmt = f"{a} <= {b}"
    nov = known.classify(stmt) if holds else {"status": "refuted",
                                              "reason": "a counterexample exists"}
    ready = lean.graph_statement(stmt)["mathlib_ready"] if holds else False
    return {"statement": stmt, "a": a, "b": b, "tested": len(_lab_battery()),
            "holds": holds, "violations": viol, "witness": witness, "tight": tight,
            "novelty": nov.get("status"), "reason": nov.get("reason"),
            "mathlib_ready": ready}


# ---- the page ------------------------------------------------------------------

_PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MatyOS — research console</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
<style>
 :root{--bg:#fafafa;--surface:#fff;--ink:#0a0a0a;--muted:#6a6a6a;--line:#e4e4e4;
  --brand:#0a0a0a;--brand-d:#000;--brand-soft:#f0f0f0;--sidebar:#0a0a0a;--sidebar-2:#161616;
  --known:#333;--known-bg:#f0f0f0;--derived:#555;--derived-bg:#f7f7f7;
  --candidate:#0a0a0a;--candidate-bg:#e6e6e6;--ok:#0a0a0a;--bad:#0a0a0a;
  --mono:'JetBrains Mono',ui-monospace,Menlo,monospace;--sans:'Inter',-apple-system,'Segoe UI',Roboto,sans-serif;
  --display:'Fredoka','Inter',-apple-system,sans-serif;
  --sh:0 1px 2px rgba(0,0,0,.04),0 6px 22px rgba(0,0,0,.06)}
 .brand b,.hero h1,.card h2,.fcard h3,.topbar h2,.stat .n,.eyebrow{font-family:var(--display)}
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
 .side nav button.on{background:#fff;color:#0a0a0a}
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
 .pill.honest{background:#0a0a0a;color:#fff;margin-left:auto}
 .views{padding:26px 30px 60px;max-width:1080px}
 .view{display:none}.view.on{display:block;animation:f .25s ease}
 @keyframes f{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
 @media(prefers-reduced-motion){.view.on{animation:none}}
 /* hero */
 .hero{display:grid;grid-template-columns:1.25fr .75fr;gap:28px;align-items:center;
   background:#0a0a0a;color:#fff;border-radius:20px;padding:42px 40px;box-shadow:var(--sh);position:relative;overflow:hidden}
 .hero::before{content:"";position:absolute;inset:0;opacity:.9;pointer-events:none;
   background-image:radial-gradient(rgba(255,255,255,.055) 1px,transparent 1px);background-size:22px 22px}
 .hero>*{position:relative;z-index:1}
 .eyebrow{font-size:11.5px;font-weight:700;letter-spacing:.16em;color:#9a9a9a}
 .hero h1{font-size:42px;line-height:1.04;margin:12px 0 14px;font-weight:700;letter-spacing:-.015em;color:#fff;text-wrap:balance}
 .hero p{color:#c7c7c7;font-size:14.5px;max-width:52ch;margin:0 0 20px}
 .cta{display:flex;gap:10px;flex-wrap:wrap}
 .go{font:600 14px var(--sans);background:var(--brand);color:#fff;border:0;border-radius:10px;padding:11px 20px;cursor:pointer;text-decoration:none;display:inline-block}
 .go:hover{background:#2a2a2a}.go.sm{padding:6px 12px;font-size:12.5px}
 .hero .go{background:#fff;color:#0a0a0a}.hero .go:hover{background:#e6e6e6}
 .hero .go.ghost{background:transparent;color:#fff;border:1px solid rgba(255,255,255,.35)}
 .hero-art{display:grid;place-items:center}
 .orb{width:196px;height:196px;border-radius:50%;background:#fff;
   display:grid;place-items:center;box-shadow:0 14px 44px rgba(0,0,0,.45)}
 .orb img{width:120px;height:120px;filter:none}
 .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:20px 0}
 .stat{background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:16px 18px;box-shadow:var(--sh)}
 .stat{transition:transform .18s ease,box-shadow .18s ease}
 .stat:hover,.fcard:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(0,0,0,.09)}
 .fcard{transition:transform .18s ease,box-shadow .18s ease}
 .stat .n{font-size:28px;font-weight:600;font-variant-numeric:tabular-nums;letter-spacing:-.01em}
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
 .badge.known{color:#555;background:#efefef}
 .badge.derived{color:#555;background:#fff;border:1px solid #cfcfcf}
 .badge.candidate{color:#fff;background:#0a0a0a}
 .badge.refuted{color:#0a0a0a;background:#fff;border:1px dashed #9a9a9a}
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
 .rl.t{background:#0a0a0a;color:#fff}.rl.t span{color:#b8b8b8}
 .rl.r{background:#ececec}.rl.f{background:#fff;border:1px dashed #9a9a9a}
 .flow{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:10px}
 .step{display:flex;flex-direction:column;align-items:center;gap:7px;border:1px solid var(--line);border-radius:12px;padding:14px 12px;background:#fff;flex:1;min-width:100px}
 .step img{width:40px;height:40px}.step b{font-size:13px}.step span{font-size:11.5px;color:var(--muted);text-align:center}
 .arrow{color:var(--muted);font-size:20px}
 .labform{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:4px 0 2px}
 .lstep{font-size:11.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);margin-right:4px}
 .labform select{font:600 13.5px var(--sans);padding:9px 11px;border:1px solid var(--line);border-radius:9px;background:#fff;min-width:190px;cursor:pointer}
 .labform .le{font-family:var(--mono);font-size:16px;color:var(--muted)}
 .stepper{display:flex;align-items:center;margin:18px 0 4px}
 .stp{display:flex;flex-direction:column;align-items:center;gap:6px;opacity:.35;transition:opacity .35s}
 .stp .dot{width:36px;height:36px;border-radius:50%;border:2px solid #0a0a0a;background:#fff;display:grid;place-items:center;font-weight:700;font-size:14px;transition:background .3s,color .3s,box-shadow .3s}
 .stp .lb{font-size:11.5px;font-weight:600}
 .stp.active,.stp.done,.stp.refuted{opacity:1}
 .stp.active .dot{background:#0a0a0a;color:#fff;animation:pulse 1.1s infinite}
 .stp.done .dot{background:#0a0a0a;color:#fff}
 .stp.refuted .dot{background:#fff;border-style:dashed;color:#0a0a0a}
 .conn{flex:1;height:2px;background:#e4e4e4;margin:0 6px;position:relative;top:-9px;overflow:hidden;min-width:20px}
 .conn::after{content:"";position:absolute;inset:0;background:#0a0a0a;transform:scaleX(0);transform-origin:left;transition:transform .45s ease}
 .conn.fill::after{transform:scaleX(1)}
 @keyframes pulse{0%,100%{box-shadow:0 0 0 4px rgba(10,10,10,.12)}50%{box-shadow:0 0 0 10px rgba(10,10,10,.02)}}
 @media (prefers-reduced-motion:reduce){.stp.active .dot{animation:none}.conn::after{transition:none}}
 .labstage{border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-top:14px;background:#fbfcff}
 .labstage .k{font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
 .labstage .big{font-size:15px;margin-top:2px}
 .labrow{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px}
 .nb{border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:12px;box-shadow:var(--sh)}
 .nb .hyp{font-size:15px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
 .nb .stages{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
 .nb .st{font-size:11.5px;padding:3px 9px;border-radius:999px;border:1px solid var(--line);background:#fff;color:var(--muted)}
 .nb .st b{color:var(--ink)}
 .flowsvg{width:100%;height:auto;max-width:960px;margin:14px 0 6px;display:block}
 @media(max-width:720px){.flowsvg{display:none}}
 .wf{margin-top:6px}
 .wfrow{display:flex;gap:16px;align-items:flex-start;padding:16px 2px;border-top:1px solid var(--line)}
 .wfrow:first-child{border-top:0}
 .wfnum{flex:none;width:26px;height:26px;border-radius:50%;background:#0a0a0a;color:#fff;display:grid;place-items:center;font-size:13px;font-weight:700;margin-top:2px}
 .wfrow>img{width:34px;height:34px;flex:none;margin-top:1px}
 .wfrow b{font-size:14.5px}.wfrow .ext{margin-left:8px;background:#f0f0f0;padding:1px 7px;border-radius:5px;font-size:12px;font-family:var(--mono)}
 .wfrow p{margin:3px 0 0;color:var(--muted);font-size:13px;max-width:70ch}
 .spin{display:inline-block;width:13px;height:13px;border:2px solid var(--line);border-top-color:var(--brand);border-radius:50%;animation:sp .7s linear infinite;vertical-align:-2px}
 @keyframes sp{to{transform:rotate(360deg)}}
 .help dt{font-weight:600;margin-top:12px}.help dd{margin:2px 0 0;color:var(--muted)}
 @keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
 @keyframes march{to{stroke-dashoffset:-20}}
 @media (prefers-reduced-motion:no-preference){
  .hero-txt>*{animation:rise .55s cubic-bezier(.2,.7,.2,1) both}
  .hero-txt>*:nth-child(2){animation-delay:.06s}.hero-txt>*:nth-child(3){animation-delay:.12s}.hero-txt>*:nth-child(4){animation-delay:.18s}
  .hero-art{animation:rise .6s .12s cubic-bezier(.2,.7,.2,1) both}
  .stats .stat{animation:rise .5s both}
  .stats .stat:nth-child(1){animation-delay:.05s}.stats .stat:nth-child(2){animation-delay:.11s}.stats .stat:nth-child(3){animation-delay:.17s}.stats .stat:nth-child(4){animation-delay:.23s}
  .feat .fcard{animation:rise .5s both}
  .feat .fcard:nth-child(1){animation-delay:.1s}.feat .fcard:nth-child(2){animation-delay:.17s}.feat .fcard:nth-child(3){animation-delay:.24s}
  .flowsvg .fwd line{stroke-dasharray:6 7;animation:march 1s linear infinite}
  .flowsvg .fb{animation:march 1.2s linear infinite}}
 @media (prefers-reduced-motion:reduce){.flowsvg .fbdot{display:none}}
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
     <button data-view="lab"><span class="i">⚗</span> Lab</button>
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

   <section class="view" id="lab">
     <div class="card">
       <h2>The Lab — run the scientific method on a claim</h2>
       <p class="lead">Pose a hypothesis about two graph quantities (“A is never bigger than B”), <b>probe</b> it on hundreds of graphs, and — if it holds and mathlib can express it — <b>certify</b> it with Lean. Every run lands in your notebook below, labelled honestly.</p>
       <div class="labform">
         <span class="lstep">1 · Pose</span>
         <select id="labType" onchange="labSwitch()">
           <option value="graph">Graph inequality</option>
           <option value="sequence">Number sequence</option>
           <option value="finite">Finite conjecture</option>
         </select>
         <span class="posegrp" id="pose-graph"><select id="labA"></select><span class="le">≤</span><select id="labB"></select></span>
         <span class="posegrp" id="pose-sequence" hidden><input type="text" id="labSeq" value="0, 1, 1, 2, 3, 5, 8, 13, 21, 34" style="min-width:280px"></span>
         <span class="posegrp" id="pose-finite" hidden><select id="labProb"></select> <span class="le" style="font-family:var(--sans)">up to</span> <input type="number" id="labN" value="1000" min="4" style="max-width:110px"></span>
         <button class="go" id="labRun" onclick="labRun()">Run experiment</button>
       </div>
       <div class="stepper" id="stepper" hidden>
         <div class="stp" data-s="pose"><div class="dot">1</div><div class="lb">Pose</div></div><div class="conn"></div>
         <div class="stp" data-s="state"><div class="dot">2</div><div class="lb">State</div></div><div class="conn"></div>
         <div class="stp" data-s="probe"><div class="dot">3</div><div class="lb">Probe</div></div><div class="conn"></div>
         <div class="stp" data-s="certify"><div class="dot">4</div><div class="lb">Certify</div></div><div class="conn"></div>
         <div class="stp" data-s="theory"><div class="dot">5</div><div class="lb">Theory</div></div>
       </div>
       <div id="labState"></div>
     </div>
     <div class="card"><div class="row" style="justify-content:space-between"><h2 style="margin:0">Lab notebook</h2>
       <button class="prv" id="labExport" onclick="labExport()" hidden>Export notebook (JSON)</button></div>
       <p class="lead" id="labempty" style="margin-top:8px">No experiments yet — pose a hypothesis above and run it.</p>
       <div id="labbook" style="margin-top:8px"></div></div>
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
     <div class="card"><h2>The scientific method, as files</h2>
       <p class="lead">MatyOS mirrors real science as a folder of files — and, like science, it’s a loop: a claim that fails a test goes back to be refined; one that passes gets proven and joins the theory. <code>matyos check</code> runs the files in this order through one trusted kernel.</p>
       <svg class="flowsvg" viewBox="0 0 980 188" role="img" aria-label="The scientific method as a loop">
        <defs><marker id="ah" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="#0a0a0a"/></marker></defs>
        <g class="fwd" stroke="#0a0a0a" stroke-width="2" marker-end="url(#ah)">
          <line x1="158" y1="58" x2="190" y2="58"/><line x1="346" y1="58" x2="378" y2="58"/>
          <line x1="534" y1="58" x2="566" y2="58"/><line x1="722" y1="58" x2="756" y2="58"/></g>
        <text x="741" y="46" font-size="11" fill="#0a0a0a" text-anchor="middle" font-weight="600" font-family="Inter,sans-serif">proven</text>
        <path class="fb" d="M459,98 C459,168 83,168 83,98" stroke="#0a0a0a" stroke-width="2" fill="none" stroke-dasharray="5 4" marker-end="url(#ah)"/>
        <circle class="fbdot" r="4.5" fill="#0a0a0a"><animateMotion dur="2.4s" repeatCount="indefinite" path="M459,98 C459,168 83,168 83,98"/></circle>
        <text x="271" y="160" font-size="12" fill="#555" text-anchor="middle" font-family="Inter,sans-serif">refuted &#8594; refine the hypothesis</text>
        <g font-family="Fredoka,Inter,sans-serif">
         <g transform="translate(8,20)"><rect width="150" height="78" rx="14" fill="#fff" stroke="#0a0a0a" stroke-width="2"/><circle cx="24" cy="21" r="11" fill="#0a0a0a"/><text x="24" y="25" font-size="12" fill="#fff" text-anchor="middle" font-weight="700">1</text><image href="/assets/icons/hyp.svg" x="12" y="40" width="28" height="28"/><text x="50" y="46" font-size="15" font-weight="700" fill="#0a0a0a">Assume</text><text x="50" y="64" font-size="11" fill="#666" font-family="JetBrains Mono,monospace">.hyp</text></g>
         <g transform="translate(196,20)"><rect width="150" height="78" rx="14" fill="#fff" stroke="#0a0a0a" stroke-width="2"/><circle cx="24" cy="21" r="11" fill="#0a0a0a"/><text x="24" y="25" font-size="12" fill="#fff" text-anchor="middle" font-weight="700">2</text><image href="/assets/icons/thm.svg" x="12" y="40" width="28" height="28"/><text x="50" y="46" font-size="15" font-weight="700" fill="#0a0a0a">State</text><text x="50" y="64" font-size="11" fill="#666" font-family="JetBrains Mono,monospace">.thm</text></g>
         <g transform="translate(384,20)"><rect width="150" height="78" rx="14" fill="#fff" stroke="#0a0a0a" stroke-width="2"/><circle cx="24" cy="21" r="11" fill="#0a0a0a"/><text x="24" y="25" font-size="12" fill="#fff" text-anchor="middle" font-weight="700">3</text><image href="/assets/icons/test.svg" x="12" y="40" width="28" height="28"/><text x="50" y="46" font-size="15" font-weight="700" fill="#0a0a0a">Probe</text><text x="50" y="64" font-size="11" fill="#666" font-family="JetBrains Mono,monospace">.test</text></g>
         <g transform="translate(572,20)"><rect width="150" height="78" rx="14" fill="#fff" stroke="#0a0a0a" stroke-width="2"/><circle cx="24" cy="21" r="11" fill="#0a0a0a"/><text x="24" y="25" font-size="12" fill="#fff" text-anchor="middle" font-weight="700">4</text><image href="/assets/icons/prf.svg" x="12" y="40" width="28" height="28"/><text x="50" y="46" font-size="15" font-weight="700" fill="#0a0a0a">Certify</text><text x="50" y="64" font-size="11" fill="#666" font-family="JetBrains Mono,monospace">.prf</text></g>
         <g transform="translate(760,20)"><rect width="212" height="78" rx="14" fill="#0a0a0a"/><circle cx="24" cy="21" r="11" fill="#fff"/><text x="24" y="25" font-size="12" fill="#0a0a0a" text-anchor="middle" font-weight="700">5</text><image href="/assets/icons/matyos.svg" x="12" y="40" width="28" height="28"/><text x="50" y="46" font-size="15" font-weight="700" fill="#fff">Theory</text><text x="50" y="64" font-size="11" fill="#bbb" font-family="JetBrains Mono,monospace">verified body</text></g>
        </g>
       </svg>
       <div class="wf">
         <div class="wfrow"><div class="wfnum">1</div><img src="/assets/icons/hyp.svg" alt="">
           <div><b>Assume</b><span class="ext">.hyp</span><p>Write down what you take as true but haven’t proved. Flagged <b>realistic</b>, so nothing built on it is ever mistaken for certainty.</p></div></div>
         <div class="wfrow"><div class="wfnum">2</div><img src="/assets/icons/thm.svg" alt="">
           <div><b>State</b><span class="ext">.thm</span><p>Write the claim you intend to establish. On its own it is just an open goal — it carries no proof yet.</p></div></div>
         <div class="wfrow"><div class="wfnum">3</div><img src="/assets/icons/test.svg" alt="">
           <div><b>Probe</b><span class="ext">.test</span><p>Run computational experiments. The kernel checks the claim on real inputs — the way a scientist tests before committing to a proof.</p></div></div>
         <div class="wfrow"><div class="wfnum">4</div><img src="/assets/icons/prf.svg" alt="">
           <div><b>Certify</b><span class="ext">.prf</span><p>Supply a proof term; the <b>trusted kernel</b> checks it against the stated theorem. If it passes, the claim is proven — <b>TRUE</b>, not just realistic.</p></div></div>
         <div class="wfrow"><div class="wfnum">5</div><img src="/assets/icons/matyos.svg" alt="">
           <div><b>Theory</b><span class="ext">folder</span><p>The verified body — definitions, theorems and proofs grouped together, every claim labelled certain or conjectural. Packs into one <code>.matyos</code> archive.</p></div></div>
       </div></div>
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
const CRUMB={overview:'Overview',lab:'Lab',explore:'Explore a sequence',graph:'Graph patterns',problems:'Hard problems',how:'How it works',help:'What is this?'};
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

const LAB=[];
const LAB_MATH={goldbach:'\\forall\\,n>2\\ \\text{even},\\ \\exists\\,p,q\\ \\text{prime}:\\ n=p+q',
  collatz:'\\forall\\,n>0,\\ \\exists\\,k:\\ C^{k}(n)=1'};
let LAB_PROBS=[];
async function labInit(){
  const inv=(await jget('/api/invariants')).invariants;
  const opts=inv.map(n=>`<option value="${n}">${n.replace(/_/g,' ')}</option>`).join('');
  $('#labA').innerHTML=opts; $('#labB').innerHTML=opts; $('#labA').value='radius'; $('#labB').value='diameter';
  LAB_PROBS=(await jget('/api/problems')).problems.filter(p=>p.finite_checkable);
  $('#labProb').innerHTML=LAB_PROBS.map(p=>`<option value="${p.key}">${p.name}</option>`).join('');
}
function labSwitch(){const t=$('#labType').value;['graph','sequence','finite'].forEach(k=>$('#pose-'+k).hidden=(k!==t));}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const _s=(s,c)=>{const el=document.querySelector('.stp[data-s="'+s+'"]');if(!el)return;el.classList.remove('active','done','refuted');if(c)el.classList.add(c);};
const _conn=i=>{const c=$$('.conn')[i];if(c)c.classList.add('fill');};
const _pk='<span class="k">3 · Probe</span>&nbsp;';
const _cr=h=>'<div class="labrow"><span class="k">4 · Certify</span>&nbsp;'+h+'</div>';
const _bcls=l=>({known:'known',derived:'derived',candidate:'candidate',refuted:'refuted',realistic:'candidate',open:'refuted',none:'refuted'}[l]||'candidate');
async function labRun(){
  const t=$('#labType').value, btn=$('#labRun'); btn.disabled=true;
  $('#stepper').hidden=false;
  $$('.stp').forEach(s=>s.classList.remove('active','done','refuted'));
  $$('.conn').forEach(c=>c.classList.remove('fill'));
  $('#labState').innerHTML='<div class="labstage" id="ls"></div>'; const ls=$('#ls');
  _s('pose','active'); await wait(340); _s('pose','done'); _conn(0);
  _s('state','active'); await wait(240);
  const id='ex'+(LAB.length); let entry=null;
  try{
   if(t==='graph'){
    const a=$('#labA').value,b=$('#labB').value;
    if(a===b){ls.innerHTML='Pick two different quantities.';btn.disabled=false;return;}
    ls.innerHTML='<div class="k">2 · State</div><div class="big">'+ruleTex(a+' <= '+b)+'</div>';
    await wait(480); _s('state','done'); _conn(1); _s('probe','active');
    ls.innerHTML+='<div class="labrow" id="pr">'+_pk+'<span class="spin"></span> stress-testing on the graph battery…</div>';
    const r=await jpost('/api/lab',{a,b});
    if(r.error){$('#pr').innerHTML=r.error;btn.disabled=false;return;}
    if(r.holds){_s('probe','done');_conn(2);
      $('#pr').innerHTML=_pk+'held on all '+r.tested+' graphs (tight on '+r.tight+') <span class="badge '+r.novelty+'">'+r.novelty+'</span>';
      await wait(320); _s('certify','active');
      if(r.mathlib_ready){ls.innerHTML+='<div class="labrow"><span class="k">4 · Certify</span>&nbsp;<button class="prv" id="cert_'+id+'" onclick="labCertify(\''+id+'\',\''+r.statement+'\')">Certify with Lean</button><span class="presult" id="cr_'+id+'"></span></div>';}
      else{_s('certify','done');ls.innerHTML+=_cr('<span style="color:var(--muted)">not expressible in mathlib yet — stays <b>'+r.novelty+'</b></span>');}
    }else{_s('probe','refuted');
      $('#pr').innerHTML=_pk+'<span class="bad">refuted</span> — counterexample <b>'+r.witness.graph+'</b>: '+r.a+'='+r.witness.a+' &gt; '+r.b+'='+r.witness.b;
      await wait(300); _s('pose','refuted');
      ls.innerHTML+='<div class="labrow" style="color:var(--muted)">↩ refuted — the loop returns to <b>Pose</b>: refine the hypothesis.</div>';}
    entry={id,type:'graph',tex:ruleTex(r.statement),title:r.statement,verdict:r.holds?('held '+r.tested+' graphs'):('refuted @ '+r.witness.graph),label:r.holds?r.novelty:'refuted',mathlib_ready:r.mathlib_ready,proof:null};
   }else if(t==='sequence'){
    const seq=$('#labSeq').value.split(',').map(s=>parseInt(s.trim())).filter(x=>!isNaN(x));
    ls.innerHTML='<div class="k">2 · State</div><div class="big mono">'+seq.slice(0,12).join(', ')+(seq.length>12?', …':'')+'</div>';
    await wait(480); _s('state','done'); _conn(1); _s('probe','active');
    ls.innerHTML+='<div class="labrow" id="pr">'+_pk+'<span class="spin"></span> searching for a pattern (PSLQ + OEIS)…</div>';
    const d=await jpost('/api/discover',{seq});
    const c=(d.candidates&&d.candidates[0])||null;
    const cf=c&&c.closed_form, lab=(c&&c.label&&c.label.status)||'', known=c&&c.verification&&c.verification.prior_art;
    _s('probe','done'); _conn(2);
    let pv = cf?('found a closed form: '+cfTex(cf)) : (lab.includes('mystery')?'stable “mystery” value — no known formula':'no formula found (often the honest answer)');
    if(known) pv+=' <span class="badge known">known: '+known+'</span>';
    $('#pr').innerHTML=_pk+pv;
    await wait(320); _s('certify','done');
    ls.innerHTML+=_cr('<span style="color:var(--muted)">'+(cf?'<b>REALISTIC</b> — a conjecture, not machine-proven here':(known?'prior art in OEIS':'nothing to certify'))+'</span>');
    entry={id,type:'sequence',tex:cf?cfTex(cf):'',title:seq.slice(0,12).join(','),verdict:cf?('formula found'):(lab.includes('mystery')?'mystery value':'no formula'),label:cf?'realistic':(known?'known':'none'),mathlib_ready:false,proof:cf?'conjecture (not certifiable here)':'n/a'};
   }else{
    const prob=$('#labProb').value, N=parseInt($('#labN').value)||1000;
    const pname=(LAB_PROBS.find(p=>p.key===prob)||{}).name||prob;
    ls.innerHTML='<div class="k">2 · State</div><div class="big">'+(LAB_MATH[prob]?kx(LAB_MATH[prob],true):pname)+'</div>';
    await wait(480); _s('state','done'); _conn(1); _s('probe','active');
    ls.innerHTML+='<div class="labrow" id="pr">'+_pk+'<span class="spin"></span> checking every n up to '+N+'…</div>';
    const v=await jpost('/api/verify_finite',{problem:prob,upto:N});
    if(v.error){$('#pr').innerHTML=v.error;btn.disabled=false;return;}
    if(v.holds){_s('probe','done');_conn(2);$('#pr').innerHTML=_pk+'holds for all n &le; '+v.checked_up_to+' <span class="badge derived">evidence</span>';}
    else{_s('probe','refuted');$('#pr').innerHTML=_pk+'<span class="bad">counterexample at '+v.counterexample+'!</span>';}
    await wait(320); _s('certify','refuted');
    ls.innerHTML+=_cr('<span class="bad">cannot be certified</span> — a famous open problem; a finite check is evidence, not a proof');
    entry={id,type:'finite',tex:LAB_MATH[prob]?kx(LAB_MATH[prob]):'',title:pname,verdict:v.holds?('holds &le; '+v.checked_up_to):('counterexample '+v.counterexample),label:'open',mathlib_ready:false,proof:'cannot certify (open problem)'};
   }
  }catch(e){$('#labState').innerHTML='<div class="labstage">error: '+e+'</div>';btn.disabled=false;return;}
  if(entry){LAB.unshift(entry);renderBook();}
  btn.disabled=false;
}
async function labCertify(id,stmt){
  const out=$('#cr_'+id),btn=$('#cert_'+id);btn.disabled=true; _s('certify','active');
  out.innerHTML='<span class="spin"></span> proving with Lean… (up to ~2 min)';
  const r=await jpost('/api/prove',{statement:stmt});
  if(r.status==='proved'){out.innerHTML='<span class="ok">✓ proved'+(r.lemma?(' via '+r.lemma):(' by '+r.tactic))+'</span>';
    _s('certify','done'); _conn(3); _s('theory','done'); _conn(4);}
  else if(r.status==='open'){out.innerHTML='<span>— open (needs a human proof)</span>';_s('certify','done');}
  else{out.innerHTML='<span>'+(r.note||r.status)+'</span>';}
  const e=LAB.find(x=>x.id===id); if(e){e.proof=(r.status==='proved')?('proved'+(r.lemma?(' · '+r.lemma):'')):r.status;} renderBook();
}
function renderBook(){
  $('#labempty').style.display=LAB.length?'none':'block';
  $('#labExport').hidden=!LAB.length;
  $('#labbook').innerHTML=LAB.map(e=>{
    const head=e.tex?e.tex:('<span class="mono">'+e.title+'</span>');
    return '<div class="nb"><div class="hyp">'+head+' <span class="badge '+_bcls(e.label)+'">'+e.label+'</span> <span class="st" style="opacity:.65">'+e.type+'</span></div>'+
      '<div class="stages"><span class="st"><b>Probe:</b> '+e.verdict+'</span>'+
      '<span class="st"><b>Certify:</b> '+(e.proof?e.proof:(e.mathlib_ready?'available':'n/a'))+'</span></div></div>';
  }).join('');
}
function labExport(){
  const data={tool:'MatyOS Lab',exported:new Date().toISOString(),
    experiments:LAB.map(e=>({type:e.type,claim:e.title,verdict:e.verdict,label:e.label,certify:e.proof||(e.mathlib_ready?'available':'n/a')}))};
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='matyos-lab-notebook.json';
  document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(a.href);
}
labInit();

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
        if self.path == "/api/invariants":
            from matyos.discovery import graph as g
            return self._send(200, json.dumps({"invariants": sorted(g.all_invariants().keys())}))
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
            if self.path == "/api/lab":
                p = self._body()
                return self._send(200, json.dumps(_lab_probe(p.get("a", ""), p.get("b", ""))))
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
