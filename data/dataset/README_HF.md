---
license: cc-by-4.0
language:
  - en
pretty_name: Aether-X Global Port Congestion Snapshot
size_categories:
  - n<1K
tags:
  - logistics
  - supply-chain
  - maritime
  - ports
  - congestion
  - finance
  - tabular
configs:
  - config_name: default
    data_files:
      - split: train
        path: port_metrics.csv
---

# Aether-X Global Port Congestion Snapshot

Point-in-time snapshot of the **Aether-X Port Congestion Oracle** — predictive
congestion, ETA delay and freight-volatility signals for 16 of the world's
largest ports.

This static CSV is a **frozen snapshot** for research, backtesting and
dashboards. The live, continuously-updated signal is available through the
REST API and the Python SDK.

## Files

- `port_metrics.csv` — one row per port.

## Schema

| Column | Type | Description |
|---|---|---|
| `port_id` | string | UN/LOCODE (e.g. `BRSSZ`) |
| `port_name` | string | Port name |
| `country` | string | Country |
| `congestion_score` | float | Congestion risk, normalized 0.0–1.0 |
| `eta_delay_days` | float | Expected ETA delay in days |
| `waiting_vessels` | int | Vessels anchored or queued |
| `freight_volatility_index` | float | Freight pricing pressure indicator |
| `updated_at` | timestamp (UTC) | Snapshot timestamp |

## Usage

```python
import pandas as pd

df = pd.read_csv(
    "hf://datasets/Aether-x/aetherx-port-congestion-metrics/port_metrics.csv"
)

# Highest congestion risk first
print(df.sort_values("congestion_score", ascending=False).head())
```

## Ports

AEDXB, BRRIO, BRSSZ, CNNGB, CNSHA, CNTAO, DEHAM, GBLGP, KRPUS, MPTNG, MXZLO, NLRTM,
SGSIN, USLAX, USNYC, ZACPT

## Live data

- API: https://aether-x-oracle-production.up.railway.app/v1/port-risk?port_id=BRSSZ
- Python SDK: `pip install aetherx-oracle`
- MCP server (AI agents): `uvx aetherx-mcp`
- Source (MIT): https://github.com/belegante-byte/aetherx-oracle

## License

CC BY 4.0 for this snapshot. The signals are provided "AS IS", without
warranty, and **do not constitute investment advice**. See the
[Terms of Service](https://aether-x-oracle-production.up.railway.app/terms).
