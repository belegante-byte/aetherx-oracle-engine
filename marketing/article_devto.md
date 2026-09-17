# Predicting Global Port Congestion in Real-Time with Python, DuckDB and MCP

> How to turn public port telemetry into machine-readable congestion signals your trading, logistics or **AI agent** stack can consume — over REST (RapidAPI), a typed Python SDK, or the Model Context Protocol.

Every global supply chain bottleneck starts the same way: ships stack up outside a port, berth windows slip, and freight rates reprice before most operators notice. By the time the delay shows up in a spreadsheet, the market has already moved.

This article shows how to programmatically track that risk with the **Aether-X Port Congestion Oracle** — an API that scores congestion, ETA delay and freight volatility for the world's largest ports — and how to wire it into both classic Python pipelines and LLM agents via MCP.

## The signal

Aether-X exposes a single endpoint:

```
GET /v1/port-risk?port_id=BRSSZ
```

The response is a compact, machine-readable payload:

```json
{
  "port_id": "BRSSZ",
  "port_name": "Santos",
  "country": "Brasil",
  "congestion_score": 0.78,
  "eta_delay_days": 1.6,
  "waiting_vessels": 12,
  "freight_volatility_index": 0.42,
  "updated_at": "2026-09-17 21:43:45"
}
```

- `congestion_score` — normalized 0.0–1.0 risk of operational congestion
- `eta_delay_days` — expected delay applied to incoming vessels
- `waiting_vessels` — ships anchored or queued
- `freight_volatility_index` — pressure indicator for freight pricing

The same contract is available three ways, so you can pick the one that matches your stack — or mix all three:

| Consumer | Transport | Install |
|---|---|---|
| Classic scripts & bots | REST / OpenAPI via RapidAPI | nothing to install |
| Python services | `aetherx-oracle` typed SDK | `pip install aetherx-oracle` |
| LLM agents (Claude, Cursor, custom) | MCP (stdio **or** remote Streamable HTTP) | `uvx aetherx-mcp` / a URL |

## 1. REST + OpenAPI, monetized through RapidAPI

The production service runs on Railway and is fully described by an OpenAPI 3 spec, so you can call it with plain `curl` or generate a client in any language:

```bash
curl "https://aether-x-oracle-production.up.railway.app/v1/port-risk?port_id=BRSSZ"
```

- OpenAPI 3.0 (RapidAPI-compatible): `https://aether-x-oracle-production.up.railway.app/openapi.rapidapi.json`
- OpenAPI 3.1 (native FastAPI): `https://aether-x-oracle-production.up.railway.app/openapi.json`
- Interactive docs: `https://aether-x-oracle-production.up.railway.app/docs`

For metered, pay-as-you-go access the same endpoint is published on the **RapidAPI Hub**, which handles API keys, quotas and billing. You only change the base URL and add two headers:

```bash
curl --request GET \
  --url 'https://aether-x-port-congestion-oracle.p.rapidapi.com/v1/port-risk?port_id=BRSSZ' \
  --header 'X-RapidAPI-Key: SUA_RAPIDAPI_KEY' \
  --header 'X-RapidAPI-Host: aether-x-port-congestion-oracle.p.rapidapi.com'
```

Pricing is intentionally boring: a **free tier** for evaluation and adoption, then **$0.02 per query** on pay-as-you-go. For a signal that can be polled on a tight loop, cheap-per-call is the whole point.

## 2. The typed Python SDK

```bash
pip install --upgrade aetherx-oracle   # v0.3.1, MIT, Python 3.8+
```

```python
from aetherx import OracleClient

client = OracleClient(api_key="SUA_RAPIDAPI_KEY")
risk = client.get_port_risk("BRSSZ")

print(f"{risk.port_name}: score={risk.congestion_score}, delay={risk.eta_delay_days}d")
```

The client returns a typed `PortRisk` object, so you get attribute access and validation instead of raw dicts. The `host` already defaults to the RapidAPI gateway, so the key is all you need.

### Monitoring a portfolio of ports in parallel

Trading bots and logistics control towers rarely watch a single port. With the async extra you can fan out across dozens of ports concurrently:

```bash
pip install "aetherx-oracle[async]"
```

```python
import asyncio
from aetherx import OracleClient

PORTS = ["BRSSZ", "CNSHA", "CNNGB", "SGSIN", "NLRTM", "USLAX", "DEHAM", "KRPUS"]

async def main():
    client = OracleClient(api_key="SUA_RAPIDAPI_KEY")
    risks = await client.get_ports_risk_async(PORTS)

    for r in sorted(risks, key=lambda r: r.congestion_score, reverse=True):
        flag = "HIGH" if r.congestion_score >= 0.7 else "ok"
        print(f"{r.port_id:<6} {r.congestion_score:.2f}  {r.eta_delay_days:.1f}d  [{flag}]")

asyncio.run(main())
```

Because calls run concurrently, the whole portfolio resolves in roughly the time of the slowest single request.

### A simple congestion alert rule

```python
def alert_level(risk) -> str:
    if risk.congestion_score >= 0.7 and risk.freight_volatility_index >= 0.35:
        return "REPRICE_RISK"
    if risk.eta_delay_days >= 1.5:
        return "SLA_RISK"
    return "NOMINAL"
```

- **REPRICE_RISK** — congestion plus volatility: freight and commodity spreads likely to move
- **SLA_RISK** — delays threaten delivery commitments
- **NOMINAL** — no action

## 3. MCP: giving agents the same signal

The most interesting shift of the last year is that the *consumer* is increasingly not a script you wrote, but an LLM agent that decides on its own which tools to call. Chatting "which of my ports is the riskiest this week?" only works if the agent has a real, deterministic data source behind it.

**MCP (Model Context Protocol)** is that interface. Aether-X ships an MCP server, `aetherx-mcp`, that exposes three tools:

| Tool | Purpose |
|---|---|
| `get_port_risk` | congestion signal for a single port (`BRSSZ`, `CNSHA`, …) |
| `get_ports_risk` | scan a portfolio of ports in parallel |
| `list_supported_ports` | list the 15 pre-seeded ports (id, name, country) |

### Option A — stdio (local, zero infrastructure)

The server is published on PyPI, so there is nothing to clone or build:

```bash
uvx aetherx-mcp          # or: pip install aetherx-mcp && aetherx-mcp
```

Register it in Claude Desktop, Cursor or any MCP client:

```json
{
  "mcpServers": {
    "aetherx": {
      "command": "uvx",
      "args": ["aetherx-mcp"],
      "env": { "RAPIDAPI_KEY": "SUA_RAPIDAPI_KEY" }
    }
  }
}
```

`RAPIDAPI_KEY` is **optional**: without it the server calls the public API directly (free tier); with it, requests are routed through the RapidAPI gateway so usage is metered and billed exactly like any other REST call.

### Option B — remote Streamable HTTP (nothing to install)

If you'd rather not run a process locally, the same tool surface is served remotely at:

```
https://aether-x-oracle-production.up.railway.app/mcp
```

```json
{
  "mcpServers": {
    "aetherx": {
      "url": "https://aether-x-oracle-production.up.railway.app/mcp"
    }
  }
}
```

The endpoint speaks MCP **Streamable HTTP**, and the risk calculation happens in-process — no self-HTTP hop, no extra latency, no duplicated logic.

### Option C — Smithery

The server is also listed on the **Smithery** registry, which can host and proxy it for you:

- Server page: https://smithery.ai/servers/belegante/aetherx-mcp
- Registry name: `belegante/aetherx-mcp`
- Also indexed in the official MCP Registry as `io.github.belegante-byte/aetherx-mcp`

### Driving it from Python

Any MCP client works. Here is the raw Streamable HTTP flow with the official Python SDK — this is the exact code that runs against production:

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    url = "https://aether-x-oracle-production.up.railway.app/mcp"
    async with streamable_http_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_ports_risk", {"port_ids": ["BRSSZ", "CNSHA"]}
            )
            for block in result.content:
                print(block.text)          # one JSON block per port
            print(result.structured_content)  # same data, machine-typed

asyncio.run(main())
```

Which prints the real engine output:

```
{"port_id": "BRSSZ", "port_name": "Santos", "country": "Brasil",
 "congestion_score": 0.78, "eta_delay_days": 1.6, "waiting_vessels": 12,
 "freight_volatility_index": 0.42, "updated_at": "..."}
{"port_id": "CNSHA", "port_name": "Shanghai", "country": "China",
 "congestion_score": 0.72, "eta_delay_days": 1.5, "waiting_vessels": 18,
 "freight_volatility_index": 0.38, "updated_at": "..."}
```

That is the whole point of exposing a data product over MCP: the agent gets numbers it can cite, instead of guessing.

## Unknown ports degrade gracefully

Request a port that isn't in the dataset and you still get a valid payload, backed by a global statistical estimate (`country="Global"`). Your pipeline — or your agent — never crashes on an unexpected UN/LOCODE, it just gets a conservative baseline.

## How it works under the hood

Aether-X is intentionally a small, fast stack — no heavyweight orchestrator, no distributed database. The whole signal pipeline fits in a handful of components:

```
  public port data          ingestion               storage              delivery
  ────────────────   ─────────────────────   ─────────────────   ─────────────────────────
   line-ups,         UPSERT by IMO           DuckDB              FastAPI
   berth/anchorage   (idempotent,           ┌───────────────┐   ┌────────────────────┐
   telemetry    ───▶  re-runs never    ───▶ │ port_metrics  │──▶ │ GET /v1/port-risk  │──▶ REST / SDK
                     duplicate)             └───────────────┘   │ POST /mcp          │──▶ MCP agents
                                                  ▲             └────────────────────┘
                                                  └── seeded at boot ──┘   (Railway)
```

- **Ingestion** — public line-ups are normalized and **upserted by IMO**, so re-running a collector never duplicates a vessel. This is what keeps the dataset trustworthy over time.
- **DuckDB** — a columnar analytical engine holding the `port_metrics` table. It answers the scoring query in single-digit milliseconds with zero external infrastructure, which is why the API stays cheap to serve.
- **FastAPI** — exposes both the REST surface and the MCP endpoint, validating every response through a Pydantic model so clients receive a stable, typed contract.
- **Railway** — deploys the service and seeds the oracle idempotently at boot, so a fresh instance is never empty.

The MCP tools call the **same** in-process function the REST route calls. One engine, two protocols: no duplicated logic, and no risk of an agent and a bot seeing different numbers.

## Built for machine discovery, not just humans

Alongside the OpenAPI spec, the service ships the small files that agents and crawlers look for:

- `GET /llms.txt` — a plain-text summary of what the API is and how to call it
- `GET /.well-known/ai-plugin.json` — plugin manifest for agent platforms
- `GET /openapi.rapidapi.json` — OpenAPI 3.0 spec for API marketplaces

## Get started

```bash
pip install --upgrade aetherx-oracle    # typed SDK
uvx aetherx-mcp                         # MCP server (stdio)
```

- PyPI (SDK): https://pypi.org/project/aetherx-oracle/
- PyPI (MCP): https://pypi.org/project/aetherx-mcp/
- GitHub (MIT SDK): https://github.com/belegante-byte/aetherx-oracle
- GitHub (MIT MCP server): https://github.com/belegante-byte/aetherx-mcp
- Live API: https://aether-x-oracle-production.up.railway.app/v1/port-risk?port_id=BRSSZ
- Remote MCP: https://aether-x-oracle-production.up.railway.app/mcp
- Smithery: https://smithery.ai/servers/belegante/aetherx-mcp

The signals are provided "AS IS" and do not constitute investment advice. See the Terms of Service.

*If you build something with Aether-X — a risk dashboard, a quant signal, an MCP-powered agent — drop a comment. I'd love to see it.*
