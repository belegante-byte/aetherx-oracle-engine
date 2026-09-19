import html
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict

from src.api.mcp_app import build_http_app
from src.api.mcp_app import mcp as mcp_server
from src.api import content_pages
from src.api.content_pages import PORT_METAS, _SLUG_MAP
from src.api.metrics import MetricsMiddleware, metrics_snapshot
from src.engine.risk_model import calculate_port_risk, calculate_port_trend

PRODUCTION_URL = os.getenv("PRODUCTION_URL", "https://aether-x-oracle-production.up.railway.app")
DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
TERMS_PATH = DOCS_DIR / "TERMS_OF_SERVICE.md"
RAPIDAPI_SPEC_PATH = Path(__file__).resolve().parent.parent.parent / "openapi.rapidapi.json"
LLMS_TXT_PATH = DOCS_DIR / "llms.txt"
AI_PLUGIN_PATH = DOCS_DIR / "ai-plugin.json"

EXAMPLE_RISK_RESPONSE = calculate_port_risk("BRSSZ")
EXAMPLE_TREND_RESPONSE = calculate_port_trend("BRSSZ")
EXAMPLE_BATCH_RESPONSE = {
    "results": [EXAMPLE_RISK_RESPONSE, calculate_port_risk("CNSHA")]
}
ERROR_401_EXAMPLE = {"detail": "Missing or invalid X-RapidAPI-Proxy-Secret header."}
ERROR_422_EXAMPLE = {
    "detail": [
        {
            "type": "missing",
            "loc": ["query", "port_id"],
            "msg": "Field required",
            "input": None,
        }
    ]
}
ERROR_400_EXAMPLE = {"detail": "port_ids accepts at most 20 ports per call."}


class RapidAPIGuard:
    """Exige o header `X-RapidAPI-Proxy-Secret` fora dos caminhos públicos.

    Ativo apenas quando `RAPIDAPI_PROXY_SECRET` está definido no ambiente.
    """

    def __init__(self, app):
        self.app = app
        self.secret = os.getenv("RAPIDAPI_PROXY_SECRET")

    @staticmethod
    def is_public_path(path: str) -> bool:
        return (
            path in {
                "/",
                "/health",
                "/health/",
                "/openapi.json",
                "/openapi.rapidapi.json",
                "/llms.txt",
                "/terms",
                "/sitemap.xml",
                "/robots.txt",
                "/santos-port-congestion-api",
            }
            or path.startswith("/port-congestion-")
            or path.startswith(("/docs", "/redoc", "/mcp", "/public/"))
            or path == "/.well-known/ai-plugin.json"
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if not self.secret or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return
        if self.is_public_path(scope.get("path", "/")):
            await self.app(scope, receive, send)
            return
        headers = dict(
            (k.decode("latin-1").lower(), v.decode("latin-1"))
            for k, v in scope.get("headers", [])
        )
        if headers.get("x-rapidapi-proxy-secret") == self.secret:
            await self.app(scope, receive, send)
            return
        payload = json.dumps(ERROR_401_EXAMPLE).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})


LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aether-X Port Congestion Oracle</title>
<meta name="description" content="Predictive port congestion signals for global trade and supply chain: congestion score, ETA delay, waiting vessels, freight volatility and daily demurrage for 16 global ports. REST API, Python SDK and MCP server.">
<meta property="og:title" content="Aether-X Port Congestion Oracle">
<meta property="og:description" content="Predictive congestion, ETA delay and freight volatility signals for 16 global ports. REST API, Python SDK and MCP server.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://aether-x-oracle-production.up.railway.app/">
<meta name="twitter:card" content="summary">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#0a0e14;color:#e6edf3;line-height:1.6;min-height:100vh}
a{color:#58a6ff;text-decoration:none}
a:hover{text-decoration:underline}
.container{max-width:720px;margin:0 auto;padding:3rem 1.5rem}
.badge-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:1.5rem}
.pill{font-size:0.75rem;padding:3px 12px;border-radius:20px;font-weight:600}
.pill-green{background:#00d9921a;color:#00d992;border:1px solid #00d99244}
.pill-blue{background:#58a6ff1a;color:#58a6ff;border:1px solid #58a6ff44}
h1{font-size:1.6rem;font-weight:700;margin-bottom:0.4rem}
.subtitle{color:#8b949e;font-size:0.95rem;margin-bottom:2.2rem}
.section-title{font-size:0.85rem;text-transform:uppercase;letter-spacing:0.08em;color:#8b949e;font-weight:600;margin-bottom:0.75rem}
.snippet-card{background:#161b22;border:1px solid #21262d;border-radius:8px;margin-bottom:1rem;overflow:hidden}
.card-header{display:flex;justify-content:space-between;align-items:center;gap:0.6rem;padding:0.5rem 0.9rem;border-bottom:1px solid #21262d;font-size:0.8rem;font-weight:600}
.card-header .hint{color:#8b949e;font-weight:400;margin-left:auto}
.copy-btn{background:none;border:1px solid #30363d;color:#8b949e;font-size:0.7rem;padding:2px 8px;border-radius:5px;cursor:pointer;font-family:inherit}
.copy-btn:hover{color:#e6edf3;border-color:#8b949e}
pre{margin:0;padding:0.9rem;font-size:0.82rem;line-height:1.55;overflow-x:auto;color:#e6edf3}
code{font-family:'SF Mono',SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace}
.links-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:0.6rem;margin-top:0.2rem}
.link-card{background:#161b22;border:1px solid #21262d;border-radius:6px;padding:0.55rem 0.8rem;font-size:0.82rem;color:#e6edf3;display:block}
.link-card:hover{border-color:#58a6ff55;text-decoration:none}
.snapshot-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:0.5rem}
@media(max-width:640px){.snapshot-grid{grid-template-columns:1fr}}
.sample-card{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:0.9rem;margin-bottom:1.4rem}
.sample-head{display:flex;align-items:center;gap:0.5rem;margin-bottom:0.7rem;flex-wrap:wrap}
.sample-code{color:#8b949e;font-family:'SF Mono',SFMono-Regular,Consolas,monospace;font-size:0.7rem;background:#0d1117;padding:0.15rem 0.4rem;border-radius:4px}
.sample-score{background:#1f6feb22;color:#58a6ff;font-family:'SF Mono',SFMono-Regular,Consolas,monospace;font-weight:700;font-size:0.75rem;padding:0.15rem 0.5rem;border-radius:999px}
.sample-trend{font-size:0.75rem;font-weight:600;margin-left:auto}
.trend-acc{color:#f85149}.trend-stable{color:#58a6ff}.trend-dec{color:#00d992}
.sample-metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:0.4rem;margin-bottom:0.7rem}
.metric span{display:block;font-size:0.62rem;color:#8b949e;text-transform:uppercase;letter-spacing:.05em}
.metric b{font-size:0.85rem;font-variant-numeric:tabular-nums}
.hint-inline{text-transform:none;letter-spacing:0;font-weight:400;font-size:0.72rem;color:#8b949e;margin-left:0.5rem}
details.raw summary{cursor:pointer;font-size:0.72rem;color:#8b949e;user-select:none}
details.raw summary:hover{color:#e6edf3}
details.raw pre{margin-top:0.5rem;max-height:18rem;overflow:auto}
.footer{margin-top:3rem;padding-top:1.5rem;border-top:1px solid #21262d;color:#8b949e;font-size:0.75rem}
</style>
</head>
<body>
<div class="container">

  <div class="badge-row">
    <span class="pill pill-blue">● Remote MCP Server Online</span>
    <span class="pill pill-blue">Glama Grade A</span>
  </div>

  <h1>Aether-X Port Congestion Oracle</h1>
  <p class="subtitle">MCP &amp; REST Engine &mdash; congestion signals for 17 global ports. <strong>BR ports feed live line-ups; others use a reference seed.</strong></p>

  <p class="section-title">Connect in 5 seconds</p>

  <div class="snippet-card">
    <div class="card-header"><span>Remote Streamable HTTP</span><span class="hint">no install</span><button class="copy-btn" onclick="copyText(this)">Copy</button></div>
    <pre><code>https://aether-x-oracle-production.up.railway.app/mcp</code></pre>
  </div>

  <div class="snippet-card">
    <div class="card-header"><span>Claude Desktop / Cursor / any stdio client</span><span class="hint">uvx aetherx-mcp</span><button class="copy-btn" onclick="copyText(this)">Copy</button></div>
    <pre><code>{
  "mcpServers": {
    "aetherx-oracle": {
      "command": "uvx",
      "args": ["aetherx-mcp"]
    }
  }
}</code></pre>
  </div>

  <div class="snippet-card">
    <div class="card-header"><span>VS Code Cline</span><span class="hint">remote http</span><button class="copy-btn" onclick="copyText(this)">Copy</button></div>
    <pre><code>{
  "mcpServers": {
    "aetherx-oracle": {
      "type": "url",
      "url": "https://aether-x-oracle-production.up.railway.app/mcp"
    }
  }
}</code></pre>
  </div>

  <p class="section-title" style="margin-top:2rem">Live Snapshot <span class="hint-inline">BR ports live; see data_source in each payload</span></p>
  __LIVE_SNAPSHOT__

  <p class="section-title" style="margin-top:2rem">Protocol &amp; Docs</p>
  <div class="links-grid">
    <a class="link-card" href="/mcp-page">Aether-X MCP (demo page)</a>
    <a class="link-card" href="/port-congestion-api">Port Congestion API</a>
    <a class="link-card" href="/santos-port-congestion-api">Santos Port Congestion API</a>
    <a class="link-card" href="/port-congestion-python">Port Congestion with Python</a>
    <a class="link-card" href="/docs">Swagger UI</a>
    <a class="link-card" href="/openapi.json">OpenAPI 3.1</a>
    <a class="link-card" href="/openapi.rapidapi.json">OpenAPI (RapidAPI)</a>
    <a class="link-card" href="/llms.txt">llms.txt</a>
    <a class="link-card" href="/.well-known/ai-plugin.json">ai-plugin.json</a>
    <a class="link-card" href="/terms">Terms of Service</a>
    <a class="link-card" href="https://glama.ai/mcp/connectors/io.github.belegante-byte/aetherx-mcp">Glama Connector (Grade A)</a>
    <a class="link-card" href="https://smithery.ai/servers/belegante/aetherx-mcp">Smithery Gateway</a>
    <a class="link-card" href="https://pypi.org/project/aetherx-mcp/">PyPI &mdash; aetherx-mcp</a>
    <a class="link-card" href="https://pypi.org/project/aetherx-oracle/">PyPI &mdash; aetherx-oracle (SDK)</a>
    <a class="link-card" href="https://github.com/belegante-byte/aetherx-mcp">GitHub &mdash; MCP server</a>
    <a class="link-card" href="https://registry.modelcontextprotocol.io">Official MCP Registry</a>
  </div>

  <p class="section-title" style="margin-top:2rem">Per-port reference pages <span class="hint-inline">one page, one port, static reference data</span></p>
  <div class="links-grid">
    <a class="link-card" href="/port-congestion-santos">Santos (BRSSZ)</a>
    <a class="link-card" href="/port-congestion-shanghai">Shanghai (CNSHA)</a>
    <a class="link-card" href="/port-congestion-rotterdam">Rotterdam (NLRTM)</a>
    <a class="link-card" href="/port-congestion-singapore">Singapore (SGSIN)</a>
    <a class="link-card" href="/port-congestion-qingdao">Qingdao (CNTAO)</a>
    <a class="link-card" href="/port-congestion-los-angeles">Los Angeles (USLAX)</a>
    <a class="link-card" href="/port-congestion-ningbo-zhoushan">Ningbo-Zhoushan (CNNGB)</a>
    <a class="link-card" href="/port-congestion-dubai-jebel-ali">Dubai / Jebel Ali (AEDXB)</a>
    <a class="link-card" href="/port-congestion-new-york">New York (USNYC)</a>
    <a class="link-card" href="/port-congestion-hamburg">Hamburg (DEHAM)</a>
    <a class="link-card" href="/port-congestion-busan">Busan (KRPUS)</a>
    <a class="link-card" href="/port-congestion-cape-town">Cape Town (ZACPT)</a>
    <a class="link-card" href="/port-congestion-rio-de-janeiro">Rio de Janeiro (BRRIO)</a>
    <a class="link-card" href="/port-congestion-tanger-med">Tanger Med (MPTNG)</a>
    <a class="link-card" href="/port-congestion-london-gateway">London Gateway (GBLGP)</a>
    <a class="link-card" href="/port-congestion-manzanillo">Manzanillo (MXZLO)</a>
  </div>

  <div class="footer">
    Aether-X Port Congestion Oracle v0.2.1 &middot; MIT &middot; Free tier $0.00
    &middot; <a href="mailto:contato@aether-grid.io">contato@aether-grid.io</a>
  </div>
</div>
<script>
function copyText(btn){
  var code = btn.closest('.snippet-card').querySelector('code');
  if (!code) return;
  (navigator.clipboard ? navigator.clipboard.writeText(code.textContent) : Promise.reject())
    .then(function(){
      var t = btn.textContent;
      btn.textContent = 'Copied!';
      btn.style.color = '#00d992';
      setTimeout(function(){ btn.textContent = t; btn.style.color = ''; }, 1200);
    });
}
</script>
</body>
</html>"""


class PortRiskResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [EXAMPLE_RISK_RESPONSE]})

    port_id: str
    port_name: str
    country: str
    congestion_score: float
    eta_delay_days: float
    waiting_vessels: int
    freight_volatility_index: float
    estimated_daily_demurrage_usd: int
    updated_at: str
    as_of: str
    data_source: str
    data_source_label: str
    live_detail: str | None = None
    live: dict | None = None


class TrendPoint(BaseModel):
    congestion_score: float
    eta_delay_days: float
    estimated_daily_demurrage_usd: int


class PortTrendResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [EXAMPLE_TREND_RESPONSE]})

    port_id: str
    port_name: str
    country: str
    trend: str
    congestion_score: float
    projection: dict[str, TrendPoint]
    updated_at: str
    as_of: str
    data_source: str
    data_source_label: str


class PortsRiskResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [EXAMPLE_BATCH_RESPONSE]})

    results: list[PortRiskResponse]


API_DESCRIPTION = """Port congestion reference signals for global trade, supply chain and quantitative finance.

**IMPORTANT · Data integrity notice**: every response includes `data_source`, `data_source_label` and `as_of`.
Brazilian ports (BRSSZ, BRPNG) serve live line-ups: `data_source="live:appa+santos+lachmann"`. The remaining ports
serve a **static reference seed**: `data_source="static_reference_seed"` means the value is a seeded baseline, not a
live measurement. The 24/48/72h trend is a `synthetic_projection`, not a live forecast. Do not treat seed numbers as
real-time field data.

**The signal** — `GET /v1/port-risk?port_id=BRSSZ` returns:

| Field | Meaning |
|-------|---------|
| `congestion_score` | Normalized 0.0–1.0 reference congestion level (seeded) |
| `eta_delay_days` | Reference delay applied to incoming vessels |
| `waiting_vessels` | Reference ships anchored or queued |
| `freight_volatility_index` | Pressure indicator for freight pricing |
| `estimated_daily_demurrage_usd` | Estimated daily demurrage (USD) for a vessel queued at the port |
| `data_source` | Always `static_reference_seed` until live telemetry is connected |
| `as_of` | Timestamp of the seed (not a live refresh) |

**Trend (24h/48h/72h)** — `GET /v1/port-trend?port_id=BRSSZ` returns a **synthetic** projection with a `trend` label: `acelerando`, `estável` or `descongestionando`.

**Free tier** — $0.00, no credit card required. Pay-as-you-go beyond the free tier at $0.02 per query.

**Other ways to consume it**
- Python SDK: `pip install aetherx-oracle`
- MCP server for AI agents: `uvx aetherx-mcp` (or the hosted `/mcp` endpoint) — tools: `get_port_risk`, `get_ports_risk`, `get_port_trend`

**Coverage** — 16 ports: BRSSZ, BRRIO, CNSHA, CNNGB, CNTAO, SGSIN, NLRTM, USLAX, USNYC, DEHAM, MPTNG, AEDXB, KRPUS, GBLGP, ZACPT, MXZLO. Unknown ports return a global statistical estimate (`country="Global"`).

Signals are provided "AS IS" and do not constitute investment advice.
"""

mcp_http_app = build_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("ENABLE_LIVE_INGESTION", "0") == "1":
        import asyncio
        from src.ingestion.live_sources import coletar_tudo
        from scripts.run_ingestion_live import gravar_raw, aplicar_no_oracle, resumo_por_porto, _score_from_status, GRID
        from src.engine.risk_model import invalidate_cache

        async def ciclo_ingestao():
            intervalo = int(os.getenv("LIVE_INGESTION_INTERVAL_S", "21600"))  # 6h padrão
            while True:
                try:
                    res = coletar_tudo()
                    resumos = resumo_por_porto(res.get("linhas", []))
                    por_porto = {}
                    for pid in GRID:
                        r = resumos.get(pid)
                        if r and r.get("total", 0) > 0:
                            por_porto[pid] = _score_from_status(pid, r, res.get("fontes", {}))
                    if por_porto:
                        gravar_raw(res.get("linhas", []))
                        aplicar_no_oracle(por_porto, resumos)
                        invalidate_cache()
                        print(f"[AETHER-X INGESTION] ciclo ok: {len(res.get('linhas', []))} linhas")
                except Exception as e:
                    print(f"[AETHER-X INGESTION] erro no ciclo: {type(e).__name__}: {e}")
                finally:
                    await asyncio.sleep(intervalo)

        asyncio.create_task(ciclo_ingestao())
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(
    lifespan=lifespan,
    title="Aether-X Port Congestion Oracle",
    description=API_DESCRIPTION,
    version="0.2.1",
    servers=[
        {"url": PRODUCTION_URL, "description": "Production (Railway)"},
        {"url": "http://127.0.0.1:8000", "description": "Local development"}
    ],
    terms_of_service="https://aether-x-oracle-production.up.railway.app/terms",
    contact={
        "name": "Aether-X",
        "url": "https://aether-x-oracle-production.up.railway.app",
        "email": "contato@aether-grid.io",
    },
    license_info={
        "name": "Machine-to-Machine Data Distribution (see /terms)",
        "url": "https://aether-x-oracle-production.up.railway.app/terms"
    },
    openapi_tags=[
        {
            "name": "Port Risk",
            "description": "Predictive congestion, ETA delay and freight volatility signals per port.",
        }
    ],
)

app.add_middleware(MetricsMiddleware)

app.add_middleware(RapidAPIGuard)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["mcp-session-id"],
    allow_credentials=False,
)


def _fmt_usd(value: int) -> str:
    return f"${value:,}/day"


def _render_live_snapshot() -> str:
    """Renderiza 'Reference Snapshot' com risco e tendência do seed (com provenance)."""
    cards = []
    trend_styles = {
        "acelerando": "trend-acc",
        "estável": "trend-stable",
        "descongestionando": "trend-dec",
    }
    for port_id in ("BRSSZ", "NLRTM"):
        risk = calculate_port_risk(port_id)
        trend = calculate_port_trend(port_id)
        proj = trend["projection"]
        tclass = trend_styles.get(trend["trend"], "trend-stable")
        code = html.escape(
            json.dumps({"risk": risk, "trend": trend}, ensure_ascii=False, indent=2)
        )
        cards.append(
            '<div class="sample-card">'
            '<div class="sample-head">'
            f'<strong>{html.escape(risk["port_name"])}</strong>'
            f'<span class="sample-code">{port_id}</span>'
            f'<span class="sample-score">{risk["congestion_score"]:.2f}</span>'
            f'<span class="sample-trend {tclass}">{trend["trend"]}</span>'
            "</div>"
            '<div class="sample-metrics">'
            f'<div class="metric"><span>24h</span><b>{proj["h24"]["congestion_score"]:.2f}</b></div>'
            f'<div class="metric"><span>48h</span><b>{proj["h48"]["congestion_score"]:.2f}</b></div>'
            f'<div class="metric"><span>72h</span><b>{proj["h72"]["congestion_score"]:.2f}</b></div>'
            f'<div class="metric"><span>Demurrage</span><b>{_fmt_usd(risk["estimated_daily_demurrage_usd"])}</b></div>'
            f'<div class="metric"><span>Waiting</span><b>{risk["waiting_vessels"]}</b></div>'
            "</div>"
            '<details class="raw"><summary>Raw JSON</summary>'
            f"<pre><code>{code}</code></pre></details>"
            "</div>"
        )
    return '<div class="snapshot-grid">' + "".join(cards) + "</div>"


@app.get("/", include_in_schema=False)
def landing_page():
    return HTMLResponse(
        LANDING_HTML.replace("__LIVE_SNAPSHOT__", _render_live_snapshot())
    )


@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok", "service": "aether-x-oracle", "version": "0.2.1"}


@app.get("/health/", include_in_schema=False)
def health_check_trailing_slash():
    return health_check()


@app.get("/terms", include_in_schema=False)
def terms_of_service():
    return PlainTextResponse(TERMS_PATH.read_text(encoding="utf-8"))


@app.get("/openapi.rapidapi.json", include_in_schema=False)
def rapidapi_spec():
    return JSONResponse(json.loads(RAPIDAPI_SPEC_PATH.read_text(encoding="utf-8")))


@app.get("/llms.txt", include_in_schema=False)
def llms_txt():
    return PlainTextResponse(
        LLMS_TXT_PATH.read_text(encoding="utf-8"), media_type="text/plain"
    )


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    return PlainTextResponse(content_pages.sitemap_xml(), media_type="application/xml")


@app.get("/robots.txt", include_in_schema=False)
def robots_txt():
    return PlainTextResponse(content_pages.robots_txt_content(), media_type="text/plain")


@app.get("/mcp-page", include_in_schema=False)
def mcp_page():
    return HTMLResponse(content_pages.mcp_page_html())


@app.get("/port-congestion-api", include_in_schema=False)
def port_congestion_api_page():
    return HTMLResponse(content_pages.port_congestion_api_page())


@app.get("/santos-port-congestion-api", include_in_schema=False)
def santos_port_congestion_api_page():
    return HTMLResponse(content_pages.santos_port_congestion_api_page())


@app.get("/port-congestion-python", include_in_schema=False)
def port_congestion_python_page():
    return HTMLResponse(content_pages.port_congestion_python_page())


@app.get("/port-congestion-{slug}", include_in_schema=False)
def port_congestion_detail(slug: str):
    meta = _SLUG_MAP.get(slug)
    if not meta:
        raise HTTPException(status_code=404, detail="Port page not found")
    return HTMLResponse(content_pages.port_detail_page(meta["port_id"], slug))


@app.get("/public/ports", include_in_schema=False)
def public_ports_all():
    """Feed público read-only: sinal dos 17 portos (BR vivos + seed de referência) para widget/embed, sem key."""
    rows = [calculate_port_risk(m["port_id"]) for m in PORT_METAS]
    return {
        "as_of": rows[0]["as_of"],
        "data_source": "mixed",
        "data_source_label": "Live line-ups for BR ports (BRSSZ/BRPNG); static reference seed elsewhere.",
        "count": len(rows),
        "results": rows,
    }


@app.get("/internal/metrics", include_in_schema=False)
def internal_metrics():
    return JSONResponse(metrics_snapshot())


@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def ai_plugin_manifest():
    return JSONResponse(json.loads(AI_PLUGIN_PATH.read_text(encoding="utf-8")))


@app.get(
    "/v1/port-risk",
    response_model=PortRiskResponse,
    tags=["Port Risk"],
    summary="Get port congestion risk for a single port",
    description=(
        "Returns the reference congestion signal for a single global port: "
        "`congestion_score` (0.0-1.0), `eta_delay_days`, `waiting_vessels`, "
        "`freight_volatility_index` and the estimated `estimated_daily_demurrage_usd`. "
        "Every response includes `data_source` (`static_reference_seed` until live "
        "telemetry is connected) and `as_of` (seed timestamp, not a live refresh). "
        "Coverage: 16 ports (BRSSZ, CNSHA, CNTAO, NLRTM, ...). Unknown ports fall back "
        'to a global statistical estimate with `country="Global"`. Requests are protected '
        "by the RapidAPI proxy secret and must send the `X-RapidAPI-Proxy-Secret` header."
    ),
    response_description="The current reference signal for the requested port.",
    responses={
        200: {
            "model": PortRiskResponse,
            "description": "The current reference signal for the requested port.",
            "content": {"application/json": {"example": EXAMPLE_RISK_RESPONSE}},
        },
        401: {
            "description": "Missing or invalid X-RapidAPI-Proxy-Secret header.",
            "content": {"application/json": {"example": ERROR_401_EXAMPLE}},
        },
        422: {
            "description": "Validation error: the port_id query parameter is required.",
            "content": {"application/json": {"example": ERROR_422_EXAMPLE}},
        },
    },
)
def get_port_risk(
    port_id: str = Query(
        ...,
        description="UN/LOCODE of the port, e.g. BRSSZ (Santos), CNSHA (Shanghai), NLRTM (Rotterdam).",
        examples=["BRSSZ"],
    )
):
    try:
        return calculate_port_risk(port_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/v1/port-trend",
    response_model=PortTrendResponse,
    tags=["Port Risk"],
    summary="Get port risk trend",
    description=(
        "Returns the 24h, 48h and 72h congestion projections for a single global port, "
        "with a `trend` label (`acelerando`, `estável` or `descongestionando`). Each "
        "projection point includes `congestion_score`, `eta_delay_days` and the estimated "
        "`estimated_daily_demurrage_usd`. NOTE: the projection is `synthetic_projection` "
        "(derived from the static reference seed), not a live forecast. Requests are "
        "protected by the RapidAPI proxy secret and must send the `X-RapidAPI-Proxy-Secret` header."
    ),
    response_description="The 24h, 48h and 72h congestion projections for the requested port.",
    responses={
        200: {
            "model": PortTrendResponse,
            "description": "The 24h, 48h and 72h congestion projections for the requested port.",
            "content": {"application/json": {"example": EXAMPLE_TREND_RESPONSE}},
        },
        401: {
            "description": "Missing or invalid X-RapidAPI-Proxy-Secret header.",
            "content": {"application/json": {"example": ERROR_401_EXAMPLE}},
        },
        422: {
            "description": "Validation error: the port_id query parameter is required.",
            "content": {"application/json": {"example": ERROR_422_EXAMPLE}},
        },
    },
)
def get_port_trend(
    port_id: str = Query(
        ...,
        description="UN/LOCODE of the port, e.g. BRSSZ (Santos), CNSHA (Shanghai), NLRTM (Rotterdam).",
        examples=["BRSSZ"],
    )
):
    try:
        return calculate_port_trend(port_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/v1/ports-risk",
    response_model=PortsRiskResponse,
    tags=["Port Risk"],
    summary="Get congestion risk for multiple ports in one call",
    description=(
        "Returns the congestion signals for up to 20 ports in a single request, preserving "
        "the order of the `port_ids` (comma-separated UN/LOCODEs). Unknown ports fall back "
        "to the global statistical estimate. Requests are protected by the RapidAPI proxy "
        "secret and must send the `X-RapidAPI-Proxy-Secret` header."
    ),
    response_description="A list of congestion signals, one per requested port, in the same order.",
    responses={
        200: {
            "model": PortsRiskResponse,
            "description": "The congestion signals, one per requested port.",
            "content": {"application/json": {"example": EXAMPLE_BATCH_RESPONSE}},
        },
        400: {
            "description": "More than 20 ports requested in port_ids.",
            "content": {"application/json": {"example": ERROR_400_EXAMPLE}},
        },
        401: {
            "description": "Missing or invalid X-RapidAPI-Proxy-Secret header.",
            "content": {"application/json": {"example": ERROR_401_EXAMPLE}},
        },
        422: {
            "description": "Validation error: the port_ids query parameter is required.",
            "content": {"application/json": {"example": ERROR_422_EXAMPLE}},
        },
    },
)
def get_ports_risk(
    port_ids: str = Query(
        ...,
        description="Comma-separated UN/LOCODEs, e.g. BRSSZ,CNSHA,NLRTM (max 20).",
        examples=["BRSSZ,CNSHA,NLRTM"],
    )
):
    ids = [pid.strip().upper() for pid in port_ids.split(",") if pid.strip()]
    if len(ids) > 20:
        raise HTTPException(
            status_code=400, detail=ERROR_400_EXAMPLE["detail"]
        )
    try:
        return {"results": [calculate_port_risk(pid) for pid in ids]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


app.mount("/", mcp_http_app)