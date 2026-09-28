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
    demurrage_cost_usd: int
    icms_rate_pct: float
    icms_cost_usd: float
    exemption_note: Optional[str]
    total_cost_usd: float
    is_recommended: bool

class FiscalRoutingResponse(BaseModel):
    schema_version: str = "fiscal-routing.v1"
    intended_port_id: str
    commodity: str
    cargo_value_usd: float
    options: List[PortRouteOption]
    recommendation_summary: str

def get_state_from_port(port_id: str) -> str:
    # Mapeamento simplificado para portos BR suportados no MVP
    mapping = {
        "BRSSZ": "SP",
        "BRPNG": "PR",
        "BRIQI": "MA",
        "BRRIO": "RJ",
        "BRNIT": "RJ",
        "BRITG": "RJ",
        "BRRGD": "RS",
        "BRVDC": "PA",
        "BRMAO": "AM"
    }
    return mapping.get(port_id.upper(), "UNKNOWN")

def evaluate_fiscal_routing(intended_port_id: str, commodity: str, cargo_value_usd: float = 10000000.0) -> FiscalRoutingResponse:
    commodity = commodity.upper()
    intended_port_id = intended_port_id.upper()
    
    # Busca os portos do Brasil que podemos usar como alternativas (apenas BR no MVP para ICMS)
    br_ports = ["BRSSZ", "BRPNG", "BRIQI", "BRRIO", "BRRGD"]
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
        demurrage = risk.get("estimated_daily_demurrage_usd", 0)
        
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
        total_cost = demurrage + icms_cost
        
        options.append(PortRouteOption(
            port_id=pid,
            port_name=risk.get("port_name", pid),
            state_code=state_code,
            congestion_score=risk.get("congestion_score", 0),
            delay_days=delay_days,
            demurrage_cost_usd=demurrage,
            icms_rate_pct=icms_pct,
            icms_cost_usd=icms_cost,
            exemption_note=exemption,
            total_cost_usd=total_cost,
            is_recommended=False
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
            f"Motivo principal: ICMS de {best_option.icms_rate_pct}% vs {intended_option.icms_rate_pct}% "
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
        options=options,
        recommendation_summary=summary
    )
