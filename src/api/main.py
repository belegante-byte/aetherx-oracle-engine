import time
from fastapi import FastAPI, Query, HTTPException
from typing import Optional
from src.engine.risk_model import calculate_port_risk


app = FastAPI(
    title="Aether-X Oracle API",
    description="Algorithmic Predictive Port Congestion Signal Engine",
    version="0.1.0"
)


@app.get("/")
def health_check():
    return {
        "status": "online",
        "system": "Aether-X Oracle",
        "mode": "monorepo_local",
        "timestamp": int(time.time())
    }


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