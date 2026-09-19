"""Aether-X Oracle MCP server.

Exposes the Aether-X Port Congestion Oracle to MCP-compatible agents
(Claude Desktop, Cursor, VS Code, custom LLM agents).

Run (stdio):

    RAPIDAPI_KEY=xxxx aetherx-mcp

By default it calls the public production API. When ``RAPIDAPI_KEY`` is set,
requests are routed through the RapidAPI gateway (metered billing).
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

PRODUCTION_URL = "https://aetherx.aether-grid.io"
DEFAULT_RAPIDAPI_HOST = "aether-x-port-congestion-oracle.p.rapidapi.com"

SUPPORTED_PORTS: list[dict[str, str]] = [
    {"port_id": "AEDXB", "port_name": "Dubai / Jebel Ali", "country": "EAU"},
    {"port_id": "BRITG", "port_name": "Itaguaí", "country": "Brasil"},
    {"port_id": "BRNIT", "port_name": "Niterói", "country": "Brasil"},
    {"port_id": "BRPNG", "port_name": "Paranaguá", "country": "Brasil"},
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
        "Reference port congestion signals for global trade, supply chain and "
        "quantitative finance. Brazilian ports (BRSSZ, BRPNG, BRRIO) feed live line-ups; "
        "the rest use a reference seed."
    ),
    instructions=(
        "Reference congestion signals for ports. Use get_port_risk for a "
        "single port, get_ports_risk to scan a portfolio of ports in parallel and "
        "get_port_trend for the 24h/48h/72h SYNTHETIC projection. Every "
        "result includes `data_source` and `as_of`. For Brazilian ports BRSSZ/BRPNG/BRRIO "
        "it is live (`live:appa+santos+lachmann`, `live:portosrio_silog`); the rest are "
        "`static_reference_seed` reference telemetry."
    ),
    version="0.2.4",
    website_url="https://aetherx.aether-grid.io",
)


def _base_url() -> str:
    return os.getenv("AETHERX_BASE_URL", PRODUCTION_URL).rstrip("/")


def _headers() -> dict[str, str]:
    key = os.getenv("RAPIDAPI_KEY")
    if not key:
        return {}
    return {
        "X-RapidAPI-Key": key,
        "X-RapidAPI-Host": os.getenv("RAPIDAPI_HOST", DEFAULT_RAPIDAPI_HOST),
    }


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=30.0)


async def _fetch(port_id: str) -> dict[str, Any]:
    url = f"{_base_url()}/v1/port-risk"
    async with _client() as client:
        resp = await client.get(
            url, params={"port_id": port_id}, headers=_headers()
        )
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def get_port_risk(port_id: str) -> dict[str, Any]:
    """Return the congestion signal for a single port (live for BR, reference seed otherwise).

    Args:
        port_id: UN/LOCODE of the port, e.g. "BRSSZ" (Santos), "CNSHA" (Shanghai).
    """
    return await _fetch(port_id.strip().upper())


@mcp.tool()
async def get_ports_risk(port_ids: list[str]) -> list[dict[str, Any]]:
    """Return congestion signals for several ports in parallel (live for BR, reference seed otherwise).

    Args:
        port_ids: list of UN/LOCODEs, e.g. ["BRSSZ", "CNSHA", "NLRTM"].
    """
    ids = [p.strip().upper() for p in port_ids if p and p.strip()]
    return list(await asyncio.gather(*(_fetch(p) for p in ids)))


async def _fetch_trend(port_id: str) -> dict[str, Any]:
    url = f"{_base_url()}/v1/port-trend"
    async with _client() as client:
        resp = await client.get(
            url, params={"port_id": port_id}, headers=_headers()
        )
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def get_port_trend(port_id: str) -> dict[str, Any]:
    """Return the 24h, 48h and 72h SYNTHETIC projection for a single port (not a live forecast).

    Args:
        port_id: UN/LOCODE of the port, e.g. "BRSSZ" (Santos), "CNSHA" (Shanghai).
    """
    return await _fetch_trend(port_id.strip().upper())


@mcp.tool()
def list_supported_ports() -> list[dict[str, str]]:
    """List the 19 ports in the oracle (id, name, country)."""
    return SUPPORTED_PORTS


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
