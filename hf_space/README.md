---
title: Aether-X Port Congestion Oracle
emoji: 🚢
colorFrom: indigo
colorTo: blue
sdk: static
pinned: false
short_description: Port congestion, ETA delay and demurrage for 16 ports.
---

# Aether-X Port Congestion Oracle

Live dashboard of port congestion, ETA delay, waiting vessels and modeled demurrage for 16 global ports.

The [public feed](https://aetherx.aether-grid.io/public/ports) powers this page (with a bundled snapshot fallback). The full signal — congestion trend 24/48/72h, batch scans and portfolio calls — is available via:

- REST API on [RapidAPI](https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle) (free tier $0.00)
- Python SDK: `pip install aetherx-oracle`
- MCP server for AI agents: `uvx aetherx-mcp` or remote endpoint

Signals are provided "AS IS" and do not constitute investment advice.