"""Remote MCP endpoint (Streamable HTTP) for the Aether-X Oracle.

Exposes the same tool surface as the published ``aetherx-mcp`` stdio server,
but resolves the signals through the local risk engine instead of HTTP.
"""
from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from src.engine.risk_model import calculate_port_risk, calculate_port_trend

SUPPORTED_PORTS: list[dict[str, str]] = [
    {"port_id": "AEDXB", "port_name": "Dubai / Jebel Ali", "country": "EAU"},
    {"port_id": "BRRIO", "port_name": "Rio de Janeiro", "country": "Brasil"},
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
        "Predictive port congestion signals for global trade, supply chain and "
        "quantitative finance."
    ),
    instructions=(
        "Predictive port congestion signals for global trade, supply chain and "
        "quantitative finance. Use get_port_risk for a single port, "
        "get_ports_risk to scan a portfolio of ports in parallel and "
        "get_port_trend for the 24h/48h/72h congestion projection."
    ),
    version="0.2.1",
    website_url="https://aether-x-oracle-production.up.railway.app",
)


@mcp.tool()
def get_port_risk(port_id: str) -> dict[str, Any]:
    """Return the predictive congestion signal for a single port.

    Args:
        port_id: UN/LOCODE of the port, e.g. "BRSSZ" (Santos), "CNSHA" (Shanghai).
    """
    return calculate_port_risk(port_id.strip().upper())


@mcp.tool()
def get_ports_risk(port_ids: list[str]) -> list[dict[str, Any]]:
    """Return congestion signals for several ports in parallel.

    Args:
        port_ids: list of UN/LOCODEs, e.g. ["BRSSZ", "CNSHA", "NLRTM"].
    """
    ids = [p.strip().upper() for p in port_ids if p and p.strip()]
    return [calculate_port_risk(p) for p in ids]


@mcp.tool()
def get_port_trend(port_id: str) -> dict[str, Any]:
    """Return the 24h, 48h and 72h congestion projection for a single port.

    Args:
        port_id: UN/LOCODE of the port, e.g. "BRSSZ" (Santos), "CNSHA" (Shanghai).
    """
    return calculate_port_trend(port_id.strip().upper())


@mcp.tool()
def list_supported_ports() -> list[dict[str, str]]:
    """List the 16 ports pre-seeded in the oracle (id, name, country)."""
    return SUPPORTED_PORTS


def build_http_app():
    """Return the Streamable HTTP ASGI app serving the MCP endpoint at ``/mcp``."""
    return mcp.streamable_http_app(
        streamable_http_path="/mcp",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
