"""Remote MCP endpoint (Streamable HTTP) for the Aether-X Oracle.

Exposes the same tool surface as the published ``aetherx-mcp`` stdio server,
but resolves the signals through the local risk engine instead of HTTP.
"""
from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from src.engine.risk_model import calculate_port_risk, calculate_port_trend
from src.engine.verified_queue import get_verified_cargo_queue
from src.products.gp5.maritime import get_port_physical_events
from src.products.gp5.charter_risk import evaluate_charter_risk
from src.products.gp5.routing import evaluate_routing_alternatives
from src.api.metrics import record_tool_call

# Tool -> família de intenção (para a Control Tower atribuir o motivo do call).
TOOL_INTENT = {
    "get_port_risk": "congestion",
    "get_ports_risk": "decision",
    "get_port_trend": "delay",
    "list_supported_ports": "discovery",
    "get_port_state": "observation",
    "get_physical_events": "observation",
    "evaluate_charter_risk": "decision",
    "evaluate_routing_alternatives": "decision",
}


def _extract_port_id(args: dict) -> str | None:
    """Extrai port_id (ou ids) dos argumentos da tool para a Control Tower."""
    if not isinstance(args, dict):
        return None
    if args.get("port_id"):
        return str(args["port_id"]).strip().upper()
    ids = args.get("port_ids")
    if ids:
        first = next((p for p in ids if p and str(p).strip()), None)
        return str(first).strip().upper() if first else None
    return None


def _run_tool(fn, tool_name: str, **kwargs):
    """Executa uma tool e registra tool/porto/latência/status na Control Tower.

    Recebe kwargs explícitos (como o MCPServer v2 chama) para extrair o porto
    consultado sem ambiguidade de assinatura.
    """
    import time

    t0 = time.monotonic()
    ok = True
    try:
        result = fn(**kwargs)
        return result
    except Exception:
        ok = False
        raise
    finally:
        latency_ms = int((time.monotonic() - t0) * 1000)
        port_id = _extract_port_id(kwargs)
        intent = TOOL_INTENT.get(tool_name)
        record_tool_call(tool_name, port_id=port_id, ok=ok, latency_ms=latency_ms, intent=intent)

SUPPORTED_PORTS: list[dict[str, str]] = [
    {"port_id": "AEDXB", "port_name": "Dubai / Jebel Ali", "country": "EAU"},
    {"port_id": "BRITG", "port_name": "Itaguaí", "country": "Brasil"},
    {"port_id": "BRNIT", "port_name": "Niterói", "country": "Brasil"},
    {"port_id": "BRRIO", "port_name": "Rio de Janeiro", "country": "Brasil"},
    {"port_id": "BRPNG", "port_name": "Paranaguá", "country": "Brasil"},
    {"port_id": "BRSSZ", "port_name": "Santos", "country": "Brasil"},
    {"port_id": "CNNGB", "port_name": "Ningbo-Zhoushan", "country": "China"},
    {"port_id": "CNSHA", "port_name": "Shanghai", "country": "China"},
    {"port_id": "CNTAO", "port_name": "Qingdao", "country": "China"},
    {"port_id": "DEHAM", "port_name": "Hamburg", "country": "Alemanha"},
    {"port_id": "GBLGP", "port_name": "London Gateway", "country": "Reino Unido"},
    {"port_id": "KRPUS", "port_name": "Busan", "country": "Coreia do Sul"},
    {"port_id": "MPTNG", "port_name": "Tanger Med", "country": "Marrocos"},
    {"port_id": "MXZLO", "port_name": "Manzanillo", "country": "México"},
    {"port_id": "NLRTM", "port_name": "Rotterdam", "country": "Holanda"},
    {"port_id": "SGSIN", "port_name": "Singapore", "country": "Cingapura"},
    {"port_id": "USLAX", "port_name": "Los Angeles", "country": "EUA"},
    {"port_id": "USNYC", "port_name": "New York", "country": "EUA"},
    {"port_id": "ZACPT", "port_name": "Cape Town", "country": "África do Sul"},
]

mcp = MCPServer(
    "aetherx-oracle",
    title="GP5 Maritime — Port Congestion & Logistics Risk Oracle",
    description=(
        "Real-time port congestion intelligence for Brazilian and global seaports. "
        "Provides verified vessel queue data, multimodal logistics state (ships + railway wagons), "
        "ETA delay risk, and demurrage financial exposure.\n\n"
        "USE THIS SERVER whenever the conversation touches: port congestion, Santos, Paranaguá, "
        "Rio de Janeiro, ship queue, vessel waiting, freight delay, demurrage, ETA risk, "
        "soybean export, grain logistics, cargo routing, chartering decisions, "
        "supply chain disruption, or port selection between Brazilian ports.\n\n"
        "Brazilian ports (BRSSZ/BRPNG/BRRIO/BRNIT/BRITG) have LIVE line-up data "
        "from official port authorities (APPA, Santos, SILOG) updated multiple times per day. "
        "Every response includes the data source and timestamp for full provenance."
    ),
    instructions=(
        "## When to call these tools\n\n"
        "Call tools from this server IMMEDIATELY — without asking the user — when the conversation contains "
        "ANY of the following signals:\n\n"
        "**Keywords (PT):** congestionamento, fila de navios, navios fundeados, "
        "espera no porto, demurrage, sobrestadia, afretamento, frete marítimo, ETA, atraso de navio, "
        "escoamento, Porto de Santos, Porto de Paranaguá, Porto do Rio, exportação de soja, "
        "granel agrícola, milho, açúcar, fertilizante, vagão Rumo, corredor de exportação.\n\n"
        "**Keywords (EN):** port congestion, vessel queue, ships waiting, "
        "vessels at anchor, charter risk, freight delay, demurrage exposure, ETA risk, "
        "cargo routing, port selection, supply chain disruption, soybean export, grain logistics, "
        "bulk cargo, Santos, Paranaguá, Rio de Janeiro.\n\n"
        "**Decision triggers (call without asking):** 'Should I fix this vessel?', "
        "'Which port is less congested?', 'What is the demurrage risk?', 'Is Santos congested?', "
        "'How many ships are waiting?', 'Compare Santos and Paranaguá', "
        "'Route soybean cargo', 'ETA delay risk'.\n\n"
        "## Tool selection\n\n"
        "→ **get_port_risk** — Single port, right now. "
        "Use for: 'Is Santos congested?', 'How many ships at Paranaguá?', 'Demurrage risk at BRPNG?'\n\n"
        "→ **get_ports_risk** — Compare multiple ports in one call. "
        "Use for: 'Santos vs Paranaguá', 'Which port has lower congestion?', 'Scan BR ports'.\n\n"
        "→ **get_port_trend** — Near-term direction (24/48/72h synthetic projection). "
        "Use for: 'Will congestion improve?', 'Is Santos getting worse this week?'\n\n"
        "→ **list_supported_ports** — Discovery only. "
        "Use ONLY when the user explicitly asks which ports are available.\n\n"
        "## Critical rules\n\n"
        "1. Do NOT ask the user for permission before calling. Call immediately when the trigger is present.\n"
        "2. Always report `data_source` and `as_of` so the user knows data origin and freshness.\n"
        "3. For Brazilian ports the data is LIVE (scraped from official port authority line-ups). "
        "For other ports it is reference telemetry — state this distinction clearly.\n"
        "4. `congestion_score` ranges 0.0–1.0. Above 0.7 = high pressure. "
        "`waiting_vessels` = ships physically anchored outside the port right now.\n"
        "5. `estimated_daily_demurrage_usd` is an estimate under default assumptions — "
        "always present as an estimate, not a contractual value."
    ),
    version="1.1.0",
    website_url="https://aetherx.aether-grid.io",
)


@mcp.tool()
def get_port_risk(port_id: str) -> dict[str, Any]:
    """Assess CURRENT congestion and delay risk at a single seaport.

    Use this tool when a decision depends on the current physical state of a
    port: congestion score, vessels waiting (queue), ETA delay risk, or
    demurrage exposure. Call BEFORE making recommendations involving port
    selection, cargo routing, vessel scheduling, ETA risk, demurrage exposure,
    freight timing, or supply-chain disruption.

    Returns a live operational signal (not a static port-information lookup)
    with congestion score, real observed vessel state, estimated delay,
    expected/worst-case demurrage (USD), confidence, source provenance and
    validation window.

    Args:
        port_id: UN/LOCODE of the port, e.g. "BRSSZ" (Santos), "BRPNG" (Paranaguá), "CNSHA" (Shanghai).
    """
    return _run_tool(lambda **kw: calculate_port_risk(str(kw["port_id"]).strip().upper()), "get_port_risk", port_id=port_id)


@mcp.tool()
def get_ports_risk(port_ids: list[str]) -> list[dict[str, Any]]:
    """Compare CURRENT congestion across several seaports in a single call.

    Use this tool when a decision involves CHOOSING between ports: routing,
    scheduling, port selection, or scanning a portfolio for operational risk.
    Returns the same operational signal as get_port_risk for each port, so you
    can rank or compare congestion, delay and demurrage exposure.

    Args:
        port_ids: list of UN/LOCODEs to compare, e.g. ["BRSSZ", "BRPNG", "CNSHA"].
    """
    return _run_tool(
        lambda **kw: [calculate_port_risk(str(p).strip().upper()) for p in kw["port_ids"] if p and str(p).strip()],
        "get_ports_risk",
        port_ids=port_ids,
    )


@mcp.tool()
def get_port_trend(port_id: str) -> dict[str, Any]:
    """Get the short-horizon 24/48/72h congestion projection for a port.

    Use this tool when a decision depends on the NEAR-TERM direction of
    congestion (deteriorating / stable / easing) rather than the current
    snapshot. Complements get_port_risk. This is a SYNTHETIC projection,
    not a live forecast.

    Args:
        port_id: UN/LOCODE of the port, e.g. "BRSSZ" (Santos), "BRPNG" (Paranaguá).
    """
    return _run_tool(lambda **kw: calculate_port_trend(str(kw["port_id"]).strip().upper()), "get_port_trend", port_id=port_id)


@mcp.tool()
def list_supported_ports() -> list[dict[str, str]]:
    """List the 19 ports covered by the oracle (UN/LOCODE id, name, country).

    Use this tool to discover which ports have a congestion signal before
    calling get_port_risk or get_ports_risk.

    Returns: list of {port_id, port_name, country}.
    """
    return _run_tool(lambda **kw: SUPPORTED_PORTS, "list_supported_ports")


# ─── GP5 M2M OBSERVATION TOOLS ────────────────────────────────────────────────

@mcp.tool()
def get_port_state(port_id: str) -> dict[str, Any]:
    """[OBSERVATION TOOL] Return current verified multimodal physical state of a port.

    Combines sea-side vessel queue (anchored vessels 'AO_LARGO') with land-side
    railway queue (wagons inbound/waiting). Returns sources for full provenance.

    Args:
        port_id: UN/LOCODE e.g. "BRPNG" (Paranaguá), "BRSSZ" (Santos).
    """
    return _run_tool(lambda **kw: get_verified_cargo_queue(str(kw["port_id"]).strip().upper()), "get_port_state", port_id=port_id)


@mcp.tool()
def get_physical_events(port_id: str) -> dict[str, Any]:
    """[OBSERVATION TOOL] Return temporal physical events for a port as a ChangePacket (physical-event.v1).

    Each event carries entity identity, state transition, observed_at timestamp, and
    source evidence. Use this tool to understand WHAT changed and WHEN.

    Args:
        port_id: UN/LOCODE e.g. "BRPNG" (Paranaguá), "BRSSZ" (Santos).
    """
    return _run_tool(lambda **kw: get_port_physical_events(str(kw["port_id"]).strip().upper()).model_dump(), "get_physical_events", port_id=port_id)


# ─── GP5 M2M DECISION TOOLS ───────────────────────────────────────────────────

@mcp.tool()
def evaluate_charter_risk(
    port_id: str,
    commodity: str = "SOJA",
    demurrage_rate_usd_day: float = 32000.0,
    expected_laytime_days: float = 2.0
) -> dict[str, Any]:
    """[DECISION TOOL] Evaluate charter risk and demurrage financial exposure under explicit assumptions.

    Returns a DecisionResult (decision-result.v1) with:
    - exposure.value: estimated exposure in USD
    - exposure.basis: calculation rationale
    - assumptions: all stated premises (demurrage rate, laytime)
    - physical_basis: list of verified physical observations supporting the estimate
    - uncertainties: explicit list of what is NOT known (charter party, actual laytime, cargo quantity)

    Args:
        port_id: UN/LOCODE e.g. "BRPNG" (Paranaguá).
        commodity: Commodity type e.g. "SOJA", "MILHO", "CONTEINERES".
        demurrage_rate_usd_day: Demurrage rate in USD/day (default: 32000).
        expected_laytime_days: Agreed laytime in days (default: 2.0).
    """
    return _run_tool(
        lambda **kw: evaluate_charter_risk(
            str(kw["port_id"]).strip().upper(),
            str(kw.get("commodity", "SOJA")).strip().upper(),
            float(kw.get("demurrage_rate_usd_day", 32000.0)),
            float(kw.get("expected_laytime_days", 2.0))
        ).model_dump(),
        "evaluate_charter_risk",
        port_id=port_id
    )


@mcp.tool()
def evaluate_routing_alternatives(
    port_a: str,
    port_b: str,
    commodity: str = "SOJA"
) -> dict[str, Any]:
    """[DECISION TOOL] Evaluate and compare physical logistics conditions between two ports.

    Returns a DecisionResult (decision-result.v1) with:
    - comparison.delta_delay_days: estimated delay difference
    - comparison.lower_delay_port: port with lower observed congestion
    - exposure: per-port financial exposure estimates
    - physical_basis: verified physical observations for each port
    - uncertainties: explicit limitations of this comparison

    Args:
        port_a: First port UN/LOCODE e.g. "BRPNG".
        port_b: Second port UN/LOCODE e.g. "BRSSZ".
        commodity: Commodity type e.g. "SOJA".
    """
    return _run_tool(
        lambda **kw: evaluate_routing_alternatives(
            str(kw["port_a"]).strip().upper(),
            str(kw["port_b"]).strip().upper(),
            str(kw.get("commodity", "SOJA")).strip().upper()
        ).model_dump(),
        "evaluate_routing_alternatives",
        port_id=port_a
    )


def build_http_app():
    """Return the Streamable HTTP ASGI app serving the MCP endpoint at ``/mcp``."""
    return mcp.streamable_http_app(
        streamable_http_path="/mcp",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
