# aetherx-mcp — Port Congestion, Maritime Logistics & Supply Chain MCP Server

<!-- mcp-name: io.github.belegante-byte/aetherx-mcp -->

**Aether-X** is an MCP server for the [Aether-X Port Congestion Oracle](https://aetherx.aether-grid.io) that gives any MCP-compatible agent (Claude Desktop, Cursor, VS Code, custom LLM agents) **port congestion, maritime delay, vessel queue and supply-chain risk** signals for global trade — answered in plain language for simple queries ("is Rotterdam delayed?") and in USD exposure for decision-grade workflows (demurrage, charter risk, fiscal arbitrage across routes).

**Keywords:** maritime, shipping, vessels, ports, port congestion, demurrage, freight, logistics, supply chain, ETA delay, vessel queue, chokepoints, Suez, Panama, trade lanes, cargo, quantitative finance.

> **DATA INTEGRITY NOTICE**: Brazilian ports (BRSSZ Santos, BRPNG Paranaguá, BRRIO Rio de Janeiro) feed **live** operational line-ups (`data_source="live:appa+santos+lachmann"`); Niterói (BRNIT) and Itaguaí (BRITG) together with Rio de Janeiro feed **live** line-up from SILOG PortosRio (`data_source="live:portosrio_silog"`). The remaining ports serve a **static reference seed** (`data_source="static_reference_seed"`). Every tool result includes `data_source` and `as_of`. The 24/48/72h trend is a synthetic projection, not a live forecast. Seed values are NOT real-time field data.

## Install

```bash
pip install aetherx-mcp
# or run without installing (recommended for MCP clients):
uvx aetherx-mcp
```

## Configure your MCP client

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "aetherx-oracle": {
      "command": "uvx",
      "args": ["aetherx-mcp"],
      "env": { "RAPIDAPI_KEY": "SUA_RAPIDAPI_KEY" }
    }
  }
}
```

### Cursor (`~/.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "aetherx-oracle": {
      "command": "uvx",
      "args": ["aetherx-mcp"],
      "env": { "RAPIDAPI_KEY": "SUA_RAPIDAPI_KEY" }
    }
  }
}
```

## Tools

| Tool | Arguments | Returns |
|------|-----------|---------|
| `get_port_operations_status` | `port_id` (UN/LOCODE) | **Plain-language status (NORMAL / CONGESTED)**, delay, waiting vessels, source provenance + optional decision-layer upsell — free observation |
| `get_port_risk` | `port_id` (UN/LOCODE) | Congestion score, ETA delay, waiting vessels, freight volatility, daily demurrage estimate |
| `get_ports_risk` | `port_ids` (list) | Same, for a whole portfolio, fetched in parallel |
| `get_port_trend` | `port_id` (UN/LOCODE) | 24h / 48h / 72h congestion projection + trend label (acelerando / estável / descongestionando) |
| `list_supported_ports` | — | The 35 ports & chokepoints (id, name, country) |

Every response is a typed payload:

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

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `RAPIDAPI_KEY` | — | When set, requests are routed through the RapidAPI gateway (metered billing) |
| `RAPIDAPI_HOST` | `aether-x-port-congestion-oracle.p.rapidapi.com` | RapidAPI host |
| `AETHERX_BASE_URL` | `https://aetherx.aether-grid.io` | Direct API base URL |

Without `RAPIDAPI_KEY`, the server calls the public production API directly.

## Example agent prompts

- *"Is the port of Santos delayed right now?"* (→ `get_port_operations_status`)
- *"Where is my cargo stuck? What's the waiting time at Paranaguá?"* (→ `get_port_operations_status`)
- *"What's the congestion risk at Rotterdam over the next 3 days?"* (→ `get_port_trend`, `forecast_vessel_queue_delays`)
- *"Rank these ports by congestion: BRSSZ, CNSHA, NLRTM, USLAX."* (→ `get_ports_risk`)
- *"How many ships are waiting at Shanghai?"* (→ `get_port_state`, `get_port_operations_status`)
- *"Which route minimizes demurrage + fiscal cost for my fertilizer cargo to MT?"* (→ `evaluate_fiscal_routing`, requires M2M key)

## License

MIT — see [LICENSE](LICENSE). The signals are provided "AS IS" and do not constitute investment advice. See the [Terms of Service](https://aetherx.aether-grid.io/terms).
