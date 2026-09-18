# Outbound — 4 Mensagens por Segmento

> Contexto: base de 50 prospects em `docs/outbound/50_prospects.csv`. Para cada mensagem, preencher as variáveis `{Person}`, `{Company}` e `{Hook}` (motivo específico para aquela pessoa). Regra: **Lote 1 (10) → medir → Lote 2 (20) → Lote 3 (20)**. Nunca disparar os 50 antes de calibrar.

## Fatos que as mensagens podem citar (verdade)
- Free Tier **$0.00**, **no credit card**, 50 calls/mês para avaliação.
- **16 portos** com dados (incl. Santos `BRSSZ`, Shanghai, Rotterdam, LA).
- Campos: congestion score, ETA delay, waiting vessels, freight volatility, **daily demurrage USD**.
- **Batch**: 1 chamada compara até 20 portos (`/v1/ports-risk`).
- **Tendência 24/48/72h** e **MCP server para agentes de IA** (publicado no Official MCP Registry).
- Docs: REST SDK (PyPI `aetherx-oracle`), Swagger, endpoint público ilustrado nas páginas `/port-congestion-*`.

---

## Mensagem 1 — Logistics / Supply-chain visibility
> Público: project44, FourKites, Descartes, Shippeo, Flexport, Kuehne+Nagel, DSV, CEVA... (visibilidade, freight forwarding, ETA). Ângulo: **camada preditiva de port risk / exceção**.

```text
Hi {Person},

{PersHook}

We built a predictive port-congestion signal (16 global ports, incl. Santos) —
congestion score, ETA delay, waiting vessels and daily demurrage exposure,
with 24/48/72h trend. It's REST + Python SDK + MCP, so it drops into feed
integrations and agent workflows.

{Company}'s ocean visibility is strong on what's happening; this adds the
predictive layer on top of ETA and port exceptions.

Free tier ($0, no card) so you can evaluate against real data in minutes:
https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle

Worth a 15-min call this week?

Best,
Giovanni
```

## Mensagem 2 — Maritime / Port Intelligence
> Público: Portcast, Kpler, Vortexa, Windward, Spire, Lloyd's List Intelligence, Signal Ocean, Veson, Pole Star, Oceanbolt. Ângulo: **benchmark / camada derivada de risco independente** (não competir): Aether-X é um sinal de congestão/risk derivado, complementar a AIS/ETA.

```text
Hi {Person},

{PersHook}

Aether-X is an independent port-congestion risk layer: 16 major ports,
congestion score, ETA-delay impact and demurrage exposure, with a
24/48/72h projection and a batch endpoint (20 ports in one call).

Unlike AIS/ETA feeds, we model the *operational risk* derived from queueing —
a natural benchmark layer inside {Company}'s data stack or as a red-flag
feature for clients. Also available as MCP tools for maritime agents.

Free tier ($0, no card) on RapidAPI:
https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle
Example live data: https://aether-x-oracle-production.up.railway.app/santos-port-congestion-api

Open to a 15-min data-rooms chat.

Best,
Giovanni
```

## Mensagem 3 — Quant / Finance / Commodities
> Público: Cargill, ADM, Bunge, LDC, COFCO, Olam, Viterra, Gunvor, Trafigura, Mercuria. Ângulo: **sinal físico precursor de preço** + exposição a portos brasileiros + demurrage + scans de portfólio. Incluir variante PT-BR para mesas no Brasil.

```text
Hi {Person},

{PersHook}

We expose port congestion as a fast physical-market signal: congestion
score, ETA delay and daily demurrage exposure for 16 ports — Santos,
Shanghai, Rotterdam, LA — with 24/48/72h trend. The batch endpoint scans
a whole port portfolio in one call.

For physical desks, congestion at export ports (e.g., Santos) often moves
freight and spreads before official reporting catches up. {Company}'s
shipping/chartering exposure suggests this could be a pre-pricing input.

Free tier ($0, no card) to wire it into backtesting/trading infra:
https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle

15-min call to walk through the data?

Best,
Giovanni
```

**Variante PT-BR (mesas no Brasil / traders BR):**

```text
Oi {Person},

{Hook de personalização}

Disponibilizamos um sinal preditivo de congestão portuária (16 portos, incl.
Santos/BRSSZ): congestion score, atraso de ETA, fila de navios e exposição
diária a demurrage, com projeção 24/48/72h. API REST + SDK Python + MCP,
e endpoint batch que varre até 20 portos em uma chamada.

Para mesas físicas, congestão no porto de exportação costuma precificar frete
e spreads antes dos dados oficiais. Se casar com a exposição de shipping da
{Company}, vale um teste com o free tier (R$0, sem cartão):
https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle

Podemos agendar 15 min?
Abraço,
Giovanni
```

## Mensagem 4 — AI / DevTools / Agents
> Público: Smithery, Glama, Composio, Pipedream, StackOne, LlamaIndex, LangChain, CrewAI, PydanticAI, OpenRouter. Dois subgrupos, mesma estrutura: (a) plataformas de distribuição MCP — pedir destaque/featured; (b) frameworks/agent infra — pedir tool/connector oficial.

```text
Hi {Person},

{PersHook}

Aether-X publishes a port-congestion MCP server (get_port_risk,
get_ports_risk, get_port_trend) covering 16 global ports with demurrage
exposure — already live in the Official MCP Registry + PyPI (`aetherx-mcp`)
and as a hosted remote endpoint.

Agents on {Company} would be able to answer: "which of my ports has the
highest congestion risk right now?" with one tool call.

Would {Company} be interested in listing/featuring/connecting it on your
platform? Happy to provide assets, demo and free-tier keys for your
community.

Best,
Giovanni
```

---

## Plano de execução por lotes

| Lote | O que | Composição sugerida | Gate para avançar |
|---|---|---|---|
| 1 | 10 mensagens (~2–3 por segmento) | 3 logistics · 2 maritime · 3 quant · 2 AI | resposta ≥3 ou ≥1 first API call em 7 dias |
| 2 | 20 (ajustar hook/spam) | conforme aprendizado do lote 1 | resposta ≥6 ou ≥3 first call |
| 3 | 20 restantes | lote final | conversões e contatos a seguir |

**Ritual 7 dias:** preencher o `docs/funnel.md` e as colunas da planilha (First Contact, Channel, Status, First API Call, Second API Call, Paid Conversion).

## Regras anti-spam
- 1 mensagem por pessoa; no máximo 1 follow-up por semana (curto, adicionando avanço: ex. trecho de dados reais de um porto dela).
- Preferir LinkedIn à mensagem direta de e-mail na primeira abordagem.
- Não citar "disponível para dados de todos os portos do mundo" — ser fiel aos 16 portos atuais.
- Priorizar fit real (companies com exposição marítima/portuária) — a base já reflete isso.