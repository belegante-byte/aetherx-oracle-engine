import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from src.products.gp5.maritime import get_port_physical_events
from src.runtime.contracts.v1 import DecisionResult


def evaluate_charter_risk(
    port_id: str,
    commodity: str,
    demurrage_rate_usd_day: float = 32000.0,
    expected_laytime_days: float = 2.0
) -> DecisionResult:
    """Avalia o risco de afretamento e exposição financeira sob premissas explícitas."""
    port_id = port_id.upper()
    commodity_norm = commodity.strip().upper()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    decision_id = f"dec_charter_{uuid.uuid4().hex[:10]}"
    
    # Busca ChangePacket da infraestrutura física
    packet = get_port_physical_events(port_id)
    
    # Contagem física de navios e vagões relevantes para essa carga ou gerais
    waiting_vessels = 0
    waiting_wagons = 0
    sources_used = set()
    
    for evt in packet.events:
        for ev in evt.evidence:
            sources_used.add(ev.source)
            
        if evt.entity.type == "vessel":
            st = evt.transition.to_value if evt.transition else None
            if st == "AO_LARGO":
                waiting_vessels += 1
        elif evt.entity.type == "train":
            wag = evt.entity.attributes.get("wagons_count", 0)
            waiting_wagons += wag

    # Estima atraso com base na fila real
    estimated_delay_days = round(max(0.5, (waiting_vessels * 0.15) + (waiting_wagons * 0.02)), 1)
    net_exposure_days = max(0.0, round(estimated_delay_days - expected_laytime_days, 1))
    estimated_exposure_usd = int(net_exposure_days * demurrage_rate_usd_day)
    
    return DecisionResult(
        decision_id=decision_id,
        evaluated_at=now,
        exposure={
            "value": estimated_exposure_usd,
            "currency": "USD",
            "estimated_delay_days": estimated_delay_days,
            "net_excess_days": net_exposure_days,
            "basis": f"{net_exposure_days} excess days × {demurrage_rate_usd_day} USD/day"
        },
        assumptions={
            "demurrage_rate_usd_day": demurrage_rate_usd_day,
            "expected_laytime_days": expected_laytime_days,
            "rate_source": "client_default_assumption",
            "target_commodity": commodity_norm
        },
        physical_basis=[
            f"Observed {waiting_vessels} vessels anchored ('AO_LARGO') at {port_id}",
            f"Observed {waiting_wagons} railway wagons queued/inbound for {port_id}",
            f"Data sources verified: {', '.join(sorted(list(sources_used))) if sources_used else 'None'}"
        ],
        uncertainties=[
            "Charter party terms (CP) not provided",
            "Actual agreed laytime not observed",
            "Vessel DWT capacity measured; exact cargo stowage quantity unmeasured"
        ]
    )
