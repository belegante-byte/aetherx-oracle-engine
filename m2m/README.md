# M2M — Machine-to-Machine Distribution

AETHER-X para máquinas: como agentes, SDKs e integrações consomem o Oracle.

## Tools disponíveis (via MCP ou REST)

**Observation (free, quota diária por IP):**
- `get_port_risk` — congestion score + demurrage exposure para um porto
- `get_ports_risk` — visão multi-porto
- `get_port_trend` — tendência histórica observada
- `get_port_state` — estado físico normalizado
- `get_physical_events` — transições de estado de navios/operações
- `get_pci_index` — Port Congestion Index
- `get_cdr_risk` — Chokepoint Disruption Risk
- `predict_vessel_queue` — previsão de fila
- `get_irdi_index` — Inland Rail Disruption Index
- `evaluate_scdew_warning` — alerta SCDEW

**Decision (requer chave M2M — trial grátis 7 dias via `request_m2m_key`):**
- `evaluate_charter_risk` — risco de afretamento
- `evaluate_routing_alternatives` — alternativas de rota
- `evaluate_corridor_risk` — risco de corredor

## Como consumir

1. **MCP remoto:** `https://aetherx.aether-grid.io/mcp` (streamable-http)
2. **PyPI SDK:** `pip install aetherx-oracle` (REST) ou `pip install aetherx-mcp` (stdio)
3. **RapidAPI:** REST via gateway (merchant-of-record)

## Autenticação M2M

Chave trial grátis: POST `/v1/m2m/request-key` → retorna Bearer token válido por 7 dias.
Chave paga: via RapidAPI subscription ou contato direto.