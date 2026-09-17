# Aether-X Port Congestion Oracle

[![PyPI version](https://img.shields.io/pypi/v/aetherx-oracle?color=blue)](https://pypi.org/project/aetherx-oracle/)
[![Python versions](https://img.shields.io/pypi/pyversions/aetherx-oracle)](https://pypi.org/project/aetherx-oracle/)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.0.3-green)](docs/openapi.rapidapi.json)
[![Status](https://img.shields.io/badge/status-live-brightgreen)](https://aether-x-oracle-production.up.railway.app/)
[![Made with DuckDB](https://img.shields.io/badge/DuckDB-analytical%20engine-yellow)](https://duckdb.org/)

**Algorithmic predictive port congestion signals for global trade, supply chain and quantitative finance.**

Aether-X turns public port telemetry and line-up data into machine-readable congestion scores, ETA delay estimates and freight volatility indices for the world's largest ports — delivered through a REST API, an MCP-style SDK and a Python client.

---

## Why

Global trade runs on a handful of chokepoints. When Santos, Shanghai or Rotterdam backs up, freight rates, delivery SLAs and commodity spreads move within hours. Aether-X compresses that signal into a single HTTP call so trading desks, logistics teams and autonomous agents can react before the market prices it in.

## Monorepo Structure

```
.
├── src/
│   ├── api/          # FastAPI application (REST endpoints)
│   ├── engine/       # Predictive model, DuckDB seeding, OpenAPI export
│   └── ingestion/    # Public port line-up collectors (UPSERT by IMO)
├── sdk_python/       # aetherx-oracle Python SDK (PyPI)
├── docs/             # OpenAPI specs + Terms of Service
├── marketing/        # Launch content (Dev.to, LinkedIn)
├── tests/            # pytest suite for the API
├── Procfile          # Railway start command
└── railway.json      # Railway deployment config
```

## Quickstart

```bash
pip install aetherx-oracle
```

### Synchronous

```python
from aetherx import OracleClient

client = OracleClient(api_key="SUA_RAPIDAPI_KEY")
risk = client.get_port_risk("BRSSZ")

print(risk.port_name)                 # Santos
print(risk.congestion_score)          # 0.78
print(risk.eta_delay_days)            # 1.6
print(risk.waiting_vessels)           # 12
print(risk.freight_volatility_index)  # 0.42
```

### Asynchronous (batch, in parallel)

```bash
pip install "aetherx-oracle[async]"
```

```python
import asyncio
from aetherx import OracleClient

async def main():
    client = OracleClient(api_key="SUA_RAPIDAPI_KEY")
    risks = await client.get_ports_risk_async(["BRSSZ", "CNSHA", "NLRTM", "USLAX"])
    for r in sorted(risks, key=lambda x: x.congestion_score, reverse=True):
        print(f"{r.port_id:<6} {r.congestion_score:.2f}")

asyncio.run(main())
```

## REST API

Base URL (production): `https://aether-x-oracle-production.up.railway.app`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/port-risk?port_id=BRSSZ` | Congestion score, ETA delay and freight volatility for a port |
| `GET` | `/terms` | Terms of Service |
| `GET` | `/openapi.json` | OpenAPI specification |

**Response**

```json
{
  "port_id": "BRSSZ",
  "port_name": "Santos",
  "country": "Brasil",
  "congestion_score": 0.78,
  "eta_delay_days": 1.6,
  "waiting_vessels": 12,
  "freight_volatility_index": 0.42,
  "updated_at": "2026-09-17 15:46:53"
}
```

## Supported Ports

`BRSSZ` `BRRIO` `CNSHA` `CNNGB` `SGSIN` `NLRTM` `USLAX` `USNYC` `DEHAM` `MPTNG` `AEDXB` `KRPUS` `GBLGP` `ZACPT` `MXZLO`

Unknown ports fall back to a global statistical estimate (`country="Global"`).

## Development

```bash
git clone <this-repo> && cd aetherx-oracle
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# seed the DuckDB oracle (15 global ports)
python src/engine/init_prod_db.py

# run the API
uvicorn src.api.main:app --reload --port 8000

# tests
python -m pytest tests/ sdk_python/tests/ -v
```

## Deployment

The API ships to [Railway](https://railway.com) via `railway.json` (Nixpacks + healthcheck on `/`). The DuckDB oracle is seeded idempotently at boot through the `Procfile` start command.

## Terms of Service

The signals are provided **"AS IS"**, without warranty, and **do not constitute investment advice**. See [`docs/TERMS_OF_SERVICE.md`](docs/TERMS_OF_SERVICE.md) or `/terms`.

## License

Proprietary — Machine-to-Machine Data Distribution. See the Terms of Service.
