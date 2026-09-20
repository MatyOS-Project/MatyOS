"""A local web dashboard for MatyOS — for a mathematical researcher.

Zero dependencies (Python stdlib ``http.server`` only), matching MatyOS's
no-runtime-deps rule. Run ``matyos-ui`` and open http://localhost:8000 .

It surfaces the three things a researcher actually works with:

* **Graph conjectures** — the classified shortlist (known / derived / candidate),
  candidates first: the bounds MatyOS's knowledge cannot yet explain.
* **Sequence explorer** — paste integers, run the discovery loop, see the honest
  labels (closed form / mystery / no formula), OEIS check included.
* **Hard problems** — the honest engagement layer: MatyOS states Riemann/Goldbach/
  twin-primes/Collatz formally and verifies finite cases; it never claims a proof.

Everything shown carries its honest label. Nothing here reports a famous conjecture
as solved.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

_CONJ_CACHE: list | None = None       # classified_search is deterministic + heavy → compute once


def _conjectures() -> list:
    global _CONJ_CACHE
    if _CONJ_CACHE is None:
        from matyos.discovery import graph as g
        _CONJ_CACHE = g.classified_search()
    return _CONJ_CACHE

_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>MatyOS — researcher console</title>
<style>
 :root{--bg:#faf9f6;--ink:#1a1a2e;--muted:#6b7280;--line:#e5e3dc;
   --known:#8a8f98;--derived:#3b6ea5;--candidate:#b4531f;--accent:#2d6a4f}
 body{margin:0;background:var(--bg);color:var(--ink);
   font:14px/1.55 -apple-system,Segoe UI,Roboto,sans-serif}
 header{padding:22px 28px;border-bottom:1px solid var(--line)}
 h1{margin:0;font-size:20px}.sub{color:var(--muted);margin-top:4px}
 main{max-width:960px;margin:0 auto;padding:24px 28px;display:grid;gap:28px}
 section{border:1px solid var(--line);border-radius:10px;background:#fff}
 section>h2{margin:0;padding:14px 18px;font-size:15px;border-bottom:1px solid var(--line)}
 .body{padding:16px 18px}
 table{width:100%;border-collapse:collapse;font-size:13px}
 td,th{padding:6px 8px;text-align:left;border-bottom:1px solid var(--line)}
 th{color:var(--muted);font-weight:600}
 .tag{font-size:11px;font-weight:700;padding:2px 7px;border-radius:999px;color:#fff}
 .known{background:var(--known)}.derived{background:var(--derived)}.candidate{background:var(--candidate)}
 code{background:#f2f0ea;padding:1px 5px;border-radius:4px}
 input,button{font:inherit;padding:7px 10px;border:1px solid var(--line);border-radius:7px}
 button{background:var(--accent);color:#fff;border:0;cursor:pointer}
 .note{color:var(--muted);font-size:12px;margin-top:8px}
 .banner{background:#fff6ef;border:1px solid #f0d9c8;color:#8a4b23;
   padding:10px 14px;border-radius:8px;font-size:12.5px}
</style></head><body>
<header><h1>MatyOS — researcher console</h1>
<div class="sub">A conjecture &amp; verification workbench. It surfaces candidate facts, checks them honestly, and states hard problems formally — it does not solve famous open problems.</div>
</header>
<main>
 <section><h2>Graph conjectures — classified</h2><div class="body">
   <div id="conj">loading…</div>
   <div class="note"><span class="tag candidate">candidate</span> = not explained by MatyOS's known-inequality DB (a lead, not a claim) · <span class="tag derived">derived</span> = implied by known bounds · <span class="tag known">known</span> = an established theorem.</div>
 </div></section>
 <section><h2>Sequence explorer</h2><div class="body">
   <input id="seq" size="52" placeholder="e.g. 0,1,1,2,3,5,8,13,21,34" value="0,1,1,2,3,5,8,13,21,34">
   <button onclick="explore()">Discover</button>
   <div id="disc" class="note">Paste integers; MatyOS runs its discovery loop and reports honest labels.</div>
 </div></section>
 <section><h2>Hard problems — honest engagement</h2><div class="body">
   <div class="banner">MatyOS can <b>state</b> these formally (Lean+mathlib) and <b>verify finite</b> cases; it <b>cannot</b> prove them, and never reports one as solved.</div>
   <div id="probs" class="note">loading…</div>
 </div></section>
</main>
<script>
async function j(u,o){const r=await fetch(u,o);return r.json()}
(async()=>{
 const c=await j('/api/conjectures');
 let h='<table><tr><th>inequality</th><th>novelty</th><th>tight</th></tr>';
 for(const r of c.conjectures){h+=`<tr><td><code>${r.statement}</code></td>`+
   `<td><span class="tag ${r.novelty}">${r.novelty}</span></td><td>${r.tight_on}/${r.held_on}</td></tr>`}
 document.getElementById('conj').innerHTML=h+'</table>';
 const p=await j('/api/problems');
 document.getElementById('probs').innerHTML=p.problems.map(x=>
   `<div style="margin:6px 0"><b>${x.name}</b> — MatyOS can: ${x.matyos_can.join(', ')}. `+
   `<i>Cannot: ${x.matyos_cannot}.</i></div>`).join('');
})();
async function explore(){
 const seq=document.getElementById('seq').value.split(',').map(s=>parseInt(s.trim())).filter(x=>!isNaN(x));
 document.getElementById('disc').textContent='running…';
 const d=await j('/api/discover',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({seq})});
 if(!d.candidates||!d.candidates.length){document.getElementById('disc').textContent='No candidate found (honest: often the right answer).';return}
 document.getElementById('disc').innerHTML=d.candidates.map(r=>
   `<div style="margin:6px 0">${r.closed_form?('<code>'+r.closed_form+'</code>'):'(no closed form)'} — `+
   `label: <b>${(r.label&&r.label.status)||'—'}</b>${r.verification&&r.verification.prior_art?(' · prior art: '+r.verification.prior_art):''}</div>`).join('');
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

    def log_message(self, *a):            # quiet
        pass

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            return self._send(200, _PAGE, "text/html; charset=utf-8")
        if self.path == "/api/conjectures":
            return self._send(200, json.dumps({"conjectures": _conjectures()}))
        if self.path == "/api/problems":
            from matyos.problems import famous as F
            probs = [F.status(k) for k in F.REGISTRY]
            return self._send(200, json.dumps({"problems": probs}))
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path != "/api/discover":
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
            seq = [int(x) for x in payload.get("seq", [])]
            if len(seq) < 4:
                return self._send(200, json.dumps({"candidates": [],
                                  "note": "give at least 4 integers"}))
            from matyos.discovery.objects import Sequence
            from matyos.discovery.engine import DiscoveryEngine
            recs = DiscoveryEngine(min_score=0.0).records([Sequence.of(seq, name="ui")])
            return self._send(200, json.dumps({"candidates": recs[:5]}))
        except Exception as e:                # a bad request must not crash the server
            return self._send(200, json.dumps({"candidates": [], "note": f"error: {e}"}))


def serve(port: int = 8000, host: str = "127.0.0.1") -> None:
    httpd = HTTPServer((host, port), _Handler)
    print(f"MatyOS researcher console → http://{host}:{port}  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="MatyOS local researcher console")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    serve(args.port, args.host)


if __name__ == "__main__":
    main()
