import json
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

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


app = FastAPI(
    title="Aether-X Port Congestion Oracle",
    description="Algorithmic predictive port delay & congestion scores for global trade and quantitative funds.",
    version="0.2.0",
    servers=[
        {"url": PRODUCTION_URL, "description": "Production (Railway)"},
        {"url": "http://127.0.0.1:8000", "description": "Local development"}
    ],
    terms_of_service="https://aether-x-oracle-production.up.railway.app/terms",
    license_info={
        "name": "Machine-to-Machine Data Distribution (see /terms)",
        "url": "https://aether-x-oracle-production.up.railway.app/terms"
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/v1/port-risk", response_model=PortRiskResponse)
def get_port_risk(
    port_id: str = Query(..., description="UN/LOCODE do porto (ex: BRSSZ - Santos, CNSHA - Shanghai)")
):
    try:
        return calculate_port_risk(port_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))