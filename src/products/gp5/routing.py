import uuid
from datetime import datetime, timezone
from typing import Dict, Any
from src.products.gp5.charter_risk import evaluate_charter_risk
from src.runtime.contracts.v1 import DecisionResult

# Matriz de tempo estimado de viagem (dias de navegação) entre grandes corredores mundiais
CORRIDOR_TRANSIT_DAYS = {
    ("BRPNG", "CNTAO"): 32,  # Paranaguá -> Qingdao (Soja)
    ("BRPNG", "CNNGB"): 31,  # Paranaguá -> Ningbo
    ("BRPNG", "CNSHA"): 31,  # Paranaguá -> Shanghai
    ("BRPNG", "NLRTM"): 16,  # Paranaguá -> Rotterdam
    ("BRSSZ", "CNTAO"): 31,  # Santos -> Qingdao
    ("BRSSZ", "CNNGB"): 30,  # Santos -> Ningbo
    ("BRSSZ", "CNSHA"): 30,  # Santos -> Shanghai
    ("BRSSZ", "NLRTM"): 15,  # Santos -> Rotterdam
    ("USLAX", "CNSHA"): 14,  # Los Angeles -> Shanghai
    ("USLAX", "CNTAO"): 15,  # Los Angeles -> Qingdao
}

DEFAULT_DESTINATION_DELAY_DAYS = {
    "CNTAO": 3.5,  # Qingdao (Congestionamento médio descarga grãos)
    "CNNGB": 3.0,  # Ningbo
    "CNSHA": 4.0,  # Shanghai
    "NLRTM": 1.5,  # Rotterdam
    "DEHAM": 2.0,  # Hamburg
}


def evaluate_routing_alternatives(
    port_a: str,
    port_b: str,
    commodity: str
) -> DecisionResult:
    """Avaliação comparativa de condições operacionais entre dois portos de origem."""
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


def evaluate_corridor_risk(
    origin_port: str,
    destination_port: str,
    commodity: str = "SOJA",
    vessel_capacity_tons: float = 60000.0
) -> DecisionResult:
    """Avaliação de Risco do Corredor Global completo (Origem -> Navegação -> Destino).

    Exemplo: Chicago/Traders perguntam sobre o corredor Paranaguá (BRPNG) -> Qingdao (CNTAO) para Soja.
    Calcula: Fila na Origem + Dias de Trânsito + Fila no Destino = Ciclo Total e Custo CFR.
    """
    origin = origin_port.upper().strip()
    destination = destination_port.upper().strip()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    decision_id = f"dec_corridor_{uuid.uuid4().hex[:10]}"

    origin_risk = evaluate_charter_risk(origin, commodity)
    origin_delay = origin_risk.exposure.get("estimated_delay_days", 0.0)
    origin_demurrage_usd = origin_risk.exposure.get("value", 0.0)

    transit_days = CORRIDOR_TRANSIT_DAYS.get((origin, destination), 30)
    dest_delay = DEFAULT_DESTINATION_DELAY_DAYS.get(destination, 3.0)

    total_cycle_days = round(origin_delay + transit_days + dest_delay, 1)
    dest_demurrage_usd = round(dest_delay * 30000.0, 2)
    total_corridor_demurrage_usd = origin_demurrage_usd + dest_demurrage_usd
    cost_per_ton_usd = round(total_corridor_demurrage_usd / vessel_capacity_tons, 2)

    return DecisionResult(
        decision_id=decision_id,
        evaluated_at=now,
        exposure={
            "origin_port": origin,
            "destination_port": destination,
            "origin_wait_days": origin_delay,
            "sea_transit_days": transit_days,
            "destination_discharge_wait_days": dest_delay,
            "total_corridor_cycle_days": total_cycle_days,
            "total_demurrage_exposure_usd": total_corridor_demurrage_usd,
            "demurrage_cost_per_ton_usd": cost_per_ton_usd,
        },
        assumptions={
            "target_commodity": commodity.upper(),
            "vessel_capacity_tons": vessel_capacity_tons,
            "sea_route": f"{origin} -> {destination} via Cape/Malacca",
            "daily_demurrage_rate_usd": 32000.0,
        },
        physical_basis=[
            f"Origin ({origin}): " + "; ".join(origin_risk.physical_basis),
            f"Sea Voyage: Estimated {transit_days} days sailing for {origin} -> {destination}",
            f"Destination ({destination}): Reference discharge delay {dest_delay} days based on trade flow benchmarks",
        ],
        uncertainties=[
            "Sea weather / canal transit delays not dynamic",
            "Destination port discharge rate is benchmark reference",
            "CFR price impact is based on demurrage exposure addition only",
        ]
    )
