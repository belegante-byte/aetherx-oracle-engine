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
    {"port_id": "ARBUE", "port_name": "Buenos Aires", "country": "Argentina"},
    {"port_id": "ARROS", "port_name": "Rosario / San Lorenzo", "country": "Argentina"},
    {"port_id": "BEANT", "port_name": "Antwerp", "country": "Bélgica"},
    {"port_id": "BRITG", "port_name": "Itaguaí", "country": "Brasil"},
    {"port_id": "BRMAO", "port_name": "Itaqui / São Luís", "country": "Brasil"},
    {"port_id": "BRNIT", "port_name": "Niterói", "country": "Brasil"},
    {"port_id": "BRPNG", "port_name": "Paranaguá", "country": "Brasil"},
    {"port_id": "BRRGD", "port_name": "Rio Grande", "country": "Brasil"},
    {"port_id": "BRRIO", "port_name": "Rio de Janeiro", "country": "Brasil"},
    {"port_id": "BRSSZ", "port_name": "Santos", "country": "Brasil"},
    {"port_id": "BRVDC", "port_name": "Barcarena / Vila do Conde", "country": "Brasil"},
    {"port_id": "CAVAN", "port_name": "Vancouver", "country": "Canadá"},
    {"port_id": "CNNGB", "port_name": "Ningbo-Zhoushan", "country": "China"},
    {"port_id": "CNSHA", "port_name": "Shanghai", "country": "China"},
    {"port_id": "CNSZX", "port_name": "Shenzhen / Yantian", "country": "China"},
    {"port_id": "CNTAO", "port_name": "Qingdao", "country": "China"},
    {"port_id": "CNTXG", "port_name": "Tianjin", "country": "China"},
    {"port_id": "DEHAM", "port_name": "Hamburg", "country": "Alemanha"},
    {"port_id": "EGSUZ", "port_name": "Canal de Suez / Port Said", "country": "Egito"},
    {"port_id": "GBLGP", "port_name": "London Gateway", "country": "Reino Unido"},
    {"port_id": "JPTYO", "port_name": "Tokyo / Yokohama", "country": "Japão"},
    {"port_id": "KRPUS", "port_name": "Busan", "country": "Coreia do Sul"},
    {"port_id": "MPTNG", "port_name": "Tanger Med", "country": "Marrocos"},
    {"port_id": "MXZLO", "port_name": "Manzanillo", "country": "México"},
    {"port_id": "NLRTM", "port_name": "Rotterdam", "country": "Holanda"},
    {"port_id": "PABLB", "port_name": "Canal do Panamá / Balboa", "country": "Panamá"},
    {"port_id": "SARAN", "port_name": "Ras Tanura", "country": "Arábia Saudita"},
    {"port_id": "SGSIN", "port_name": "Singapore", "country": "Cingapura"},
    {"port_id": "USHOU", "port_name": "Houston", "country": "EUA"},
    {"port_id": "USLAX", "port_name": "Los Angeles", "country": "EUA"},
    {"port_id": "USMSY", "port_name": "New Orleans / Mississippi", "country": "EUA"},
    {"port_id": "USNYC", "port_name": "New York", "country": "EUA"},
    {"port_id": "USSEA", "port_name": "Seattle / Tacoma", "country": "EUA"},
    {"port_id": "ZACPT", "port_name": "Cape Town", "country": "África do Sul"},
]

mcp = MCPServer(
    "gp5-maritime",
    title="GP5 Maritime — M2M Physical Operations Intelligence",
    description=(
        "GP5 Maritime is a Machine-to-Machine (M2M) product that delivers verified "
        "physical operational intelligence for seaports and multimodal logistics corridors. "
        "It combines real-time vessel line-up data (AIS, port authority scraping) with "
        "land-side railway queue observations (Rumo Logística) to produce two categories of tools:\n\n"
        "OBSERVATION TOOLS (available to all clients):\n"
        "  get_port_state — Current multimodal physical state of a port (vessels + wagons)\n"
        "  get_physical_events — Temporal ChangePacket (physical-event.v1) with source provenance\n\n"
        "DECISION TOOLS (premium access):\n"
        "  evaluate_charter_risk — Demurrage exposure in USD under explicit stated assumptions\n"
        "  evaluate_routing_alternatives — Comparative condition analysis between two ports\n\n"
        "Data sources: APPA Paranaguá, Porto de Santos, SILOG PortosRio, Rumo Logística, ShipInfo AIS.\n"
        "All responses carry schema_version, evidence provenance, and explicit uncertainty declarations."
    ),
    instructions=(
        "You are connected to the GP5 Maritime M2M Product Runtime. "
        "This product operates in two layers:\n\n"
        "OBSERVATION LAYER:\n"
        "Call get_port_state or get_physical_events FIRST when you need to understand the "
        "current physical condition of a port. These tools return verified observations with "
        "explicit source provenance (e.g. 'appa', 'rumo_logistica'). "
        "Treat their output as Ground Truth about the physical world.\n\n"
        "DECISION LAYER:\n"
        "Call evaluate_charter_risk when a user is evaluating whether to sign a charter party, "
        "fix a vessel to a port, or quantify demurrage exposure. "
        "Call evaluate_routing_alternatives when a user is choosing between two ports for cargo routing. "
        "These tools build on top of the Observation Layer and return DecisionResult (decision-result.v1) "
        "with explicit assumptions, physical basis, and uncertainty declarations.\n\n"
        "CRITICAL RULES:\n"
        "1. Always report the 'sources' field to the user — it identifies the real-world data origin.\n"
        "2. Always surface the 'uncertainties' list when presenting a DecisionResult — do not omit it.\n"
        "3. Never claim a 'recommendation' from evaluate_routing_alternatives — it returns comparative "
        "evidence, not a prescriptive routing mandate.\n"
        "4. For ports without live coverage, return INSUFFICIENT_OBSERVATION and say so explicitly."
    ),
    version="1.0.0",
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


async def _fetch_verified_queue(port_id: str) -> dict[str, Any]:
    url = f"{_base_url()}/v1/verified-queue"
    async with _client() as client:
        resp = await client.get(
            url, params={"port_id": port_id}, headers=_headers()
        )
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def get_verified_queue(port_id: str) -> dict[str, Any]:
    """Return the verified multimodal physical queue for a port, combining sea-side vessels and land-side logistics (trains/wagons). Only works for live ports. Returns INSUFFICIENT_OBSERVATION for others.

    Args:
        port_id: UN/LOCODE of the port, e.g. "BRPNG" (Paranaguá) or "BRSSZ" (Santos).
    """
    return await _fetch_verified_queue(port_id.strip().upper())


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
    """List the 35 ports & global chokepoints in the oracle (id, name, country)."""
    return SUPPORTED_PORTS


# ─── GP5 M2M OBSERVATION TOOLS ────────────────────────────────────────────────

@mcp.tool()
async def get_port_state(port_id: str) -> dict[str, Any]:
    """[OBSERVATION TOOL] Return the current verified multimodal physical state of a port.

    Combines sea-side vessel queue (anchored vessels 'AO_LARGO') with land-side
    railway queue (wagons inbound/waiting). Returns sources for full provenance.

    Args:
        port_id: UN/LOCODE e.g. "BRPNG" (Paranaguá), "BRSSZ" (Santos).
    """
    url = f"{_base_url()}/v1/verified-queue"
    async with _client() as client:
        resp = await client.get(url, params={"port_id": port_id.strip().upper()}, headers=_headers())
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def get_physical_events(port_id: str) -> dict[str, Any]:
    """[OBSERVATION TOOL] Return temporal physical events for a port as a ChangePacket (physical-event.v1).

    Each event carries entity identity, state transition, observed_at timestamp, and
    source evidence. Use this tool to understand WHAT changed and WHEN.

    Args:
        port_id: UN/LOCODE e.g. "BRPNG" (Paranaguá), "BRSSZ" (Santos).
    """
    url = f"{_base_url()}/v1/gp5/physical-events"
    async with _client() as client:
        resp = await client.get(url, params={"port_id": port_id.strip().upper()}, headers=_headers())
        resp.raise_for_status()
        return resp.json()


# ─── GP5 M2M PROVISIONING TOOLS ────────────────────────────────────────────────

@mcp.tool()
async def request_m2m_key(agent_name: str, organization: str, contact_email: str = "agent@m2m.local") -> dict[str, Any]:
    """[M2M SELF-SERVE TOOL] Request an instant 7-day trial M2M API Key.

    Use this tool if a Decision Tool returns an Access Denied / 403 error.
    Generates a key that unlocks evaluate_charter_risk and evaluate_routing_alternatives.

    Args:
        agent_name: Name or ID of your AI agent or client.
        organization: Organization or trading desk name.
        contact_email: Contact email.
    """
    url = f"{_base_url()}/v1/m2m/request-key"
    payload = {"name": agent_name, "email": contact_email, "organization": organization}
    async with _client() as client:
        resp = await client.post(url, json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()


# ─── GP5 M2M DECISION TOOLS ───────────────────────────────────────────────────

@mcp.tool()
async def evaluate_charter_risk(
    port_id: str,
    commodity: str,
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

    IMPORTANT: Always surface the 'uncertainties' list to the user. This tool produces an
    *estimate under stated assumptions*, not a contractual value.

    Args:
        port_id: UN/LOCODE e.g. "BRPNG" (Paranaguá).
        commodity: Commodity type e.g. "SOJA", "MILHO", "CONTEINERES".
        demurrage_rate_usd_day: Demurrage rate in USD/day (default: 32000).
        expected_laytime_days: Agreed laytime in days (default: 2.0).
    """
    url = f"{_base_url()}/v1/gp5/charter-risk"
    params = {
        "port_id": port_id.strip().upper(),
        "commodity": commodity.strip().upper(),
        "demurrage_rate_usd_day": demurrage_rate_usd_day,
        "expected_laytime_days": expected_laytime_days
    }
    async with _client() as client:
        resp = await client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def evaluate_routing_alternatives(port_a: str, port_b: str, commodity: str) -> dict[str, Any]:
    """[DECISION TOOL] Evaluate and compare physical logistics conditions between two ports.

    Returns a DecisionResult (decision-result.v1) with:
    - comparison.delta_delay_days: estimated delay difference
    - comparison.lower_delay_port: port with lower observed congestion
    - exposure: per-port financial exposure estimates
    - physical_basis: verified physical observations for each port
    - uncertainties: explicit limitations of this comparison

    IMPORTANT: This tool returns COMPARATIVE EVIDENCE, not a routing mandate.
    Do not tell the user to divert cargo based solely on this output.

    Args:
        port_a: First port UN/LOCODE e.g. "BRPNG".
        port_b: Second port UN/LOCODE e.g. "BRSSZ".
        commodity: Commodity type e.g. "SOJA".
    """
    url = f"{_base_url()}/v1/gp5/routing-eval"
    params = {
        "port_a": port_a.strip().upper(),
        "port_b": port_b.strip().upper(),
        "commodity": commodity.strip().upper()
    }
    async with _client() as client:
        resp = await client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def evaluate_corridor_risk(
    origin_port: str,
    destination_port: str,
    commodity: str = "SOJA",
    vessel_capacity_tons: float = 60000.0
) -> dict[str, Any]:
    """[DECISION TOOL] Evaluate full global trade corridor risk (e.g. Chicago/Brazil -> China/Europe).

    Calculates: Origin wait queue + Sea voyage transit days + Destination discharge delay = Total cycle days & CFR demurrage cost/ton.

    Args:
        origin_port: Export port UN/LOCODE e.g. "BRPNG" (Paranaguá), "BRSSZ" (Santos).
        destination_port: Import port UN/LOCODE e.g. "CNTAO" (Qingdao), "CNNGB" (Ningbo), "NLRTM" (Rotterdam).
        commodity: Commodity type e.g. "SOJA", "MILHO".
        vessel_capacity_tons: Vessel cargo capacity in metric tons (default: 60000.0).
    """
    url = f"{_base_url()}/v1/gp5/corridor-risk"
    params = {
        "origin_port": origin_port.strip().upper(),
        "destination_port": destination_port.strip().upper(),
        "commodity": commodity.strip().upper(),
        "vessel_capacity_tons": vessel_capacity_tons
    }
    async with _client() as client:
        resp = await client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
