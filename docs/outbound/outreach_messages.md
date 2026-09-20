# Outbound Commercial Strategy — GP5 Maritime M2M Productization

> Contexto: Base de prospects em `docs/outbound/50_prospects.csv`. Para cada abordagem, preencher as variáveis `{Person}`, `{Company}` e `{Hook}`.
> **Regra de Execução:** Lote 1 (10) → Medir respostas e conversão em `/m2m-keys` → Lote 2 (20) → Lote 3 (20).

## Fatos Atualizados do Produto GP5 (Verdadeiro & Auditável)
- **19 Portos globais monitorados** (5 brasileiros AO VIVO: Santos `BRSSZ`, Paranaguá `BRPNG`, Rio `BRRIO`, Niterói `BRNIT`, Itaguaí `BRITG`).
- **Integração Multimodal:** Fila marítima de navios (APPA, Santos) + Fila de vagões de trem em tempo real (Rumo Logística).
- **Decision Tools (USD):** 
  - `evaluate_charter_risk`: cálculo de exposição a demurrage (US$) sob premissas explícitas de laytime/taxa diária.
  - `evaluate_routing_alternatives`: avaliação comparativa de atrasos entre portos alternativos.
  - `get_physical_events`: pacotes de eventos temporais auditáveis (`change-packet.v1`).
- **Chave de Trial M2M de 7 dias grátis:** Sem cartão de crédito, geração instantânea em **https://aetherx.aether-grid.io/m2m-keys**.
- **Conexão Nativa:** MCP Remote Server (`/mcp`), REST API, SDK Python (`aetherx-oracle`), PyPI (`aetherx-mcp`).

---

## Mensagem 1 — Mesas de Trading & Commodities Agrícolas (PT-BR)
> Público: Cargill, Bunge, ADM, Louis Dreyfus (LDC), COFCO, Amaggi, Caramuru, Viterra, Fiagril, FS Agrisolution.
> Ângulo: **Risco de Demurrage em Dólar + Fila Multimodal (Navios + Trem Rumo)**.

```text
Oi {Person},

{Hook de personalização}

Desenvolvemos o GP5 Maritime, um motor M2M de inteligência física portuária para exportação de grãos (soja, milho, farelo). Ele monitora 19 portos (incluindo Paranaguá e Santos ao vivo) cruzando a fila de navios no largo com a fila de vagões de trem da Rumo em tempo real.

Para mesas de operação física e chartering, ele avalia a exposição financeira a demurrage (sobrestadia em US$) e compara atrasos entre portos em uma única chamada M2M ou via agente MCP (Claude/Cursor).

Disponibilizamos uma chave de teste empresarial de 7 dias (grátis, sem cartão):
https://aetherx.aether-grid.io/m2m-keys

Vale 15 minutos de conversa esta semana para apresentarmos o sinal comparado com os dados da {Company}?

Abraço,
Giovanni
```

---

## Mensagem 2 — Logistics & Ocean Visibility (EN)
> Público: project44, FourKites, Flexport, Descartes, Shippeo, Kuehne+Nagel, DSV, CEVA.
> Ângulo: **Predictive Physical Queue & Demurrage Layer for ETAs**.

```text
Hi {Person},

{PersHook}

We built GP5 Maritime — a predictive M2M physical queue intelligence engine covering 19 ports (Santos, Paranaguá, Shanghai, Rotterdam, LA). It fuses live sea-side vessel queues with land-side railway wagon queueing (Rumo Logistics).

It provides Decision Tools (evaluating daily demurrage financial exposure in USD and comparative port routing alternatives) as raw ChangePackets (physical-event.v1) or MCP agent tools.

Free 7-day M2M trial key (instant generation, no credit card):
https://aetherx.aether-grid.io/m2m-keys

Would you be open to a 15-min data integration call this week?

Best,
Giovanni
```

---

## Mensagem 3 — Maritime Intelligence & Shipbrokers (EN)
> Público: Kpler, Vortexa, Windward, Spire, Veson Nautical, Signal Ocean, Clarksons, Braemar, Simpson Spence Young.
> Ângulo: **Independent Charter Risk Benchmark & ChangePacket Stream**.

```text
Hi {Person},

{PersHook}

GP5 Maritime provides an independent physical risk layer for bulk and container ports, with live multimodal ground truth for major South American export hubs (Paranaguá & Santos).

Beyond static AIS snapshots, it generates temporal physical events (change-packet.v1) and evaluates charter party demurrage risk under explicit user-defined laytime assumptions. Available via REST, Python SDK and hosted MCP server.

Get an instant 7-day trial M2M key:
https://aetherx.aether-grid.io/m2m-keys

Example live data: https://aetherx.aether-grid.io/v1/gp5/physical-events?port_id=BRPNG

Open to a 15-min chat to discuss data-room benchmarking?

Best,
Giovanni
```

---

## Mensagem 4 — AI Agent Marketplaces & MCP Distribution (EN)
> Público: Smithery, Glama, Composio, OpenRouter, LangChain, CrewAI, PydanticAI.
> Ângulo: **Authenticated MCP Decision Tools & Enterprise Connector**.

```text
Hi {Person},

{PersHook}

We updated the Aether-X GP5 Maritime MCP Server to version 1.1.0 with a Dual-Mode runtime. It now exposes both public Observation Tools and authenticated Decision Tools (Demurrage USD risk & Comparative Port Routing).

Agents using {Company}'s framework can evaluate physical supply chain risks in real time without custom scraper logic.

Server endpoint: https://aetherx.aether-grid.io/mcp
Trial M2M Provisioner: https://aetherx.aether-grid.io/m2m-keys

Would love to explore featuring the connector or featuring a demo for your developer community.

Best,
Giovanni
```

---

## Plano de Execução do Lote 1 (10 Prospectos Prioritários)

| Prospecto / Empresa | Responsável / Perfil | Canal | Mensagem | Status |
|---|---|---|---|---|
| 1. Bunge Brasil | Head de Logística / Chartering | LinkedIn | Mensagem 1 (PT-BR) | Preparado |
| 2. Cargill agrícola | Gerente de Corredores de Exportação | LinkedIn | Mensagem 1 (PT-BR) | Preparado |
| 3. Caramuru Alimentos | Mesa de Originação & Frete | LinkedIn | Mensagem 1 (PT-BR) | Preparado |
| 4. Amaggi Commodities | Gestão de Risco & Shipping | LinkedIn | Mensagem 1 (PT-BR) | Preparado |
| 5. LDC (Louis Dreyfus) | Operações Portuárias Paranaguá | LinkedIn | Mensagem 1 (PT-BR) | Preparado |
| 6. Kpler | Product Manager Maritime Data | LinkedIn / Email | Mensagem 3 (EN) | Preparado |
| 7. Veson Nautical | Integration Partnerships | LinkedIn / Email | Mensagem 3 (EN) | Preparado |
| 8. project44 | Director Ocean Freight Data | LinkedIn / Email | Mensagem 2 (EN) | Preparado |
| 9. Flexport | Freight Data Lead | LinkedIn / Email | Mensagem 2 (EN) | Preparado |
| 10. Glama.ai | Developer Relations / MCP Lead | Email / Discord | Mensagem 4 (EN) | Preparado |