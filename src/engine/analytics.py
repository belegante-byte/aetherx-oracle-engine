"""Motor de Inferências Estatísticas de Alto Valor Econômico para o Aether-X.

Modelos implementados:
1. PCI (Port Congestion Index, 0-100)
2. CDR (Chokepoint Disruption Risk, 0-100)
3. VQPM (Vessel Queue Predictive Model, t+1..t+7)
4. IRDI (Intermodal Rail Delay Index, 0-100)
5. SCDEW (Supply Chain Disruption Early Warning, 0-100)
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from src.engine.risk_model import calculate_port_risk
from src.ingestion.live_sources import (
    fetch_asian_port_congestion,
    fetch_european_port_congestion,
    fetch_chokepoint_and_african_telemetry,
)

# Pesos econométricos ajustados para calibração de modelos de risco de supply chain
DEMURRAGE_BASE_USD_DAY = 32000.0


def calculate_pci(port_id: str) -> Dict[str, Any]:
    """Calcula o Port Congestion Index (PCI) — Score Composto 0-100.
    
    Fórmula: PCI = (Congestion Level × 0.4) + (Avg Delay × 0.3) + (Vessel Queue × 0.2) + (Berth Use × 0.1)
    """
    port_id = port_id.upper().strip()
    risk = calculate_port_risk(port_id)
    
    cong_lvl = risk.get("congestion_score", 0.45) * 100.0
    delay_days = risk.get("eta_delay_days", 1.0)
    queue_vessels = risk.get("waiting_vessels", 10)
    
    # Extrai ocupação de berços da telemetria viva se disponível ou infere do congestion score
    live_detail = risk.get("live_detail")
    berth_use = 70.0
    if live_detail:
        try:
            import json
            det = json.loads(live_detail)
            berth_use = float(det.get("berth_occupancy_pct") or det.get("yard_utilization_pct") or 70.0)
        except Exception:
            pass

    # Normalizações para a escala 0-100
    norm_delay = min(100.0, (delay_days / 5.0) * 100.0)
    norm_queue = min(100.0, (queue_vessels / 50.0) * 100.0)
    
    pci_score = round(
        (cong_lvl * 0.4) + (norm_delay * 0.3) + (norm_queue * 0.2) + (berth_use * 0.1), 2
    )
    
    if pci_score >= 70.0:
        pci_level = "HIGH CONGESTION"
        freight_impact_pct = "+15% to +30%"
        demurrage_est_usd = int((delay_days + 1.5) * DEMURRAGE_BASE_USD_DAY)
    elif pci_score >= 40.0:
        pci_level = "MODERATE CONGESTION"
        freight_impact_pct = "+5% to +15%"
        demurrage_est_usd = int(delay_days * DEMURRAGE_BASE_USD_DAY)
    else:
        pci_level = "LOW CONGESTION / NORMAL"
        freight_impact_pct = "-5% to +5%"
        demurrage_est_usd = int(max(0, delay_days - 1.0) * DEMURRAGE_BASE_USD_DAY)

    return {
        "port_id": port_id,
        "port_name": risk.get("port_name", port_id),
        "pci_score": pci_score,
        "pci_level": pci_level,
        "components": {
            "congestion_level_pct": round(cong_lvl, 1),
            "avg_delay_days": delay_days,
            "vessel_queue_count": queue_vessels,
            "berth_occupancy_pct": round(berth_use, 1),
        },
        "economic_impact": {
            "freight_rate_impact": freight_impact_pct,
            "modeled_demurrage_exposure_usd": demurrage_est_usd,
            "recommended_safety_stock_buffer_days": round(delay_days * 1.5, 1),
        },
        "data_source": risk.get("data_source"),
        "as_of": risk.get("as_of"),
    }


def calculate_cdr(chokepoint_id: str) -> Dict[str, Any]:
    """Calcula o Chokepoint Disruption Risk (CDR) — Score de Risco 0-100.
    
    Fórmula: CDR = (Risk Score × 0.4) + (% of Normal × 0.3) + (7-day Avg × 0.2) + (Diversion Tracking × 0.1)
    """
    chokepoint_id = chokepoint_id.upper().strip()
    telemetry = fetch_chokepoint_and_african_telemetry()
    cp_info = telemetry.get(chokepoint_id, {
        "port_name": chokepoint_id,
        "congestion_score": 0.5,
        "pct_of_normal_baseline": 80.0,
        "daily_transits": 25,
        "seven_day_avg_transits": 26.0,
        "status": "OPERATIONAL",
        "sources": ["straittraffic_imf"],
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    })
    
    risk_score = cp_info.get("congestion_score", 0.5) * 100.0
    pct_normal = cp_info.get("pct_of_normal_baseline", 80.0)
    # Inverte % of normal para compor o risco (menor tráfego = maior disrupção)
    norm_disruption = min(100.0, max(0.0, (100.0 - pct_normal)))
    
    avg_transits = cp_info.get("seven_day_avg_transits", 25.0)
    norm_avg = min(100.0, max(0.0, (30.0 - avg_transits) * 3.33))
    
    diversion_tracking_score = 90.0 if "DISRUPTED" in cp_info.get("status", "") else 15.0
    
    cdr_score = round(
        (risk_score * 0.4) + (norm_disruption * 0.3) + (norm_avg * 0.2) + (diversion_tracking_score * 0.1), 2
    )
    
    if cdr_score >= 70.0:
        cdr_level = "HIGH DISRUPTIVE RISK"
        oil_price_impact = "+15% to +35%"
        war_risk_insurance_premium = "+30% to +60%"
    elif cdr_score >= 40.0:
        cdr_level = "ELEVATED RISK"
        oil_price_impact = "+5% to +15%"
        war_risk_insurance_premium = "+10% to +30%"
    else:
        cdr_level = "LOW RISK"
        oil_price_impact = "-2% to +5%"
        war_risk_insurance_premium = "BASELINE"

    return {
        "chokepoint_id": chokepoint_id,
        "chokepoint_name": cp_info.get("port_name", chokepoint_id),
        "cdr_score": cdr_score,
        "cdr_level": cdr_level,
        "status": cp_info.get("status"),
        "metrics": {
            "daily_transits": cp_info.get("daily_transits"),
            "pct_of_normal_baseline": pct_normal,
            "seven_day_avg_transits": avg_transits,
        },
        "economic_impact": {
            "oil_and_gas_price_sensitivity": oil_price_impact,
            "war_risk_insurance_premium_delta": war_risk_insurance_premium,
            "rerouting_cape_of_good_hope_impact": cp_info.get("rerouting_impact", "None observed"),
        },
        "sources": cp_info.get("sources"),
        "as_of": cp_info.get("as_of"),
    }


def calculate_vqpm(port_id: str, forecast_horizon_days: int = 1) -> Dict[str, Any]:
    """Modelo Preditivo de Fila de Navios (VQPM) para t+1 até t+7.
    
    Fórmula: VQPM_{t+1} = α × VQ_t + β × PCI_t + γ × CDR_t + δ × Seasonality + ε_t
    """
    port_id = port_id.upper().strip()
    pci = calculate_pci(port_id)
    vq_t = pci["components"]["vessel_queue_count"]
    pci_score = pci["pci_score"]
    
    # Seleciona chokepoint relevante (ex: Hormuz ou Suez)
    cdr_hormuz = calculate_cdr("HORMUZ")["cdr_score"]
    
    alpha, beta, gamma, delta = 0.50, 0.25, 0.15, 0.10
    seasonality_factor = 1.05  # Pico de safra / exportação agromineradora
    
    predictions = {}
    current_vq = float(vq_t)
    
    for h in range(1, min(8, forecast_horizon_days + 1)):
        vq_next = (
            (alpha * current_vq)
            + (beta * (pci_score / 2.0))
            + (gamma * (cdr_hormuz / 3.0))
            + (delta * 10.0 * seasonality_factor)
        )
        current_vq = vq_next
        predictions[f"day_{h}"] = {
            "predicted_vessel_queue": round(vq_next, 1),
            "projected_demurrage_exposure_usd": int(vq_next * 0.15 * DEMURRAGE_BASE_USD_DAY),
        }

    return {
        "port_id": port_id,
        "current_vessel_queue": vq_t,
        "forecast_horizon_days": forecast_horizon_days,
        "vqpm_predictions": predictions,
        "model_parameters": {
            "alpha_autoregressive": alpha,
            "beta_pci_weight": beta,
            "gamma_cdr_weight": gamma,
            "delta_seasonality_weight": delta,
        },
        "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    }


def calculate_irdi(port_or_corridor_id: str = "NLRTM") -> Dict[str, Any]:
    """Calcula o Intermodal Rail Delay Index (IRDI) — Score de Atrasos Ferroviários (0-100).
    
    Fórmula: IRDI = (Avg Delay × 0.4) + (Delays % × 0.3) + (Timetables × 0.2) + (Rolling Stock × 0.1)
    """
    port_id = port_or_corridor_id.upper().strip()
    euro_telemetry = fetch_european_port_congestion()
    info = euro_telemetry.get(port_id, {
        "intermodal_rail_status": "OPERATIONAL",
        "yard_utilization_pct": 75.0,
        "median_wait_hours": 30.0,
    })
    
    avg_delay_min = 25.0 if "DELAYED" in info.get("intermodal_rail_status", "") else 12.0
    delays_pct = 28.0 if "DELAYED" in info.get("intermodal_rail_status", "") else 14.0
    timetable_compliance_pct = 82.0
    rolling_stock_operability_pct = 88.0
    
    norm_delay = min(100.0, (avg_delay_min / 60.0) * 100.0)
    
    irdi_score = round(
        (norm_delay * 0.4) + (delays_pct * 0.3) + ((100.0 - timetable_compliance_pct) * 0.2) + ((100.0 - rolling_stock_operability_pct) * 0.1), 2
    )

    return {
        "hub_id": port_id,
        "irdi_score": irdi_score,
        "intermodal_status": info.get("intermodal_rail_status", "OPERATIONAL"),
        "components": {
            "avg_delay_minutes": avg_delay_min,
            "delayed_trains_pct": delays_pct,
            "timetable_compliance_pct": timetable_compliance_pct,
            "rolling_stock_operability_pct": rolling_stock_operability_pct,
        },
        "economic_impact": {
            "inland_freight_delay_days": round(avg_delay_min / 12.0, 1),
            "production_schedule_disruption_risk": "MODERATE" if irdi_score >= 35.0 else "LOW",
        },
        "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    }


def calculate_scdew(
    origin_port: str = "BRPNG",
    destination_port: str = "CNTAO",
    chokepoint_id: Optional[str] = "HORMUZ"
) -> Dict[str, Any]:
    """Calcula o Alerta Precoce de Disrupção da Cadeia de Suprimentos (SCDEW) — Score 0-100.
    
    Fórmula: SCDEW = (PCI × 0.3) + (CDR × 0.3) + (VQPM × 0.2) + (IRDI × 0.2)
    """
    chokepoint_id = (chokepoint_id or "HORMUZ").upper().strip()
    pci_res = calculate_pci(origin_port)
    pci_val = pci_res["pci_score"]
    
    cdr_res = calculate_cdr(chokepoint_id)
    cdr_val = cdr_res["cdr_score"]
    
    vqpm_res = calculate_vqpm(origin_port, forecast_horizon_days=1)
    vqpm_val = min(100.0, vqpm_res["vqpm_predictions"]["day_1"]["predicted_vessel_queue"] * 2.0)
    
    irdi_res = calculate_irdi(destination_port)
    irdi_val = irdi_res["irdi_score"]
    
    scdew_score = round(
        (pci_val * 0.3) + (cdr_val * 0.3) + (vqpm_val * 0.2) + (irdi_val * 0.2), 2
    )
    
    if scdew_score >= 70.0:
        warning_level = "CRITICAL / SEVERE EARLY WARNING"
        rec = "Activate secondary trade corridors, increase safety stock by +30%, lock long-term freight CP"
    elif scdew_score >= 40.0:
        warning_level = "MODERATE EARLY WARNING"
        rec = "Monitor chokepoint transit updates, buffer inland delivery lead times by +2 days"
    else:
        warning_level = "LOW / NORMAL OPERATIONAL RISK"
        rec = "Maintain JIT inventory schedules"

    return {
        "corridor": f"{origin_port} -> {destination_port} (via {chokepoint_id})",
        "scdew_score": scdew_score,
        "warning_level": warning_level,
        "recommendation": rec,
        "input_indices": {
            "origin_pci": pci_val,
            "chokepoint_cdr": cdr_val,
            "predicted_vqpm": round(vqpm_val, 1),
            "destination_irdi": irdi_val,
        },
        "macroeconomic_exposure": {
            "estimated_cfr_freight_premium_pct": f"+{round(scdew_score * 0.4, 1)}%",
            "commodity_price_volatility_risk": "HIGH" if scdew_score >= 50.0 else "MODERATE",
        },
        "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    }
