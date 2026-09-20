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
 .logo{width:34px;height:34px;border-radius:9px;background:var(--brand);color:#fff;
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
 @media(max-width:600px){.top{flex-wrap:wrap}}
</style></head><body>
<header><div class="wrap">
  <div class="top"><div class="logo">M</div><h1>MatyOS</h1><span class="pill">research console</span></div>
  <p class="tag">A workbench that finds small true patterns, checks them honestly, and proves the easy ones with a real theorem-checker. It <b>does not</b> solve famous open problems — and it says so.</p>
  <nav>
    <button class="on" data-tab="explore">Explore a sequence</button>
    <button data-tab="graph">Graph patterns</button>
    <button data-tab="problems">Hard problems</button>
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
<script>
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
async function jget(u){return (await fetch(u)).json()}
async function jpost(u,o){return (await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)})).json()}
$$('nav button').forEach(b=>b.onclick=()=>{
  $$('nav button').forEach(x=>x.classList.toggle('on',x===b));
  $$('.panel').forEach(p=>p.classList.toggle('on',p.id===b.dataset.tab));
});
function setSeq(s){$('#seq').value=s.split(',').join(', ')}

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
        if(cf){cls='found';big='Formula: '+cf}
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
  let h='<table><tr><th>rule (A ≤ B)</th><th>status</th><th>held / tight</th><th></th></tr>';
  for(const r of c){
    const canProve=r.mathlib_ready;
    h+=`<tr><td class="ineq">${r.statement}</td>`+
       `<td><span class="badge ${r.novelty}">${r.novelty}</span></td>`+
       `<td class="mono">${r.held_on} / ${r.tight_on}</td>`+
       `<td>${canProve?`<button class="prv" onclick="prove(this,'${r.statement}')">Prove</button><div class="presult"></div>`:''}</td></tr>`;
  }
  $('#conj').innerHTML=h+'</table>';
  const p=(await jget('/api/problems')).problems;
  $('#probs').innerHTML=p.map(x=>{
    const fin=x.finite_checkable;
    return `<div class="prob"><h3>${x.name}</h3>`+
      `<div class="can">✓ MatyOS can: ${x.matyos_can.join(', ')}.</div>`+
      `<div class="cant">✗ Cannot: ${x.matyos_cannot}.</div>`+
      (fin?`<div class="row" style="margin-top:10px"><input type="number" id="n_${x.key}" value="1000" min="4" style="max-width:130px">`+
        `<button class="prv" onclick="verify('${x.key}',this)">Verify up to N</button><span class="presult" id="v_${x.key}"></span></div>`:
        `<div class="lead" style="margin:8px 0 0">No finite check settles this one${x.key==='riemann'?' (needs the zeta function)':' (it asserts infinitely many cases)'}.</div>`)+
      `<details><summary>Formal Lean statement</summary><pre>${x.lean_statement.replace(/</g,'&lt;')}</pre></details></div>`;
  }).join('');
})();

async function prove(btn,stmt){
  const out=btn.nextElementSibling; btn.disabled=true;
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
            return self._send(200, _PAGE, "text/html; charset=utf-8")
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
