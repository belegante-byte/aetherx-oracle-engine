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
    inland_freight_rate_usd_per_ton: float
    inland_freight_source: str
    inland_freight_as_of: str
    inland_freight_is_real: bool
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


# Câmbio de referência: dólar comercial fechamento 28/09/2026 em R$ 5,22
# (Agência Brasil / Reuters), sobrescrevível via USD_BRL_FX.
USD_BRL_FX_DEFAULT = 5.22
FREIGHT_DEFAULT_AS_OF = "2026-07"  # Boletim Logístico Conab (última referência publicada)


def _usd_brl_fx() -> float:
    try:
        val = float(os.getenv("USD_BRL_FX", str(USD_BRL_FX_DEFAULT)))
        return val if val > 0 else USD_BRL_FX_DEFAULT
    except ValueError:
        return USD_BRL_FX_DEFAULT


# Matriz LEGACY (mock) que o produto usava antes da Fase 2. Ainda é usada como
# fallback EXPLÍCITO quando a tabela `freight_rates` (corredores reais, semeada
# no boot por init_prod_db) não existe — ex.: snapshot binário antigo. O flag
# `is_real=False` e a source "LEGACY_MOCK_FALLBACK" tornam a degradação visível.
_LEGACY_FREIGHT_MATRIX = {
    "MT": {"BRSSZ": 45.0, "BRPNG": 50.0, "BRMAO": 35.0, "BRRIO": 55.0, "BRRGD": 65.0},
    "GO": {"BRSSZ": 40.0, "BRPNG": 45.0, "BRMAO": 50.0, "BRRIO": 50.0, "BRRGD": 60.0},
    "PR": {"BRSSZ": 25.0, "BRPNG": 10.0, "BRMAO": 70.0, "BRRIO": 35.0, "BRRGD": 30.0},
    "SP": {"BRSSZ": 10.0, "BRPNG": 25.0, "BRMAO": 80.0, "BRRIO": 20.0, "BRRGD": 45.0},
}


def estimate_inland_freight_usd(port_id: str, inland_uf: str, cargo_tons: float, conn=None) -> dict:
    """Custo de frete terrestre (USD) + metadados de fonte.

    Fase 2 (Fretes Reais): prioriza a tabela `freight_rates`, semeada no boot
    com tarifas reais de corredores de grãos (CONAB Boletim Logístico 07/2026,
    Sifreca/ESALQ) em R$/t convertidos a USD/t via USD_BRL_FX. Corridors sem
    tarifa publicada levam estimativa calibrada e marcada `is_real=False`.

    Degrada para LEGACY_MOCK_FALLBACK (explícito) se a tabela não existir.
    """
    fx = _usd_brl_fx()
    if conn:
        try:
            row = conn.execute(
                "SELECT rate_brl_per_ton, source, reference_date, is_estimate "
                "FROM freight_rates WHERE origin_uf = ? AND port_id = ?",
                [inland_uf.upper(), port_id.upper()],
            ).fetchone()
            if row:
                rate_brl = float(row[0])
                rate_usd = round(rate_brl / fx, 4)
                return {
                    "cost_usd": round(cargo_tons * rate_usd, 2),
                    "rate_usd_per_ton": rate_usd,
                    "source": str(row[1]),
                    "as_of": str(row[2] if row[2] else FREIGHT_DEFAULT_AS_OF),
                    "is_real": not bool(row[3]),
                }
        except duckdb.CatalogException:
            pass  # tabela freight_rates ausente -> fallback legacy abaixo

    rate_per_ton = _LEGACY_FREIGHT_MATRIX.get(inland_uf.upper(), {}).get(port_id.upper(), 60.0)
    return {
        "cost_usd": round(cargo_tons * rate_per_ton, 2),
        "rate_usd_per_ton": rate_per_ton,
        "source": "LEGACY_MOCK_FALLBACK (sem tabela freight_rates)",
        "as_of": "n/a",
        "is_real": False,
    }

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
            try:
                row = conn.execute(
                    "SELECT icms_rate_pct, exemption_note FROM tax_rules WHERE state_code = ? AND commodity = ?",
                    [inland_uf.upper(), commodity]
                ).fetchone()
                if row:
                    icms_pct = row[0]
                    exemption = row[1]
            except duckdb.CatalogException:
                # Tabela tax_rules é criada no boot (startCommand roda
                # init_prod_db); se ausente (ex.: frozensnapshot de teste),
                # degrada para a alíquota padrão em vez de quebrar.
                icms_pct = 18.0
                exemption = None
                
        icms_cost = cargo_value_usd * (icms_pct / 100.0)
        freight = estimate_inland_freight_usd(pid, inland_uf, cargo_tons, conn=conn)
        total_cost = round(demurrage + icms_cost + freight["cost_usd"], 2)
        
        options.append(PortRouteOption(
            port_id=pid,
            port_name=risk.get("port_name", pid),
            state_code=state_code,
            congestion_score=risk.get("congestion_score", 0),
            delay_days=delay_days,
            demurrage_cost_usd=demurrage,
            icms_rate_pct=icms_pct,
            icms_cost_usd=round(icms_cost, 2),
            inland_freight_cost_usd=freight["cost_usd"],
            inland_freight_rate_usd_per_ton=freight["rate_usd_per_ton"],
            inland_freight_source=freight["source"],
            inland_freight_as_of=freight["as_of"],
            inland_freight_is_real=freight["is_real"],
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
        d_icms = intended_option.icms_cost_usd - best_option.icms_cost_usd
        d_freight = intended_option.inland_freight_cost_usd - best_option.inland_freight_cost_usd
        d_demurrage = intended_option.demurrage_cost_usd - best_option.demurrage_cost_usd

        # ICMS é apurado pelo estado de destino (inland_uf) — idêntico entre as
        # opções — então só entra na prosa se realmente variar. Os drivers reais
        # são frete terrestre e fila/demurrage, ordenados por contribuição.
        notes = []
        if abs(d_icms) >= 1:
            notes.append((abs(d_icms), f"ICMS de {best_option.icms_rate_pct:g}% vs {intended_option.icms_rate_pct:g}%"))
        if abs(d_freight) >= 1:
            notes.append((abs(d_freight), f"frete terrestre de US$ {best_option.inland_freight_cost_usd:,.0f} vs US$ {intended_option.inland_freight_cost_usd:,.0f}"))
        if abs(d_demurrage) >= 1:
            notes.append((abs(d_demurrage), f"fila/demurrage de US$ {best_option.demurrage_cost_usd:,.0f} em {best_option.delay_days:g} dias vs US$ {intended_option.demurrage_cost_usd:,.0f} em {intended_option.delay_days:g} dias"))

        opening = (
            f"Alerta de Arbitragem: Redirecionar carga de {intended_option.port_name} ({intended_option.state_code}) "
            f"para {best_option.port_name} ({best_option.state_code}) economiza US$ {savings:,.2f}."
        )
        if notes:
            notes.sort(key=lambda item: item[0], reverse=True)
            if len(notes) == 1:
                summary = f"{opening} Motivo principal: {notes[0][1]}."
            else:
                summary = f"{opening} Motivo principal: {notes[0][1]}. Fator adicional: {', '.join(n for _, n in notes[1:])}."
        else:
            summary = opening
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
