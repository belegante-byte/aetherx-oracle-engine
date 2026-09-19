# Aether-X Port Congestion Oracle

[![PyPI version](https://img.shields.io/pypi/v/aetherx-oracle?color=blue)](https://pypi.org/project/aetherx-oracle/)
[![PyPI downloads](https://img.shields.io/pypi/dm/aetherx-oracle)](https://pypi.org/project/aetherx-oracle/)
[![Python versions](https://img.shields.io/pypi/pyversions/aetherx-oracle)](https://pypi.org/project/aetherx-oracle/)
[![MCP Registry](https://img.shields.io/badge/MCP%20Registry-active-brightgreen)](https://registry.modelcontextprotocol.io)
[![Status](https://img.shields.io/badge/status-online-blue)](https://aether-x-oracle-production.up.railway.app/)

**Port congestion signals for developers, AI agents, logistics systems and quantitative workflows.**

> **DATA INTEGRITY NOTICE**: **Brazilian ports feed LIVE operational line-ups.** Santos (BRSSZ) and Paranaguá (BRPNG) are refreshed from APPA Paranaguá, the Porto de Santos operations panel and Lachmann schedules (`data_source="live:appa+santos+lachmann"`); Rio de Janeiro (BRRIO) from SILOG PortosRio (`data_source="live:portosrio_silog"`), refreshed periodically in production. The remaining 14 ports serve a **reference seed** (`data_source="static_reference_seed"`). Every API/MCP response includes `data_source` and `as_of`. The 24/48/72h trend is a synthetic projection (`data_source="synthetic_projection"`), not a live forecast. Numbers from the seed are reference baselines, NOT real-time field data.

Aether-X exposes congestion scores, ETA delay estimates, freight volatility indices and modeled daily demurrage exposure for 17 global ports — delivered through a **REST API**, a **typed Python SDK** and a **remote MCP server** for AI agents.

Free tier available. No credit card required.

---

## Quick start (Python) — under 3 minutes

```bash
pip install --upgrade aetherx-oracle
```

```python
from aetherx import OracleClient

client = OracleClient(api_key="YOUR_RAPIDAPI_KEY")

risk = client.get_port_risk("BRSSZ")

print(risk.port_name)                        # Santos
print(risk.congestion_score)                 # 0.78
print(risk.eta_delay_days)                   # 1.6
print(risk.estimated_daily_demurrage_usd)    # 63200 (USD/day)
```

Get a free API key on the **[RapidAPI listing](https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle)**.

### Compare many ports in one call

```python
portfolio = ["BRSSZ", "CNSHA", "NLRTM", "USLAX", "SGSIN"]
results = client.get_ports_risk(portfolio)
for r in sorted(results, key=lambda x: x.congestion_score, reverse=True):
    print(f"{r.port_id:<6} {r.congestion_score:.2f}  {r.estimated_daily_demurrage_usd:,}/day")
```

### 24/48/72h trend

```python
trend = client.get_port_trend("NLRTM")
print(trend.trend)                              # acelerando / estável / descongestionando
print(trend.projection["h48"].congestion_score)
```

### Async (parallel batch)

```bash
pip install "aetherx-oracle[async]"
```

```python
import asyncio
from aetherx import OracleClient

async def main():
    client = OracleClient(api_key="YOUR_RAPIDAPI_KEY")
    risks = await client.get_ports_risk_async(["BRSSZ", "CNSHA", "NLRTM", "USLAX"])
    for r in risks:
        print(r.port_id, r.congestion_score)

asyncio.run(main())
```

---

## MCP server (for AI agents)

Ask your agent directly:

> "What's the congestion risk at Santos?"

> "Compare Santos, Shanghai and Rotterdam."

> "Which of these ports has the highest modeled demurrage exposure?"

> "Show me the 72-hour congestion trend for Santos."

**Available tools:** `get_port_risk` · `get_ports_risk` · `get_port_trend`

### Remote (no install)

Add to your MCP client config:

```json
{
  "mcpServers": {
    "aetherx-oracle": {
      "type": "url",
      "url": "https://aether-x-oracle-production.up.railway.app/mcp"
    }
  }
}
```

### Local (stdio)

```json
{
  "mcpServers": {
    "aetherx-oracle": {
      "command": "uvx",
      "args": ["aetherx-mcp"]
    }
  }
}
```

Published in the **[Official MCP Registry](https://registry.modelcontextprotocol.io)** as `io.github.belegante-byte/aetherx-mcp`, available on [PyPI](https://pypi.org/project/aetherx-mcp/), [Glama](https://glama.ai/mcp/connectors/io.github.belegante-byte/aetherx-mcp) and [Smithery](https://smithery.ai/servers/belegante/aetherx-mcp).

---

## REST API

Base URL: `https://aether-x-oracle-production.up.railway.app`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/port-risk?port_id=BRSSZ` | Congestion score, ETA delay, waiting vessels, freight volatility and daily demurrage for one port |
| `GET` | `/v1/ports-risk?port_ids=...` | Same signal for up to 20 ports in a single call |
| `GET` | `/v1/port-trend?port_id=BRSSZ` | 24h / 48h / 72h congestion projection with trend label |
| `GET` | `/mcp` | Remote MCP endpoint (Streamable HTTP) |

**Example response** (`/v1/port-risk?port_id=BRSSZ`):

```json
{
  "port_id": "BRSSZ",
  "port_name": "Santos",
  "country": "Brasil",
  "congestion_score": 0.78,
  "eta_delay_days": 1.6,
  "waiting_vessels": 12,
  "freight_volatility_index": 0.42,
  "estimated_daily_demurrage_usd": 63200,
  "updated_at": "2026-09-17 15:46:53"
}
```

Interactive docs: [Swagger UI](https://aether-x-oracle-production.up.railway.app/docs) · [OpenAPI](https://aether-x-oracle-production.up.railway.app/openapi.json)

---

## Supported ports

`BRSSZ` `BRRIO` `CNSHA` `CNNGB` `CNTAO` `SGSIN` `NLRTM` `USLAX` `USNYC` `DEHAM` `MPTNG` `AEDXB` `KRPUS` `GBLGP` `ZACPT` `MXZLO`

Unknown ports fall back to a global statistical estimate (`country="Global"`).

---

## Pricing & free tier

**Free Developer Tier — $0.00** for development, prototyping, CI and evaluation. **No credit card required.**

| Plan | Price | Best for |
|------|-------|----------|
| Free Developer Tier | **$0.00** | Evaluation, prototypes, CI — up to the plan's monthly request limit |
| Pay-as-you-go | **$0.02 / query** | Production traffic beyond the free tier |

Grab a key on the **[RapidAPI listing](https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle)**.

---

## Resources

- [RapidAPI marketplace](https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle)
- [PyPI — aetherx-oracle (SDK)](https://pypi.org/project/aetherx-oracle/)
- [PyPI — aetherx-mcp (MCP server)](https://pypi.org/project/aetherx-mcp/)
- [Official MCP Registry](https://registry.modelcontextprotocol.io) — `io.github.belegante-byte/aetherx-mcp`
- [Glama connector](https://glama.ai/mcp/connectors/io.github.belegante-byte/aetherx-mcp)
- [Smithery gateway](https://smithery.ai/servers/belegante/aetherx-mcp)
- [llms.txt](https://aether-x-oracle-production.up.railway.app/llms.txt)
- [Terms of Service](https://aether-x-oracle-production.up.railway.app/terms)

## Writing

- [Predicting Global Port Congestion in Real-Time with Python, DuckDB and MCP](https://dev.to/giovanni_belegante_2b04c5/predicting-global-port-congestion-in-real-time-with-python-duckdb-and-mcp-1ahm) — DEV Community

## Repository layout

```
src/            FastAPI app (REST + remote MCP), reference engine, data
sdk_python/     aetherx-oracle Python SDK (PyPI)
mcp_server/     aetherx-mcp MCP server for AI agents (PyPI)
docs/           OpenAPI specs, llms.txt, Terms of Service
tests/          pytest suite
```

## Development & deployment

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/engine/init_prod_db.py   # seed the DuckDB oracle
uvicorn src.api.main:app --reload --port 8000
python -m pytest tests/ sdk_python/tests/ -v
```

Deploys to [Railway](https://railway.com) via `railway.json`; the DuckDB oracle is seeded idempotently at boot.

---

## Terms & license

Signals are provided **"AS IS"**, without warranty, and **do not constitute investment advice**. See [Terms of Service](https://aether-x-oracle-production.up.railway.app/terms).

The **Python SDK** is **MIT** licensed. The **API, reference engine and data pipeline** are proprietary — hosted usage is governed by the Terms.