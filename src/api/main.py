import os
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from src.engine.risk_model import calculate_port_risk

PRODUCTION_URL = os.getenv("PRODUCTION_URL", "https://aether-x-oracle-production.up.railway.app")
TERMS_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "TERMS_OF_SERVICE.md"


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


@app.get("/v1/port-risk", response_model=PortRiskResponse)
def get_port_risk(
    port_id: str = Query(..., description="UN/LOCODE do porto (ex: BRSSZ - Santos, CNSHA - Shanghai)")
):
    try:
        return calculate_port_risk(port_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))