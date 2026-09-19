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
"Reference port congestion signals for global trade, supply chain and "
         "quantitative finance. Brazilian ports (BRSSZ, BRPNG, BRRIO, BRNIT, BRITG) feed live line-ups; "
         "the rest use a static reference seed."
    ),
    instructions=(
        "Reference congestion signals for ports. Use get_port_risk for a "
        "single port, get_ports_risk to scan a portfolio of ports in parallel and "
        "get_port_trend for the 24h/48h/72h synthetic projection. Every "
        "result includes `data_source` and `as_of`. For Brazilian ports BRSSZ/BRPNG/BRRIO/BRNIT/BRITG "
        "it is live (`live:appa+santos+lachmann`, `live:portosrio_silog`); the rest are "
        "`static_reference_seed` reference telemetry."
    ),
    version="0.2.1",
    website_url="https://aetherx.aether-grid.io",
)


@mcp.tool()
def get_port_risk(port_id: str) -> dict[str, Any]:
    """Return the congestion signal for a single port (live for BR, reference seed otherwise).

    Args:
        port_id: UN/LOCODE of the port, e.g. "BRSSZ" (Santos), "CNSHA" (Shanghai).
    """
    return _run_tool(lambda **kw: calculate_port_risk(str(kw["port_id"]).strip().upper()), "get_port_risk", port_id=port_id)


@mcp.tool()
def get_ports_risk(port_ids: list[str]) -> list[dict[str, Any]]:
    """Return congestion signals for several ports in parallel (live for BR, reference seed otherwise).

    Args:
        port_ids: list of UN/LOCODEs, e.g. ["BRSSZ", "CNSHA", "NLRTM"].
    """
    return _run_tool(
        lambda **kw: [calculate_port_risk(str(p).strip().upper()) for p in kw["port_ids"] if p and str(p).strip()],
        "get_ports_risk",
        port_ids=port_ids,
    )


@mcp.tool()
def get_port_trend(port_id: str) -> dict[str, Any]:
    """Return the 24h, 48h and 72h SYNTHETIC projection for a single port (not a live forecast).

    Args:
        port_id: UN/LOCODE of the port, e.g. "BRSSZ" (Santos), "CNSHA" (Shanghai).
    """
    return _run_tool(lambda **kw: calculate_port_trend(str(kw["port_id"]).strip().upper()), "get_port_trend", port_id=port_id)


@mcp.tool()
def list_supported_ports() -> list[dict[str, str]]:
    """List the 19 ports in the oracle (id, name, country)."""
    return _run_tool(lambda **kw: SUPPORTED_PORTS, "list_supported_ports")


def build_http_app():
    """Return the Streamable HTTP ASGI app serving the MCP endpoint at ``/mcp``."""
    return mcp.streamable_http_app(
        streamable_http_path="/mcp",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
