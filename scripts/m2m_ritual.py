"""Snapshot diário do ritual M2M — leitura do KPI com exclusão de tráfego operacional.

Carrega `GET /internal/metrics` usando um User-Agent próprio
(`belegante-aetherx-operational/0.1`). Esse header identifica tráfego
operacional/teste interno e o produto já o exclui dos contadores de aquisição
(tokem `_SELF_TOKENS`). Eventos históricos (D0/D1) NÃO são reclassificados.

Usage:
    python scripts/m2m_ritual.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.getenv(
    "AETHERX_BASE_URL", "https://aether-x-oracle-production.up.railway.app"
)
SECRET = None
_env = ROOT / "config" / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        if line.startswith("RAPIDAPI_PROXY_SECRET="):
            SECRET = line.split("=", 1)[1].strip()

UA = "belegante-aetherx-operational/0.1 (ritual m2m; excluded_from_acquisition)"

# Canais que o funil M2M considera aquisição (bots/crawlers ficam de fora).
FUNNEL_CHANNELS = ("mcp", "rest", "discovery", "seo")


def fetch_snapshot() -> dict:
    if not SECRET:
        sys.exit("RAPIDAPI_PROXY_SECRET não encontrado em config/.env")
    req = urllib.request.Request(
        f"{BASE_URL}/internal/metrics",
        headers={
            "X-RapidAPI-Proxy-Secret": SECRET,
            "User-Agent": UA,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main() -> None:
    snap = fetch_snapshot()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== Ritual M2M — {now} ===")
    print(f"uptime: {snap['uptime_seconds']}s")

    uniq = snap.get("unique_machines", {})
    repeat = snap.get("repeat_machines", {})
    rate = snap.get("second_call_rate", {})

    print("\nCanal | first(uniq) | second(repeat) | 2nd-call-rate | bots")
    for ch in ("mcp", "rest", "discovery", "seo"):
        f = uniq.get(ch, 0)
        s = repeat.get(ch, 0)
        r = rate.get(ch)
        bots = snap["total"].get("bot", 0)
        print(
            f"{ch:<11} | {f:^11} | {s:^14} | "
            f"{('%.2f' % r).rjust(14) if r is not None else '—'.rjust(14)} | {bots}"
        )
    bots_uniq = uniq.get("bot", 0)
    print(f"\nBots (liveness/crawlers, excluídos do funil): {snap.get('bot_calls', 0)} calls / {bots_uniq} máquinas")
    print("Canal | total calls")
    for ch, n in sorted(snap.get("total", {}).items(), key=lambda x: -x[1]):
        print(f"  {ch:<11} | {n}")
    print("\nTop paths:")
    for path, n in snap.get("top_paths", []):
        print(f"  {n:>4}  {path}")

    first_total = sum(uniq.get(c, 0) for c in FUNNEL_CHANNELS)
    second_total = sum(repeat.get(c, 0) for c in FUNNEL_CHANNELS)
    print("\n== Funil acumulado (aquisição; bots excluídos) ==")
    print(f"first:  {first_total}")
    print(f"second: {second_total}")
    print(
        "External Second Call Rate (acumulado): "
        f"{second_total / first_total:.2f}" if first_total
        else "External Second Call Rate: — (sem first calls)"
    )


if __name__ == "__main__":
    main()