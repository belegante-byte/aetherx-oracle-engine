"""Aether-X Control Tower — dashboard local em tempo real.

Serve em uma porta local uma visão que faz polling contínuo do
`/internal/metrics` da produção (aetherx.aether-grid.io), injetando o
proxy secret. A página se atualiza sozinha (JS polling ~3s).

Uso:
    .venv/bin/python scripts/control_tower_local.py          # porta 8787
    .venv/bin/python scripts/control_tower_local.py --port 9000
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

load_dotenv(Path(__file__).resolve().parent.parent / "config" / ".env")

PROD_METRICS_URL = os.getenv(
    "AETHERX_PROD_METRICS_URL",
    "https://aetherx.aether-grid.io/internal/metrics",
)
SECRET = os.getenv("RAPIDAPI_PROXY_SECRET", "")
CACHE_TTL = 3  # segundos entre polls efetivos na produção

_cache: dict = {"ts": 0.0, "data": None, "error": None}


def _fmt_uptime(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s"


def _fmt_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")


def fetch_metrics() -> dict:
    """Busca o snapshot da produção, com cache curto para não estourar o serviço."""
    now = time.time()
    if _cache["data"] is not None and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["data"]
    try:
        req = urllib.request.Request(
            PROD_METRICS_URL,
            headers={"X-RapidAPI-Proxy-Secret": SECRET, "User-Agent": "aetherx-tower-local/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        _cache.update({"ts": now, "data": data, "error": None})
    except Exception as e:
        _cache["error"] = f"{type(e).__name__}: {e}"
    return _cache["data"] or {}


app = FastAPI(title="Aether-X Control Tower (local)")


@app.get("/metrics")
def metrics():
    data = fetch_metrics()
    data["_tower_error"] = _cache.get("error")
    data["_tower_fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return data


@app.get("/", response_class=HTMLResponse)
def index():
    return CONTROL_TOWER_HTML


CONTROL_TOWER_HTML = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aether-X Control Tower · LIVE</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,monospace;background:#0a0e14;color:#e6edf3;padding:2rem;font-size:14px}
h1{font-size:1.3rem;letter-spacing:2px;color:#58a6ff;margin-bottom:.4rem}
.sub{color:#6e7681;font-size:.75rem;margin-bottom:1.5rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem;max-width:1300px}
.card{background:#10161f;border:1px solid #1c2430;border-radius:8px;padding:1rem}
.card h2{font-size:.72rem;text-transform:uppercase;letter-spacing:1px;color:#8b949e;margin-bottom:.6rem;border-bottom:1px solid #1c2430;padding-bottom:.3rem}
.row{display:flex;justify-content:space-between;padding:2px 0}
.val{color:#e6edf3}
.muted{color:#6e7681}
.big{font-size:1.6rem;font-weight:700}
.green{color:limegreen}.blue{color:#58a6ff}.orange{color:orange}.red{color:#f85149}
.dot{font-size:.9rem}
.stat{padding:2px 0}
.event{display:flex;gap:.5rem;padding:2px 0;font-size:13px}
.event .ts{color:#6e7681}.event .kind{color:#8b949e}.event .det{color:#e6edf3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#status-bar{position:fixed;top:0;left:0;right:0;background:#0d1117;border-bottom:1px solid #1c2430;padding:.4rem 1rem;font-size:.72rem;color:#8b949e;z-index:10}
#status-bar b{color:limegreen}
@media(prefers-reduced-motion:no-preference){.live{animation:blink 1.5s infinite}}
@keyframes blink{50%{opacity:.35}}
</style></head><body>
<div id="status-bar"><b>●</b> <span id="last-update">conectando…</span> · fonte: <span id="src">…</span></div>
<br>
<h1>AETHER-X CONTROL TOWER <span class="live" style="color:limegreen">● LIVE</span></h1>
<div class="sub">tela local · polling produção a cada ~3s · <span id="clock"></span></div>
<div class="grid">
  <div class="card"><h2>SYSTEM</h2><div id="system">…</div></div>
  <div class="card"><h2>TOP TOOLS</h2><div id="tools">…</div></div>
  <div class="card"><h2>TOP PORTS</h2><div id="ports">…</div></div>
  <div class="card"><h2>MONETIZATION</h2><div id="money">…</div></div>
  <div class="card"><h2>DISCOVERY</h2><div id="discovery">…</div></div>
  <div class="card"><h2>DATA QUALITY</h2><div id="quality">…</div></div>
  <div class="card"><h2>RECENT EVENTS</h2><div id="events">…</div></div>
</div>
<script>
const COLORS = {live:'limegreen',indexing:'#58a6ff',pending:'orange',blocked:'#f85149'};
const ICONS = {tool_call:'🔧',port_query:'⚓',new_machine:'🆕',repeat_machine:'🔁',mcp_call:'🤖',error:'⚠️'};
function uptime(s){const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h?h+'h '+String(m).padStart(2,'0')+'m':m+'m '+String(s%60).padStart(2,'0')+'s';}
function ts(u){return new Date(u*1000).toISOString().slice(11,19);}
function esc(x){return String(x).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function render(d){
  if(!d||!d.uptime_seconds){document.getElementById('system').innerHTML='<div class="muted">sem dados / erro de conexão</div>';return;}
  const uniq=Object.values(d.unique_machines||{}).reduce((a,b)=>a+b,0);
  const rep=Object.values(d.repeat_machines||{}).reduce((a,b)=>a+b,0);
  const repRate=uniq?(rep/uniq*100).toFixed(1):'0.0';
  document.getElementById('system').innerHTML=
    '<div class="stat">SYSTEM <span class="green">● ONLINE</span></div>'+
    '<div class="stat">UPTIME <span class="val">'+uptime(d.uptime_seconds)+'</span></div>'+
    '<div class="stat">REQUESTS <span class="val big">'+(d.requests_total||0).toLocaleString()+'</span></div>'+
    '<div class="stat">MCP CALLS <span class="val big">'+(d.mcp_calls||0).toLocaleString()+'</span></div>'+
    '<div class="stat">MCP ERROS <span class="val">'+(d.mcp_errors||0)+'</span></div>'+
    '<div class="stat">UNIQUE M2M <span class="val">'+uniq+'</span></div>'+
    '<div class="stat">REPEAT <span class="val">'+rep+'</span></div>'+
    '<div class="stat">REPEAT RATE <span class="val">'+repRate+'%</span></div>'+
    '<div class="stat">ERROR RATE <span class="val">'+((d.error_rate||0)*100).toFixed(2)+'%</span></div>';
  document.getElementById('tools').innerHTML=(d.top_tools||[]).map(t=>'<div class="row"><span>'+esc(t[0])+'</span><span class="val">'+t[1]+'</span></div>').join('')||'<div class="muted">sem dados</div>';
  document.getElementById('ports').innerHTML=(d.top_ports||[]).map(p=>'<div class="row"><span>'+esc(p[0])+'</span><span class="val">'+p[1]+'</span></div>').join('')||'<div class="muted">sem dados</div>';
  const paidPlans=d.paid_plans||{};
  const paidTotal=Object.values(paidPlans).reduce((a,b)=>a+b,0);
  document.getElementById('money').innerHTML=
    '<div class="row"><span>PAID CALLS</span><span class="val big">'+paidTotal+'</span></div>'+
    '<div class="row"><span>PAID USERS</span><span class="val">'+(d.paid_user_count||0)+'</span></div>'+
    Object.entries(paidPlans).map(([p,c])=>'<div class="row"><span>'+esc(p)+'</span><span class="val">'+c+'</span></div>').join('')+
    ((d.paid_users||[]).slice(0,10).map(u=>'<div class="row muted"><span>'+esc(u)+'</span></div>').join(''))||'';
  const disc=[['MCP Registry','live'],['Glama','live'],['Smithery','live'],['RapidAPI','live'],['Google','indexing'],['public-apis','pending'],['GitHub','live'],['Hugging Face','live'],['PyPI','live'],['mcp.so','blocked'],['PulseMCP','blocked']];
  document.getElementById('discovery').innerHTML=disc.map(([n,s])=>'<div class="row"><span>'+n+'</span><span class="val"><span class="dot" style="color:'+(COLORS[s]||'gray')+'">'+(s==='blocked'?'○':'●')+'</span> '+s+'</span></div>').join('');
  const q=[['BRPNG','LIVE','VALIDATED','green'],['BRSSZ','LIVE','CONDITIONAL','orange'],['BRRIO','LIVE','CONDITIONAL','orange'],['BRNIT','LIVE','CONDITIONAL','orange'],['BRITG','LIVE','CONDITIONAL','orange']];
  document.getElementById('quality').innerHTML=q.map(([p,l,g,c])=>'<div class="row"><span>'+p+'</span><span class="val"><span class="dot" style="color:'+c+'">●</span> '+l+' / '+g+'</span></div>').join('')+'<div class="row muted"><span>+14 portos</span><span class="val">REFERENCE</span></div>';
  document.getElementById('events').innerHTML=(d.recent_events||[]).slice(0,30).map(e=>'<div class="event"><span class="ts">'+ts(e.ts)+'</span><span class="kind">'+(ICONS[e.kind]||'•')+' '+esc(e.kind)+'</span><span class="det">'+esc(e.detail||'')+'</span></div>').join('')||'<div class="muted">sem eventos</div>';
}
function tick(){const n=new Date();document.getElementById('clock').textContent=n.toLocaleTimeString('pt-BR');}
async function poll(){
  try{
    const r=await fetch('/metrics');
    const d=await r.json();
    render(d);
    const e=d._tower_error;
    document.getElementById('last-update').textContent='atualizado '+new Date().toLocaleTimeString('pt-BR')+(e?' · <span style="color:#f85149">'+e+'</span>':'');
    document.getElementById('src').textContent=d._tower_fetched_at||'';
  }catch(err){
    document.getElementById('last-update').innerHTML='<span class="red">erro: '+esc(err.message)+'</span>';
  }
}
setInterval(poll,3000);setInterval(tick,1000);poll();tick();
</script></body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Aether-X Control Tower local (tempo real)")
    parser.add_argument("--port", type=int, default=8787, help="porta local (padrão 8787)")
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    if not SECRET:
        print("⚠️  RAPIDAPI_PROXY_SECRET não encontrado em config/.env — dashboard não consegue ler produção.")
        sys.exit(1)
    print(f"▶  Aether-X Control Tower local em http://{args.host}:{args.port}")
    print(f"   fonte: {PROD_METRICS_URL}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()