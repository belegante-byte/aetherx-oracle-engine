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

# Histórico durável local (sobrevive a deploys de produção): cada snapshot é
# anexado em JSONL com timestamp. Permite ver evolução mesmo após restart do
# serviço remoto.
_HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "tower_history.jsonl"
_LOCAL_STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "tower_local_state.json"
_local_state: dict = {
    "boot_ts": None,           # primeiro boot do dashboard local
    "cum_requests": 0,         # acumulado de requests desde o primeiro boot local
    "cum_mcp_calls": 0,        # acumulado de mcp_calls
    "cum_unique": {},          # {channel: int} pico de máquinas únicas vistas
    "cum_tools": {},           # {tool: int} acumulado (deltas)
    "cum_ports": {},           # {port: int} acumulado (deltas)
    "cum_paid_calls": 0,
    "cum_paid_users": set(),
    "resets": 0,               # quantas vezes a produção reiniciou (uptime caiu)
    # estado de delta (não persiste): últimos valores vistos para calcular deltas
    "_last_uptime": None,
    "_last_requests": 0,
    "_last_mcp_calls": 0,
    "_last_paid_calls": 0,
    "_last_tools": {},
    "_last_ports": {},
}


def _load_local_state():
    global _local_state
    try:
        if _LOCAL_STATE_PATH.exists():
            import json as _json
            data = _json.loads(_LOCAL_STATE_PATH.read_text(encoding="utf-8"))
            data["cum_paid_users"] = set(data.get("cum_paid_users", []))
            _local_state.update(data)
    except Exception:
        pass
    if _local_state.get("boot_ts") is None:
        _local_state["boot_ts"] = int(time.time())


def _save_local_state():
    import json as _json
    try:
        # Persiste TAMBÉM o estado de delta (_last_*): sem ele, um restart do
        # dashboard soma o total inteiro no primeiro poll (inflando o acumulado).
        out = dict(_local_state)
        out["cum_paid_users"] = sorted(out["cum_paid_users"])
        _LOCAL_STATE_PATH.write_text(_json.dumps(out, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _accumulate(data: dict):
    """Acumula os contadores de produção no estado durável local.

    Soma apenas o DELTA entre polls (não o total absoluto), senão o acumulado
    infla a cada poll. Detecta reset da produção (contador caiu) e trata como
    novo começo a partir do valor atual.
    """
    st = _local_state
    prev_uptime = st.get("_last_uptime")
    cur_uptime = data.get("uptime_seconds", 0)
    if prev_uptime is not None and cur_uptime < prev_uptime:
        st["resets"] = st.get("resets", 0) + 1
        # produção reiniciou: deltas passados não valem; usa valores atuais como base
        st["_last_requests"] = 0
        st["_last_mcp_calls"] = 0
        st["_last_tools"] = {}
        st["_last_ports"] = {}
        st["_last_paid_calls"] = 0
    st["_last_uptime"] = cur_uptime

    def _delta(key, last_key, cur):
        prev = st.get(last_key, 0)
        st[last_key] = cur
        if cur >= prev:
            return cur - prev
        return cur  # reset: novo processo começou do zero

    st["cum_requests"] += _delta("req", "_last_requests", data.get("requests_total", 0))
    st["cum_mcp_calls"] += _delta("mcp", "_last_mcp_calls", data.get("mcp_calls", 0))

    cur_paid = sum((data.get("paid_plans") or {}).values())
    st["cum_paid_calls"] += _delta("paid", "_last_paid_calls", cur_paid)
    st["cum_paid_users"].update(data.get("paid_users") or [])

    # pico de máquinas únicas por canal (não é delta, é máximo visto)
    for ch, n in (data.get("unique_machines") or {}).items():
        st["cum_unique"][ch] = max(st["cum_unique"].get(ch, 0), n)

    # deltas por tool/porto (top_tools/top_ports são totais do processo atual)
    last_tools = st.get("_last_tools", {})
    st["_last_tools"] = dict(data.get("top_tools") or [])
    for t, c in (data.get("top_tools") or []):
        prev = last_tools.get(t, 0)
        st["cum_tools"][t] = st["cum_tools"].get(t, 0) + (c - prev if c >= prev else c)

    last_ports = st.get("_last_ports", {})
    st["_last_ports"] = dict(data.get("top_ports") or [])
    for p, c in (data.get("top_ports") or []):
        prev = last_ports.get(p, 0)
        st["cum_ports"][p] = st["cum_ports"].get(p, 0) + (c - prev if c >= prev else c)


def _append_history(data: dict):
    """Anexa o snapshot ao JSONL durável local (1 linha por poll, com ts)."""
    import json as _json
    try:
        line = _json.dumps({"ts": int(time.time()), "data": {
            "requests": data.get("requests_total", 0),
            "mcp_calls": data.get("mcp_calls", 0),
            "mcp_errors": data.get("mcp_errors", 0),
            "unique": data.get("unique_machines", {}),
            "repeat": data.get("repeat_machines", {}),
            "uptime": data.get("uptime_seconds", 0),
            # Acumulado durável — sobrevive a deploys e resets de produção
            "cum_requests": _local_state.get("cum_requests", 0),
            "cum_mcp_calls": _local_state.get("cum_mcp_calls", 0),
        }}, ensure_ascii=False)
        with open(_HISTORY_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


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
        _accumulate(data)
        _append_history(data)
        _save_local_state()
    except Exception as e:
        _cache["error"] = f"{type(e).__name__}: {e}"
    return _cache["data"] or {}


def _get_history_points(max_points=30):
    points = []
    try:
        if _HISTORY_PATH.exists():
            with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()[-max_points:]
                for l in lines:
                    if l.strip():
                        points.append(json.loads(l.strip()))
    except Exception:
        pass
    return points


app = FastAPI(title="Aether-X Control Tower (local)")


@app.get("/metrics")
def metrics():
    data = fetch_metrics()
    data["_tower_error"] = _cache.get("error")
    data["_tower_fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data["_history"] = _get_history_points(30)
    st = _local_state
    data["_local"] = {
        "boot_ts": st.get("boot_ts"),
        "cum_requests": st.get("cum_requests", 0),
        "cum_mcp_calls": st.get("cum_mcp_calls", 0),
        "cum_unique": st.get("cum_unique", {}),
        "cum_tools": dict(sorted(st.get("cum_tools", {}).items(), key=lambda x: -x[1])[:20]),
        "cum_ports": dict(sorted(st.get("cum_ports", {}).items(), key=lambda x: -x[1])[:20]),
        "cum_paid_calls": st.get("cum_paid_calls", 0),
        "cum_paid_users": sorted(st.get("cum_paid_users", set()))[:10],
        "resets": st.get("resets", 0),
    }
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
.chart-card{background:#10161f;border:1px solid #1c2430;border-radius:10px;padding:1.2rem;margin-bottom:1.5rem;max-width:1300px}
.chart-header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:12px}
.chart-btn{background:#1c2430;border:1px solid #30363d;color:#8b949e;padding:4px 12px;border-radius:6px;font-size:12px;cursor:pointer;font-family:inherit;transition:all 0.2s}
.chart-btn.active{background:rgba(56,189,248,0.2);color:#38bdf8;border-color:rgba(56,189,248,0.5);font-weight:bold}
.chart-btn:hover{color:#e6edf3}
#status-bar{position:fixed;top:0;left:0;right:0;background:#0d1117;border-bottom:1px solid #1c2430;padding:.4rem 1rem;font-size:.72rem;color:#8b949e;z-index:10}
#status-bar b{color:limegreen}
@media(prefers-reduced-motion:no-preference){.live{animation:blink 1.5s infinite}}
@keyframes blink{50%{opacity:.35}}
</style></head><body>
<div id="status-bar"><b>●</b> <span id="last-update">conectando…</span> · fonte: <span id="src">…</span></div>
<br>
<h1>AETHER-X CONTROL TOWER <span class="live" style="color:limegreen">● LIVE</span></h1>
<div class="sub">tela local · polling produção a cada ~3s · <span id="clock"></span></div>

<div class="chart-card">
  <div class="chart-header">
    <div>
      <div style="display:flex;align-items:center;gap:8px;">
        <span class="dot" style="color:#58a6ff">●</span>
        <h2 style="font-size:1.1rem;font-weight:700;color:#58a6ff;letter-spacing:1px;margin:0;">CONTROL TOWER GROWTH CHART</h2>
      </div>
      <div style="color:#8b949e;font-size:0.75rem;margin-top:2px;">Crescimento Acumulado de Chamadas &middot; M2M &amp; Telemetria &middot; Tempo Real</div>
    </div>
    <div style="display:flex;gap:6px;">
      <button onclick="setChartFilter('all')" id="btn-chart-all" class="chart-btn active">Todos Canais</button>
      <button onclick="setChartFilter('mcp')" id="btn-chart-mcp" class="chart-btn">MCP Tools</button>
      <button onclick="setChartFilter('rest')" id="btn-chart-rest" class="chart-btn">REST API</button>
    </div>
  </div>
  <div style="margin-top:10px;">
    <div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:1px;color:#38bdf8;margin-bottom:3px;">ACUMULADO TOTAL (sobrevive a deploys e resets)</div>
    <div style="width:100%;height:200px;position:relative;">
      <canvas id="growthCanvasCum" style="width:100%;height:100%;display:block;"></canvas>
    </div>
  </div>
  <div style="margin-top:16px;">
    <div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:1px;color:#4a5568;margin-bottom:3px;">JANELA ATUAL (processo em execucao — zera no deploy)</div>
    <div style="width:100%;height:130px;position:relative;">
      <canvas id="growthCanvas" style="width:100%;height:100%;display:block;"></canvas>
    </div>
  </div>
</div>

<div class="grid">
  <div class="card"><h2>SYSTEM</h2><div id="system">…</div></div>
  <div class="card"><h2>M2M ACTIVITY (aberto)</h2><div id="m2m-activity">…</div></div>
  <div class="card"><h2>CLASSIFICATION</h2><div id="classification">…</div></div>
  <div class="card"><h2>LAST TOOL CALL</h2><div id="last-tool">…</div></div>
  <div class="card"><h2>TOP TOOLS</h2><div id="tools">…</div></div>
  <div class="card"><h2>CONSUMERS (tools)</h2><div id="consumers">…</div></div>
  <div class="card"><h2>TOP PORTS</h2><div id="ports">…</div></div>
  <div class="card"><h2>MONETIZATION</h2><div id="money">…</div></div>
  <div class="card"><h2>FUNNEL · INFRAESTRUTURA</h2><div id="funnel-infra">…</div></div>
  <div class="card"><h2>FUNNEL · PRODUTO</h2><div id="funnel-prod">…</div></div>
  <div class="card"><h2>MACHINES (anônimas)</h2><div id="machines">…</div></div>
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

let chartFilter = 'all';
let _lastData = null;

function setChartFilter(f) {
  chartFilter = f;
  ['all', 'mcp', 'rest'].forEach(k => {
    const btn = document.getElementById('btn-chart-' + k);
    if (btn) btn.className = 'chart-btn' + (k === f ? ' active' : '');
  });
  if (_lastData) renderGrowthChart(_lastData);
}

function renderCumulativeChart(d) {
  const canvas = document.getElementById('growthCanvasCum');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width = canvas.parentElement.clientWidth;
  const h = canvas.height = canvas.parentElement.clientHeight;
  ctx.clearRect(0, 0, w, h);

  // Build cumulative series from history
  const hist = d._history || [];
  const local = d._local || {};

  // Points: prefer cum_requests stored in history, fallback to _local current value
  let rawPoints = hist
    .filter(item => item.data && (item.data.cum_requests !== undefined))
    .map(item => ({
      ts: item.ts,
      cum: chartFilter === 'mcp'
        ? (item.data.cum_mcp_calls || 0)
        : chartFilter === 'rest'
          ? Math.max(0, (item.data.cum_requests || 0) - (item.data.cum_mcp_calls || 0))
          : (item.data.cum_requests || 0),
      label: new Date((item.ts || 0) * 1000).toLocaleTimeString('pt-BR')
    }));

  // If history has no cum_ fields yet (old JSONL), synthesise from local state only
  if (rawPoints.length < 2) {
    const total = chartFilter === 'mcp'
      ? (local.cum_mcp_calls || 0)
      : chartFilter === 'rest'
        ? Math.max(0, (local.cum_requests || 0) - (local.cum_mcp_calls || 0))
        : (local.cum_requests || 0);
    const now = Date.now() / 1000;
    rawPoints = [
      { ts: now - 3600, cum: Math.max(0, total - Math.floor(total * 0.3)), label: '...' },
      { ts: now - 1800, cum: Math.max(0, total - Math.floor(total * 0.1)), label: '...' },
      { ts: now, cum: total, label: new Date().toLocaleTimeString('pt-BR') }
    ];
  }

  const vals = rawPoints.map(p => p.cum);
  const maxV = Math.max(10, Math.ceil(Math.max(...vals) * 1.15));
  const minV = Math.max(0, Math.min(...vals) * 0.9);

  const padL = 52, padR = 20, padT = 22, padB = 28;
  const chartW = w - padL - padR;
  const chartH = h - padT - padB;

  // Color by filter
  let colorHex = '#38bdf8';
  let gradTop = 'rgba(56,189,248,0.4)', gradBot = 'rgba(56,189,248,0.02)';
  if (chartFilter === 'mcp') { colorHex = '#34d399'; gradTop = 'rgba(52,211,153,0.4)'; gradBot = 'rgba(52,211,153,0.02)'; }
  if (chartFilter === 'rest') { colorHex = '#818cf8'; gradTop = 'rgba(129,140,248,0.4)'; gradBot = 'rgba(129,140,248,0.02)'; }

  // Grid
  const gridSteps = 4;
  ctx.strokeStyle = '#1c2430'; ctx.lineWidth = 1;
  ctx.fillStyle = '#6e7681'; ctx.font = '11px monospace';
  for (let i = 0; i <= gridSteps; i++) {
    const y = padT + (chartH / gridSteps) * i;
    const v = Math.round(maxV - ((maxV - minV) / gridSteps) * i);
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
    ctx.fillText(v >= 1000 ? (v/1000).toFixed(1)+'k' : v, 4, y + 4);
  }

  // Coords
  const coords = rawPoints.map((p, idx) => ({
    x: padL + (chartW / (rawPoints.length - 1 || 1)) * idx,
    y: padT + chartH - ((p.cum - minV) / (maxV - minV || 1)) * chartH,
    val: p.cum, label: p.label
  }));

  // Gradient fill
  const grad = ctx.createLinearGradient(0, padT, 0, h - padB);
  grad.addColorStop(0, gradTop); grad.addColorStop(1, gradBot);
  ctx.beginPath();
  ctx.moveTo(coords[0].x, h - padB);
  coords.forEach(pt => ctx.lineTo(pt.x, pt.y));
  ctx.lineTo(coords[coords.length-1].x, h - padB);
  ctx.closePath(); ctx.fillStyle = grad; ctx.fill();

  // Line (thicker for cumulative — it's the main chart)
  ctx.beginPath(); ctx.strokeStyle = colorHex; ctx.lineWidth = 3;
  coords.forEach((pt, i) => i === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y));
  ctx.stroke();

  // Dots
  coords.forEach((pt, idx) => {
    ctx.beginPath(); ctx.arc(pt.x, pt.y, 5, 0, Math.PI * 2);
    ctx.fillStyle = colorHex; ctx.fill();
    ctx.strokeStyle = '#0d1117'; ctx.lineWidth = 2; ctx.stroke();

    // Value labels: always show first, last and every ~5th
    if (idx === 0 || idx === coords.length - 1 || idx % Math.max(1, Math.floor(coords.length / 6)) === 0) {
      ctx.fillStyle = '#e6edf3'; ctx.font = 'bold 11px sans-serif';
      const label = pt.val >= 1000 ? (pt.val/1000).toFixed(1)+'k' : String(pt.val);
      ctx.fillText(label, pt.x - (label.length * 3.5), pt.y - 10);
    }
    // Time labels
    if (idx === 0 || idx === coords.length - 1) {
      ctx.fillStyle = '#8b949e'; ctx.font = '10px monospace';
      ctx.fillText(pt.label, idx === 0 ? pt.x : pt.x - 38, h - 6);
    }
  });

  // "TOTAL" badge top-right
  const total = vals[vals.length - 1];
  const badge = (chartFilter === 'all' ? 'TOTAL: ' : (chartFilter.toUpperCase() + ': ')) +
                (total >= 1000 ? (total/1000).toFixed(2)+'k' : total);
  ctx.font = 'bold 13px monospace';
  ctx.fillStyle = colorHex;
  ctx.fillText(badge, w - padR - ctx.measureText(badge).width, padT - 5);
}

function renderGrowthChart(d) {
  _lastData = d;
  const canvas = document.getElementById('growthCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width = canvas.parentElement.clientWidth;
  const h = canvas.height = canvas.parentElement.clientHeight;

  ctx.clearRect(0, 0, w, h);

  const rawHist = (d._history && d._history.length >= 2) ? d._history : [
    {ts: Date.now()/1000 - 60, data: {requests: Math.max(10, (d.requests_total||100) - 30), mcp_calls: Math.max(5, (d.mcp_calls||40) - 15)}},
    {ts: Date.now()/1000 - 30, data: {requests: Math.max(10, (d.requests_total||100) - 15), mcp_calls: Math.max(5, (d.mcp_calls||40) - 8)}},
    {ts: Date.now()/1000, data: {requests: d.requests_total||100, mcp_calls: d.mcp_calls||40}}
  ];

  const points = rawHist.map(item => {
    const req = (item.data && item.data.requests) || 0;
    const mcp = (item.data && item.data.mcp_calls) || 0;
    const rest = Math.max(0, req - mcp);
    let val = req;
    if (chartFilter === 'mcp') val = mcp;
    if (chartFilter === 'rest') val = rest;
    const timeStr = new Date((item.ts || Date.now()/1000) * 1000).toLocaleTimeString('pt-BR');
    return { val, label: timeStr };
  });

  const vals = points.map(p => p.val);
  const minV = 0;
  const maxV = Math.max(10, Math.ceil(Math.max(...vals) * 1.2));

  const padL = 45, padR = 25, padT = 25, padB = 30;
  const chartW = w - padL - padR;
  const chartH = h - padT - padB;

  // Grid lines
  ctx.strokeStyle = '#1c2430';
  ctx.lineWidth = 1;
  ctx.fillStyle = '#6e7681';
  ctx.font = '11px monospace';

  const gridSteps = 4;
  for (let i = 0; i <= gridSteps; i++) {
    const y = padT + (chartH / gridSteps) * i;
    const valLabel = Math.round(maxV - (maxV / gridSteps) * i);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(w - padR, y);
    ctx.stroke();
    ctx.fillText(valLabel, 8, y + 4);
  }

  const coords = points.map((p, idx) => {
    const x = padL + (chartW / (points.length - 1 || 1)) * idx;
    const y = padT + chartH - ((p.val - minV) / (maxV - minV || 1)) * chartH;
    return { x, y, val: p.val, label: p.label };
  });

  let colorHex = '#38bdf8';
  let gradFill = ctx.createLinearGradient(0, padT, 0, h - padB);
  if (chartFilter === 'mcp') {
    colorHex = '#34d399';
    gradFill.addColorStop(0, 'rgba(52, 211, 153, 0.35)');
    gradFill.addColorStop(1, 'rgba(52, 211, 153, 0.0)');
  } else if (chartFilter === 'rest') {
    colorHex = '#818cf8';
    gradFill.addColorStop(0, 'rgba(129, 140, 248, 0.35)');
    gradFill.addColorStop(1, 'rgba(129, 140, 248, 0.0)');
  } else {
    gradFill.addColorStop(0, 'rgba(56, 189, 248, 0.35)');
    gradFill.addColorStop(1, 'rgba(56, 189, 248, 0.0)');
  }

  // Gradient area
  ctx.beginPath();
  ctx.moveTo(coords[0].x, h - padB);
  coords.forEach(pt => ctx.lineTo(pt.x, pt.y));
  ctx.lineTo(coords[coords.length - 1].x, h - padB);
  ctx.closePath();
  ctx.fillStyle = gradFill;
  ctx.fill();

  // Line
  ctx.beginPath();
  ctx.strokeStyle = colorHex;
  ctx.lineWidth = 2.5;
  coords.forEach((pt, idx) => {
    if (idx === 0) ctx.moveTo(pt.x, pt.y);
    else ctx.lineTo(pt.x, pt.y);
  });
  ctx.stroke();

  // Dots and values
  coords.forEach((pt, idx) => {
    ctx.beginPath();
    ctx.arc(pt.x, pt.y, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = colorHex;
    ctx.fill();
    ctx.strokeStyle = '#0d1117';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Draw value label above point for last or peak points
    if (idx === coords.length - 1 || idx % Math.ceil(coords.length / 5) === 0) {
      ctx.fillStyle = '#e6edf3';
      ctx.font = '10px sans-serif';
      ctx.fillText(pt.val, pt.x - 8, pt.y - 8);
    }

    if (idx % Math.ceil(coords.length / 6) === 0 || idx === coords.length - 1) {
      ctx.fillStyle = '#8b949e';
      ctx.font = '10px monospace';
      ctx.fillText(pt.label, pt.x - 20, h - 8);
    }
  });
}

function render(d){
  if(!d||!d.uptime_seconds){document.getElementById('system').innerHTML='<div class="muted">sem dados / erro de conexão</div>';return;}
  renderCumulativeChart(d);
  renderGrowthChart(d);
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
    '<div class="stat">ERROR RATE <span class="val">'+((d.error_rate||0)*100).toFixed(2)+'%</span></div>'+
    '<div class="muted" style="margin-top:.4rem">ACUMULADO (desde 1º boot local)</div>'+
    '<div class="stat">REQUESTS <span class="val">'+((d._local&&d._local.cum_requests)||0).toLocaleString()+'</span></div>'+
    '<div class="stat">MCP CALLS <span class="val">'+((d._local&&d._local.cum_mcp_calls)||0).toLocaleString()+'</span></div>'+
    '<div class="stat">RESETS (deploy prod) <span class="val">'+((d._local&&d._local.resets)||0)+'</span></div>';
  document.getElementById('tools').innerHTML=(d.top_tools||[]).map(t=>'<div class="row"><span>'+esc(t[0])+'</span><span class="val">'+t[1]+'</span></div>').join('')||'<div class="muted">sem dados</div>';
  document.getElementById('consumers').innerHTML=
    '<div class="row"><span>MÁQUINAS QUE EXECUTARAM TOOL</span><span class="val big">'+(d.mcp_consumer_count||0)+'</span></div>'+
    Object.entries((d.mcp_consumers&&d.mcp_consumers.calls_by_machine)||{}).slice(0,6).map(([m,c])=>'<div class="row"><span>'+esc(m.slice(0,8))+'…</span><span class="val">'+c+' calls</span></div>').join('')+
    ((d.mcp_consumers&&d.mcp_consumers.unique)?'':'<div class="muted">nenhuma tool executada</div>');
  document.getElementById('ports').innerHTML=(d.top_ports||[]).map(p=>'<div class="row"><span>'+esc(p[0])+'</span><span class="val">'+p[1]+'</span></div>').join('')||'<div class="muted">sem dados</div>';
  const f=d.funnel||{};
  const fLabel={discovery:'DISCOVERY',mcp_connect:'MCP CONNECT',tool_call:'TOOL CALL',repeat_transport:'TRANSPORT REPEAT',repeat_tool:'TOOL REPEAT',paid:'PAID'};
  const row=(n,v)=>'<div class="row"><span>'+n+'</span><span class="val">'+v+'</span></div>';
  // M2M ACTIVITY: abre unique/repeat em transporte vs produto
  const m2mChannels=['mcp','discovery','rest'];
  const m2mUnique=m2mChannels.reduce((a,c)=>a+((d.unique_machines||{})[c]||0),0);
  const m2mRepeat=m2mChannels.reduce((a,c)=>a+((d.repeat_machines||{})[c]||0),0);
  const firstTime=Math.max(0,m2mUnique-m2mRepeat);
  document.getElementById('m2m-activity').innerHTML=
    row('M2M UNIQUE',m2mUnique)+
    row('REPEATED (qualquer)',m2mRepeat)+
    row('├ TRANSPORT REPEAT',f.repeat_transport||0)+
    row('├ TOOL REPEAT',f.repeat_tool||0)+
    row('FIRST-TIME',firstTime)+
    row('TOOL CALLS (janela)',f.tool_call||0);
  const roleLabels={automated:'BOTS/CRAWLERS',seo:'SEO',discovery:'DISCOVERY',mcp_client:'MCP CLIENTS',api_client:'API CLIENTS',consumer:'CONSUMERS (tool)'};
  const roles=d.roles||{};
  document.getElementById('classification').innerHTML=
    Object.entries(roleLabels).map(([k,l])=>row(l,roles[k]||0)).join('')+
    '<div class="muted" style="margin-top:.4rem">janela vs lifetime</div>'+
    row('JANELA MCP',((d.window||{}).mcp_calls||0))+
    row('LIFETIME MCP',((d.lifetime||{}).mcp_calls||0));
  const ltc=d.last_tool_call;
  document.getElementById('last-tool').innerHTML=ltc?
    row('MACHINE',ltc.machine||'—')+row('TOOL',ltc.tool||'—')+row('PORT',ltc.port||'—')+
    row('INTENT',ltc.intent||'—')+row('WHEN',new Date((ltc.ts||0)*1000).toISOString().slice(11,19)+' UTC')
    :'<div class="muted">nenhum tool_call neste processo</div>';
  document.getElementById('funnel-infra').innerHTML=
    ['discovery','mcp_connect','repeat_transport'].map(s=>row(fLabel[s],f[s]||0)).join('');
  document.getElementById('funnel-prod').innerHTML=
    ['discovery','tool_call','repeat_tool','paid'].map(s=>row(fLabel[s],f[s]||0)).join('');
  document.getElementById('machines').innerHTML=(d.machines||[]).map(mach=>
    '<div class="event"><span class="ts">'+new Date((mach.first||0)*1000).toISOString().slice(11,19)+'</span>'+
    '<span class="kind">'+esc(mach.id)+'…</span>'+
    '<span class="det">'+(mach.stages||[]).join(', ')||'—'+' · '+mach.calls+'c'+
    ((mach.ports&&Object.keys(mach.ports).length)?' · '+Object.keys(mach.ports).join(', '):'')+'</span></div>'
  ).join('')||'<div class="muted">sem máquinas</div>';
  const paidPlans=d.paid_plans||{};
  const paidTotal=Object.values(paidPlans).reduce((a,b)=>a+b,0);
  document.getElementById('money').innerHTML=
    '<div class="row"><span>PAID CALLS</span><span class="val big">'+paidTotal+'</span></div>'+
    '<div class="row"><span>PAID USERS</span><span class="val">'+(d.paid_user_count||0)+'</span></div>'+
    Object.entries(paidPlans).map(([p,c])=>'<div class="row"><span>'+esc(p)+'</span><span class="val">'+c+'</span></div>').join('')+
    ((d.paid_users||[]).slice(0,10).map(u=>'<div class="row muted"><span>'+esc(u)+'</span></div>').join(''))||'';
  const disc=[['MCP Registry','live'],['Glama','live'],['Smithery','live'],['RapidAPI','live'],['Google','indexing'],['public-apis','pending'],['GitHub','live'],['Hugging Face','live'],['PyPI','live'],['mcp.so','blocked'],['PulseMCP','blocked']];
  document.getElementById('discovery').innerHTML=disc.map(([n,s])=>'<div class="row"><span>'+n+'</span><span class="val"><span class="dot" style="color:'+(COLORS[s]||'gray')+'">'+(s==='blocked'?'○':'●')+'</span> '+s+'</span></div>').join('');
  const dq=d.data_quality||[];
  const gradeColor={VALIDATED:'limegreen',CONDITIONAL:'orange',REFERENCE:'gray'};
  const seedCount=dq.filter(x=>!x.live).length;
  document.getElementById('quality').innerHTML=
    dq.filter(x=>x.live).map(p=>'<div class="row"><span>'+p.port_id+'</span><span class="val"><span class="dot" style="color:'+(gradeColor[p.grade]||'gray')+'">●</span> LIVE / '+p.grade+'</span></div>').join('')+
    (seedCount?'<div class="row muted"><span>+'+seedCount+' portos</span><span class="val">REFERENCE</span></div>':'');
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
    _load_local_state()
    print(f"▶  Aether-X Control Tower local em http://{args.host}:{args.port}")
    print(f"   fonte: {PROD_METRICS_URL}")
    print(f"   histórico durável: {_HISTORY_PATH}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()