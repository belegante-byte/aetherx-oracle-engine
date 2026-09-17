# Predicting Port Congestion with Python + Aether-X

> How to turn public port telemetry into machine-readable congestion signals your trading or logistics stack can consume in one HTTP call.

Every global supply chain bottleneck starts the same way: ships stack up outside a port, berth windows slip, and freight rates reprice before most operators notice. By the time the delay shows up in a spreadsheet, the market has already moved.

This article shows how to programmatically track that risk with **Python** and the **Aether-X Port Congestion Oracle** — an API that scores congestion, ETA delay and freight volatility for the world's largest ports.

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
  "updated_at": "2026-09-17 15:46:53"
}
```

- `congestion_score` — normalized 0.0–1.0 risk of operational congestion
- `eta_delay_days` — expected delay applied to incoming vessels
- `waiting_vessels` — ships anchored or queued
- `freight_volatility_index` — pressure indicator for freight pricing

## Install

```bash
pip install aetherx-oracle
```

## First call (synchronous)

```python
from aetherx import OracleClient

client = OracleClient(api_key="SUA_RAPIDAPI_KEY")
risk = client.get_port_risk("BRSSZ")

print(f"{risk.port_name}: score={risk.congestion_score}, delay={risk.eta_delay_days}d")
```

The client returns a typed `PortRisk` object, so you get attribute access and validation instead of raw dicts.

## Monitoring a portfolio of ports in parallel

Trading bots and logistics control towers rarely watch a single port. With the async extra, you can fan out across dozens of ports concurrently:

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

    ranking = sorted(risks, key=lambda r: r.congestion_score, reverse=True)
    for r in ranking:
        flag = "HIGH" if r.congestion_score >= 0.7 else "ok"
        print(f"{r.port_id:<6} {r.congestion_score:.2f}  {r.eta_delay_days:.1f}d  [{flag}]")

asyncio.run(main())
```

Because calls run concurrently, the whole portfolio resolves in roughly the time of the slowest single request — ideal for tight monitoring loops.

## A simple congestion alert rule

Combining delay and volatility into a single trigger gives a practical early-warning rule:

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

## Unknown ports degrade gracefully

Request a port that isn't in the dataset and you still get a valid payload, backed by a global statistical estimate (`country="Global"`). That means your pipeline never crashes on an unexpected UN/LOCODE — it just returns a conservative baseline.

## How it works under the hood

Aether-X runs on a small, fast stack:

- **FastAPI** for the REST surface, with a validated Pydantic response model
- **DuckDB** as the analytical engine, holding the `port_metrics` table
- **Idempotent ingestion** — public line-ups are upserted by IMO, so re-runs never duplicate vessels
- **Railway** for zero-friction deployment, seeding the oracle at boot

## Get started

```bash
pip install aetherx-oracle
```

- PyPI: https://pypi.org/project/aetherx-oracle/
- Live API: https://aether-x-oracle-production.up.railway.app/v1/port-risk?port_id=BRSSZ

The signals are provided "AS IS" and do not constitute investment advice. See the Terms of Service.

*If you build something with Aether-X — a risk dashboard, a quant signal, an agent — drop a comment. I'd love to see it.*
