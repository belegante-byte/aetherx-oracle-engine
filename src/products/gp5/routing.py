import uuid
from datetime import datetime, timezone
from typing import Dict, Any
from src.products.gp5.charter_risk import evaluate_charter_risk
from src.runtime.contracts.v1 import DecisionResult


def evaluate_routing_alternatives(
    port_a: str,
    port_b: str,
    commodity: str
) -> DecisionResult:
    """Avaliação comparativa de condições operacionais entre dois portos (Evaluation mode)."""
    port_a = port_a.upper()
    port_b = port_b.upper()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    decision_id = f"dec_route_{uuid.uuid4().hex[:10]}"
    
    risk_a = evaluate_charter_risk(port_a, commodity)
    risk_b = evaluate_charter_risk(port_b, commodity)
    
    exp_a = risk_a.exposure.get("value", 0)
    exp_b = risk_b.exposure.get("value", 0)
    delay_a = risk_a.exposure.get("estimated_delay_days", 0)
    delay_b = risk_b.exposure.get("estimated_delay_days", 0)
    
    return DecisionResult(
        decision_id=decision_id,
        evaluated_at=now,
        exposure={
            "port_a": {"port_id": port_a, "estimated_delay_days": delay_a, "exposure_usd": exp_a},
            "port_b": {"port_id": port_b, "estimated_delay_days": delay_b, "exposure_usd": exp_b},
            "exposure_delta_usd": exp_a - exp_b
        },
        assumptions={
            "target_commodity": commodity.strip().upper(),
            "evaluation_mode": "comparative_conditions_only"
        },
        physical_basis=[
            f"{port_a}: " + "; ".join(risk_a.physical_basis),
            f"{port_b}: " + "; ".join(risk_b.physical_basis)
        ],
        uncertainties=[
            "Comparative evaluation of observed physical states only; no prescriptive routing mandate implied",
            "Inland freight cost differentials not included in comparison"
        ],
        comparison={
            "delta_delay_days": round(delay_a - delay_b, 1),
            "lower_delay_port": port_a if delay_a < delay_b else (port_b if delay_b < delay_a else "EQUAL"),
            "lower_financial_exposure_port": port_a if exp_a < exp_b else (port_b if exp_b < exp_a else "EQUAL")
        }
    )
