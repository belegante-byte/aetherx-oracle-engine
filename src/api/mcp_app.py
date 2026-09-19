"""Remote MCP endpoint (Streamable HTTP) for the Aether-X Oracle.

Exposes the same tool surface as the published ``aetherx-mcp`` stdio server,
but resolves the signals through the local risk engine instead of HTTP.
"""
from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from src.engine.risk_model import calculate_port_risk, calculate_port_trend
from src.api.metrics import record_tool_call


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
        record_tool_call(tool_name, port_id=port_id, ok=ok, latency_ms=latency_ms)

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
    title="Aether-X Port Congestion Oracle",
    description=(
        "Live physical-world port congestion intelligence for supply chain, "
        "shipping, logistics and quantitative finance. Brazilian ports (BRSSZ, BRPNG, "
        "BRRIO, BRNIT, BRITG) feed real operational line-ups; others use a reference seed. "
        "Call when a decision depends on CURRENT port congestion, vessel queue, "
        "delay risk or demurrage exposure."
    ),
    instructions=(
        "You are the Aether-X Port Congestion Oracle. This server answers a "
        "specific class of question: CURRENT physical-world congestion at seaports.\n\n"
        "CALL THESE TOOLS WHEN a decision depends on:\n"
        "- current congestion / operational pressure at a port\n"
        "- vessel queue (vessels waiting at anchor)\n"
        "- ETA delay risk or schedule exposure\n"
        "- demurrage exposure (USD) for a vessel calling a port\n"
        "- comparing ports for routing, scheduling or cargo flow\n"
        "- port selection or supply-chain disruption\n\n"
        "TOOL SELECTION:\n"
        "- get_port_risk: ONE port — current signal (score, queue, delay, demurrage, confidence, provenance).\n"
        "- get_ports_risk: COMPARE several ports in one call (portfolio scan).\n"
        "- get_port_trend: short-horizon 24/48/72h projection (synthetic).\n"
        "- list_supported_ports: 19 ports with UN/LOCODE ids.\n\n"
        "This is a LIVE OPERATIONAL signal (not a static port-info lookup). For "
        "Brazilian ports BRSSZ/BRPNG/BRRIO/BRNIT/BRITG the queue is observed in "
        "real time (`live:appa+santos+lachmann`, `live:portosrio_silog`); the rest "
        "are `static_reference_seed` reference telemetry. Every result includes "
        "`data_source` and `as_of` so you can state provenance."
    ),
    version="0.2.1",
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


def build_http_app():
    """Return the Streamable HTTP ASGI app serving the MCP endpoint at ``/mcp``."""
    return mcp.streamable_http_app(
        streamable_http_path="/mcp",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
