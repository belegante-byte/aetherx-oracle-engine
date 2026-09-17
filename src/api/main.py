import os
import time
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import PlainTextResponse
from typing import Optional
from src.engine.risk_model import calculate_port_risk

PRODUCTION_URL = os.getenv("PRODUCTION_URL", "https://aether-x-oracle-production.up.railway.app")
TERMS_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "TERMS_OF_SERVICE.md"


app = FastAPI(
    title="Aether-X Port Congestion Oracle",
    description="Algorithmic predictive port delay & congestion scores for global trade and quantitative funds.",
    version="0.1.0",
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


@app.get("/v1/port-risk")
def get_port_risk(
    port_id: str = Query(..., description="UN/LOCODE do porto (ex: BRSSZ - Santos)")
):
    try:
        data = calculate_port_risk(port_id)
        data["timestamp"] = int(time.time())
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))