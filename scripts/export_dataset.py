"""Export the Aether-X ``port_metrics`` oracle to a shareable dataset snapshot.

Produces a static CSV + dataset card for Kaggle / Hugging Face Datasets.
The snapshot is a point-in-time copy; the live, constantly-updated signal is
served by the API and the SDK.

Usage:
    python scripts/export_dataset.py
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DATABASE_PATH", str(ROOT / "data" / "oracle.duckdb"))
OUT_DIR = ROOT / "data" / "dataset"

COLUMNS = [
    "port_id",
    "port_name",
    "country",
    "congestion_score",
    "eta_delay_days",
    "waiting_vessels",
    "freight_volatility_index",
    "updated_at",
]

DATASET_CARD = """# Aether-X Global Port Congestion Snapshot

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
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        df = con.execute(
            f"SELECT {', '.join(COLUMNS)} FROM port_metrics ORDER BY port_id"
        ).fetchdf()
    finally:
        con.close()

    csv_path = OUT_DIR / "port_metrics.csv"
    df.to_csv(csv_path, index=False)

    card_path = OUT_DIR / "README.md"
    card_path.write_text(DATASET_CARD, encoding="utf-8")

    print(f"wrote {csv_path} ({len(df)} rows, {len(COLUMNS)} columns)")
    print(f"wrote {card_path}")


if __name__ == "__main__":
    main()
