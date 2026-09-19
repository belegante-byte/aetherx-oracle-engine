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
## Apêndice — Experimentos ativos (2026-09-19)

### Experimento 1: Tool Selection Engineering → resultado positivo
```
ANTES   discovery → connect → tool_call = 0
APÓS    discovery → connect → tool_call = 1   (8ca5bfea: BRPNG, BRSSZ)
```
Intervenção (tool descriptions orientadas a decisão + server instructions + campo `signal`)
alterou o funil de 0 → 1 tool_call. Primeiro resultado experimental positivo.

### Experimento 2: Distribution-by-Intent (ativo)
Ontologia de intenção (congestion/queue/delay/economic/decision) aplicada em
llms.txt, README, registry v0.4.3, MCP description, meta tags e páginas.
Objetivo: aumentar máquinas QUALIFICADAS (com razão explícita de chamar).

### Máquina observada: `8ca5bfea`
```
tool_call #1: congestion→BRPNG, decision→[BRSSZ,BRPNG], delay→BRSSZ
```
Aguardando **retorno em janela distinta ≥300s** com tool_call → `repeat_tool = 1`.

### Marcos (não mexer em pricing até atingir)
1. `TOOL CALL ≥ 1` — ✅ atingido
2. `TOOL REPEAT ≥ 1` — próximo marco (janela ≥300s)
3. machine → múltiplas tools
4. machine → uso recorrente
5. machine → paid

### Regra vigente
Sem pricing, sem paywall, sem intervenção estrutural nova. Deixar a distribuição
por intenção produzir oportunidades e o funil medir comportamento.

## Decisão 2026-09-19 (tarde): zero mudanças estruturais — aguardar comportamento

Três intervenções sequenciais já executadas e registradas:
1. Produto real / dados reais (calibração, fila, demurrage)
2. Tool Selection Engineering (tool_call 0 → 1)
3. Distribution-by-Intent (ontologia em todas as superfícies)

**Regra:** NÃO alterar o sistema agora — perderíamos a atribuição
"qual intervenção produziu qual efeito". O experimento precisa respirar.

### Estado atual (decomposto pela Control Tower)
```
M2M UNIQUE             11+ (mcp + discovery + rest, excl. bots)
TRANSPORT REPEAT       14   (voltaram ao servidor)
TOOL REPEAT             0   (nenhuma voltou para tool)
TOOL CALL (janela)      0   (5 acumuladas = validações)
ERROR RATE              0%
```
**Descoberta:** 14 máquinas demonstram retorno à infraestrutura; nenhuma
demonstrou retorno para consumir o Oracle. Não é problema de instrumentação.

### Próximo evento decisivo
```
TOOL CALL → tempo ≥300s → TOOL CALL   ⇒  TOOL REPEAT = 1
```
Quando ocorrer, examinar: mesma máquina? mesma tool? mesmo porto? novo porto?
mesma intenção? intervalo? o sinal mudou? (mecanismo econômico do produto).

### Ressalva metodológica (janela de 300s)
Se não houver tool_repeat, NÃO concluir falha: a frequência natural da decisão
que o Oracle suporta pode exceder 300s (ex.: consultas 08:00/12:00/16:00).
Quando houver mais tool calls, medir a DISTRIBUIÇÃO dos intervalos, não só o
threshold de 300s.

### Posição
- Discovery/infraestrutura: funcionando ✓
- Primeiro consumo: demonstrado historicamente ✓
- Consumo recorrente: ainda não demonstrado
- Pagamento: ainda não demonstrado
