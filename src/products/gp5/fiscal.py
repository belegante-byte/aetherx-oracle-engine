import os
import duckdb
from pydantic import BaseModel, Field
from typing import List, Optional
from src.engine.risk_model import calculate_port_risk

DB_PATH = os.getenv("DATABASE_PATH", "data/oracle.duckdb")

class PortRouteOption(BaseModel):
    port_id: str
    port_name: str
    state_code: str
    congestion_score: float
    delay_days: float
    demurrage_cost_usd: float
    icms_rate_pct: float
    icms_cost_usd: float
    inland_freight_cost_usd: float
    exemption_note: Optional[str]
    total_cost_usd: float
    is_recommended: bool
    data_source: str
    as_of: str
    decision_grade: str

class FiscalRoutingResponse(BaseModel):
    schema_version: str = "fiscal-routing.v1"
    intended_port_id: str
    commodity: str
    cargo_value_usd: float
    inland_uf: str
    cargo_tons: float
    options: List[PortRouteOption]
    recommendation_summary: str

def get_state_from_port(port_id: str) -> str:
    # Mapeamento simplificado para portos BR suportados no MVP
    mapping = {
        "BRSSZ": "SP",
        "BRPNG": "PR",
        "BRMAO": "MA",
        "BRRIO": "RJ",
        "BRNIT": "RJ",
        "BRITG": "RJ",
        "BRRGD": "RS",
        "BRVDC": "PA",
    }
    return mapping.get(port_id.upper(), "UNKNOWN")


def estimate_inland_freight_usd(port_id: str, inland_uf: str, cargo_tons: float) -> float:
    # MVP: Mock de frete terrestre (US$ por tonelada) do porto até o estado de destino/origem
    matrix = {
        "MT": {"BRSSZ": 45.0, "BRPNG": 50.0, "BRMAO": 35.0, "BRRIO": 55.0, "BRRGD": 65.0},
        "GO": {"BRSSZ": 40.0, "BRPNG": 45.0, "BRMAO": 50.0, "BRRIO": 50.0, "BRRGD": 60.0},
        "PR": {"BRSSZ": 25.0, "BRPNG": 10.0, "BRMAO": 70.0, "BRRIO": 35.0, "BRRGD": 30.0},
        "SP": {"BRSSZ": 10.0, "BRPNG": 25.0, "BRMAO": 80.0, "BRRIO": 20.0, "BRRGD": 45.0},
    }
    rate_per_ton = matrix.get(inland_uf.upper(), {}).get(port_id.upper(), 60.0)
    return cargo_tons * rate_per_ton

def evaluate_fiscal_routing(intended_port_id: str, commodity: str, cargo_value_usd: float = 10000000.0, inland_uf: str = 'MT', cargo_tons: float = 60000.0) -> FiscalRoutingResponse:

    if cargo_value_usd <= 0 or cargo_tons <= 0:
        raise ValueError("Cargo value and tons must be greater than 0.")
    if inland_uf.upper() not in ["MT", "GO", "PR", "SP", "MS", "MG"]:
        pass # We allow fallback, but we should probably warn.

    commodity = commodity.upper()
    intended_port_id = intended_port_id.upper()
    
    # Busca os portos do Brasil que podemos usar como alternativas (apenas BR no MVP para ICMS)
    br_ports = ["BRSSZ", "BRPNG", "BRMAO", "BRRIO", "BRRGD"]
    if intended_port_id not in br_ports and intended_port_id.startswith("BR"):
        br_ports.append(intended_port_id)
        
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
    except duckdb.Error:
        conn = None

    options = []
    
    for pid in br_ports:
        state_code = get_state_from_port(pid)
        if state_code == "UNKNOWN":
            continue
            
        # Puxa o risco (demurrage logístico)
        risk = calculate_port_risk(pid)
        delay_days = risk.get("eta_delay_days", 0)
        daily_demurrage = risk.get("estimated_daily_demurrage_usd", 0)
        demurrage = daily_demurrage * delay_days
        
        # Puxa a alíquota fiscal (DuckDB)
        icms_pct = 18.0 # fallback
        exemption = None
        if conn:
            row = conn.execute(
                "SELECT icms_rate_pct, exemption_note FROM tax_rules WHERE state_code = ? AND commodity = ?",
                [state_code, commodity]
            ).fetchone()
            if row:
                icms_pct = row[0]
                exemption = row[1]
                
        icms_cost = cargo_value_usd * (icms_pct / 100.0)
        freight_cost = estimate_inland_freight_usd(pid, inland_uf, cargo_tons)
        total_cost = demurrage + icms_cost + freight_cost
        
        options.append(PortRouteOption(
            port_id=pid,
            port_name=risk.get("port_name", pid),
            state_code=state_code,
            congestion_score=risk.get("congestion_score", 0),
            delay_days=delay_days,
            demurrage_cost_usd=demurrage,
            icms_rate_pct=icms_pct,
            icms_cost_usd=round(icms_cost, 2),
            inland_freight_cost_usd=freight_cost,
            exemption_note=exemption,
            total_cost_usd=round(total_cost, 2),
            is_recommended=False,
            data_source=risk.get("data_source", "unknown"),
            as_of=risk.get("as_of", "unknown"),
            decision_grade=risk.get("decision_grade", "unknown")
        ))
        
    if conn:
        conn.close()

    # Ordenar pelas opções mais baratas
    options.sort(key=lambda x: x.total_cost_usd)
    if options:
        options[0].is_recommended = True
        
    intended_option = next((opt for opt in options if opt.port_id == intended_port_id), None)
    best_option = options[0] if options else None
    
    if intended_option and best_option and intended_option.port_id != best_option.port_id:
        savings = intended_option.total_cost_usd - best_option.total_cost_usd
        summary = (
            f"Alerta de Arbitragem: Redirecionar carga de {intended_option.port_name} ({intended_option.state_code}) "
            f"para {best_option.port_name} ({best_option.state_code}) economiza US$ {savings:,.2f}. "
            f"Motivo principal: ICMS de {best_option.icms_rate_pct}% vs {intended_option.icms_rate_pct}%, e Frete Terrestre de US$ {best_option.inland_freight_cost_usd:,.0f} vs US$ {intended_option.inland_freight_cost_usd:,.0f} "
            f"e fila de {best_option.delay_days} dias vs {intended_option.delay_days} dias."
        )
    elif intended_option and best_option and intended_option.port_id == best_option.port_id:
        summary = f"A rota originalmente pretendida ({intended_option.port_name}) já é a opção de menor custo logístico-tributário atual."
    else:
        summary = "Análise concluída. Verifique as alternativas."

    return FiscalRoutingResponse(
        intended_port_id=intended_port_id,
        commodity=commodity,
        cargo_value_usd=cargo_value_usd,
        inland_uf=inland_uf,
        cargo_tons=cargo_tons,
        options=options,
        recommendation_summary=summary
    )
