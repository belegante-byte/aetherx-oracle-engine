# Agent framework integrations

Each file shows how an AI agent framework can consume the Aether-X signal directly, using the
typed Python SDK (`pip install aetherx-oracle`). Import of the framework happens inside the file,
so nothing here is required at runtime by the API itself.

## Requirements

- `pip install aetherx-oracle`
- A free RapidAPI key (Free tier $0.00): https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle
- Export it: `export AETHERX_API_KEY="<your key>"`

## Files

| File | Framework | What it shows |
|---|---|---|
| `langchain_agent.py` | LangChain | `@tool` wrapping `get_port_risk` + agent skeleton |
| `llamaindex_agent.py` | LlamaIndex | `FunctionTool` + `ReActAgent` skeleton |
| `crewai_agent.py` | CrewAI | `BaseTool` usable inside a Crew |
| `pydanticai_agent.py` | PydanticAI | `@agent.tool` + `agent.run_sync` |

LLM sections are commented: each framework needs its own model/API key (e.g. `OPENAI_API_KEY`) —
the Aether-X part only needs `AETHERX_API_KEY`.

## Also works via MCP

Every agent framework that speaks MCP can just point at the hosted server:

```json
{
  "mcpServers": {
    "aetherx-oracle": {
      "url": "https://aetherx.aether-grid.io/mcp"
    }
  }
}
```

Or local: `uvx aetherx-mcp` (stdio).