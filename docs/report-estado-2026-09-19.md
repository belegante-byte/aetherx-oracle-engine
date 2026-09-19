# Relatório de Estado — 2026-09-19

> Checkpoint pós-entrada em **Continuous Improvement Mode**. Registra o estado do
> sistema, a instrumentação de observabilidade e as evidências atuais de consumo.

## Marco principal

> **M2M funnel instrumentation is now operational in production.** The system
> distinguishes discovery, MCP connection, tool invocation, repeat behavior and
> paid state at anonymous-machine level.

### Evidência atual (janela observada)

| Etapa | Status | Evidência |
| --- | --- | --- |
| Descoberta | ✅ demonstrado | `funnel.discovery` |
| Conexão MCP | ✅ demonstrado | `funnel.mcp_connect` |
| Transport repeat | ✅ demonstrado | `funnel.repeat_transport` |
| **Tool call** | ⚠️ **ainda não observado na janela** | `funnel.tool_call = 0` |
| Repeat tool call | ❌ não demonstrado | `funnel.repeat_tool = 0` |
| Paid | ❌ não demonstrado | `funnel.paid = 0` |

**Máquina ilustrativa `846488f1`:** `discovery → mcp_connect → repeat` (34 calls),
**sem tool_call** — retenção de infraestrutura, não do produto.

## Interpretação correta

- **Não interpretar** "N unique / N repeat" como retenção de produto.
- **Interpretar** como: máquinas repetindo interação com infraestrutura.
- O KPI de produto é **tool-call retention** (`repeat_tool`), não connection retention.
- Consumo real do Oracle **ainda não demonstrado nesta janela**.

## Infraestrutura comercial completa (montada)

| Camada | Estado |
| --- | --- |
| Descoberta | MCP Registry v0.4.2 · Glama · Smithery · GitHub · HF · RapidAPI · public-apis PR |
| Acesso | MCP (4 tools) · REST (3 endpoints) · SDK (aetherx-oracle 0.4.1) |
| Produto | 23 campos + provenance (`fonte`/`semantica`) + validation ANTAQ |
| Qualidade | BRPNG calibrado (0.504) + confidence 0.52 + ANTAQ 2026-jan |
| Observabilidade | Control Tower interna + dashboard local + persistência + funil M2M |
| Monetização | detecção `X-RapidAPI-Subscription` (paid_plans/paid_users) |

## Funis (definição operacional)

```
INFRAESTRUTURA FUNNEL
Discovery → MCP Connect → Transport Repeat

PRODUTO FUNNEL
Discovery → Tool Call → Tool Repeat → Paid
```

- `repeat_transport`: máquina voltou ao servidor (infra).
- `repeat_tool`: máquina executou tools em janelas distintas (≥300s) = consumo recorrente.

## Marco a perseguir

```
machine X → MCP connect → get_port_risk → BRPNG → retorna → get_port_risk → BRPNG
```

**Primeiro sinal inequívoco de consumo recorrente do produto.** Depois:
`tool repeat → free limit → subscription → PAID`.

## Prioridades

- **P0:** capturar o primeiro `tool_call` real (funil de produto).
- **P1:** distribuição (public-apis #7432, awesome PRs, novas superfícies).
- **P1:** acumular BRPNG (1/30 pares) — sem calibrar com 1 ponto.
- **P1:** melhorar sinal (A+B por evidência).
- **P2:** observabilidade contínua (já em grande parte entregue).

## Pricing

**Não alterar pricing / não colocar paywall.** O RapidAPI já tem monetização;
o MCP é canal de distribuição. Antes de pricing, capturar primeiro tool_call real.

## Dados / Calibração

- **1 par BRPNG** (2026-09-19, fila=33 ↔ ANTAQ 2026-jan). Acumulação diária via launchd 08:30.
- ANTAQ: 37 meses × 5 portos BR.
- Matriz de qualidade: BRPNG=VALIDATED · BRSSZ/RIO/NIT/ITG=CONDITIONAL · +14=REFERENCE.