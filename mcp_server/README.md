# aetherx-mcp

<!-- mcp-name: io.github.belegante-byte/aetherx-mcp -->

**MCP server for the [Aether-X Port Congestion Oracle](https://aether-x-oracle-production.up.railway.app)** — gives any MCP-compatible agent (Claude Desktop, Cursor, VS Code, custom LLM agents) **reference** port congestion signals for global trade and quantitative finance.

> **DATA INTEGRITY NOTICE**: Brazilian ports (BRSSZ Santos, BRPNG Paranaguá) feed **live** operational line-ups (`data_source="live:appa+santos+lachmann"`); Rio de Janeiro (BRRIO) feeds **live** line-up from SILOG PortosRio (`data_source="live:portosrio_silog"`). The remaining ports serve a **static reference seed** (`data_source="static_reference_seed"`). Every tool result includes `data_source` and `as_of`. The 24/48/72h trend is a synthetic projection, not a live forecast. Seed values are NOT real-time field data.

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
| `get_port_risk` | `port_id` (UN/LOCODE) | Congestion score, ETA delay, waiting vessels, freight volatility, daily demurrage estimate |
| `get_ports_risk` | `port_ids` (list) | Same, for a whole portfolio, fetched in parallel |
| `get_port_trend` | `port_id` (UN/LOCODE) | 24h / 48h / 72h congestion projection + trend label (acelerando / estável / descongestionando) |
| `list_supported_ports` | — | The 17 ports (id, name, country) |

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
| `AETHERX_BASE_URL` | `https://aether-x-oracle-production.up.railway.app` | Direct API base URL |

Without `RAPIDAPI_KEY`, the server calls the public production API directly.

## Example agent prompts

- *"What's the congestion risk at Santos right now?"*
- *"Rank these ports by congestion: BRSSZ, CNSHA, NLRTM, USLAX."*
- *"Which of my Asian ports has the highest freight volatility index?"*
- *"Project the congestion at Rotterdam over the next 3 days."*

## License

MIT — see [LICENSE](LICENSE). The signals are provided "AS IS" and do not constitute investment advice. See the [Terms of Service](https://aether-x-oracle-production.up.railway.app/terms).
