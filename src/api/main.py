import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from src.api.mcp_app import build_http_app
from src.api.mcp_app import mcp as mcp_server
from src.engine.risk_model import calculate_port_risk

PRODUCTION_URL = os.getenv("PRODUCTION_URL", "https://aether-x-oracle-production.up.railway.app")
DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
TERMS_PATH = DOCS_DIR / "TERMS_OF_SERVICE.md"
RAPIDAPI_SPEC_PATH = DOCS_DIR / "openapi.rapidapi.min.json"
LLMS_TXT_PATH = DOCS_DIR / "llms.txt"
AI_PLUGIN_PATH = DOCS_DIR / "ai-plugin.json"


class PortRiskResponse(BaseModel):
    port_id: str
    port_name: str
    country: str
    congestion_score: float
    eta_delay_days: float
    waiting_vessels: int
    freight_volatility_index: float
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

**Free tier** — $0.00, no credit card required. Pay-as-you-go beyond the free tier at $0.02 per query.

**Other ways to consume it**
- Python SDK: `pip install aetherx-oracle`
- MCP server for AI agents: `uvx aetherx-mcp` (or the hosted `/mcp` endpoint)

**Coverage** — 15 ports: BRSSZ, BRRIO, CNSHA, CNNGB, SGSIN, NLRTM, USLAX, USNYC, DEHAM, MPTNG, AEDXB, KRPUS, GBLGP, ZACPT, MXZLO. Unknown ports return a global statistical estimate (`country="Global"`).

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
def health_check():
    return {
        "status": "online",
        "system": "Aether-X Oracle",
        "mode": "monorepo_local",
        "timestamp": int(time.time())
    }


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


app.mount("/", mcp_http_app)