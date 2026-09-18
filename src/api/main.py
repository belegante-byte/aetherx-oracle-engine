import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from src.api.mcp_app import build_http_app
from src.api.mcp_app import mcp as mcp_server
from src.engine.risk_model import calculate_port_risk, calculate_port_trend

PRODUCTION_URL = os.getenv("PRODUCTION_URL", "https://aether-x-oracle-production.up.railway.app")
DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
TERMS_PATH = DOCS_DIR / "TERMS_OF_SERVICE.md"
RAPIDAPI_SPEC_PATH = DOCS_DIR / "openapi.rapidapi.min.json"
LLMS_TXT_PATH = DOCS_DIR / "llms.txt"
AI_PLUGIN_PATH = DOCS_DIR / "ai-plugin.json"


LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aether-X Port Congestion Oracle</title>
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
.footer{margin-top:3rem;padding-top:1.5rem;border-top:1px solid #21262d;color:#8b949e;font-size:0.75rem}
</style>
</head>
<body>
<div class="container">

  <div class="badge-row">
    <span class="pill pill-green">● Remote MCP Server Live</span>
    <span class="pill pill-blue">Glama Grade A</span>
  </div>

  <h1>Aether-X Port Congestion Oracle</h1>
  <p class="subtitle">MCP &amp; REST Engine &mdash; predictive congestion, ETA delay and freight volatility for 15 global ports.</p>

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

  <p class="section-title" style="margin-top:2rem">Protocol &amp; Docs</p>
  <div class="links-grid">
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

  <div class="footer">
    Aether-X Port Congestion Oracle v0.2.0 &middot; MIT &middot; Free tier $0.00
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
    port_id: str
    port_name: str
    country: str
    congestion_score: float
    eta_delay_days: float
    waiting_vessels: int
    freight_volatility_index: float
    estimated_daily_demurrage_usd: int
    updated_at: str


class TrendPoint(BaseModel):
    congestion_score: float
    eta_delay_days: float
    estimated_daily_demurrage_usd: int


class PortTrendResponse(BaseModel):
    port_id: str
    port_name: str
    country: str
    trend: str
    congestion_score: float
    projection: dict[str, TrendPoint]
    updated_at: str


API_DESCRIPTION = """Predictive port congestion signals for global trade, supply chain and quantitative finance.

Aether-X turns public port telemetry into machine-readable congestion scores, ETA delay estimates and freight volatility indices for the world's largest ports — so trading desks, logistics teams and autonomous agents can react before the market prices the delay in.

**The signal** — `GET /v1/port-risk?port_id=BRSSZ` returns:

| Field | Meaning |
|-------|---------|
| `congestion_score` | Normalized 0.0–1.0 risk of operational congestion |
| `eta_delay_days` | Expected delay applied to incoming vessels |
| `waiting_vessels` | Ships anchored or queued |
| `freight_volatility_index` | Pressure indicator for freight pricing |
| `estimated_daily_demurrage_usd` | Estimated daily demurrage (USD) for a vessel queued at the port |

**Trend (24h/48h/72h)** — `GET /v1/port-trend?port_id=BRSSZ` returns the congestion projection with a `trend` label: `acelerando`, `estável` or `descongestionando`.

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
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(
    lifespan=lifespan,
    title="Aether-X Port Congestion Oracle",
    description=API_DESCRIPTION,
    version="0.2.0",
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["mcp-session-id"],
    allow_credentials=False,
)


@app.get("/", include_in_schema=False)
def landing_page():
    return HTMLResponse(LANDING_HTML)


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


@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def ai_plugin_manifest():
    return JSONResponse(json.loads(AI_PLUGIN_PATH.read_text(encoding="utf-8")))


@app.get(
    "/v1/port-risk",
    response_model=PortRiskResponse,
    tags=["Port Risk"],
    summary="Get port risk",
    response_description="The current congestion signal for the requested port.",
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
    response_description="The 24h, 48h and 72h congestion projections for the requested port.",
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


app.mount("/", mcp_http_app)