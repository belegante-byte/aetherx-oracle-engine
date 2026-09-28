# Gate de Monetização & Diagnóstico do Funil

> Estratégia de acesso e medição aplicada em 2026-09-28 (v1.3.0). Complementa
> `../estrategia-adesao.md` (adesão) e `../funnel.md` (funil comportamental).

## Modelo de acesso (quem pode o quê)

| Camada | Acesso | Tools | Proteção |
|---|---|---|---|
| **Discovery** | Sem credencial, sempre livre | `list_supported_ports`, `request_m2m_key`, `initialize` | — |
| **Observation** | Anônimo, quota diária por IP (default 60) | `get_port_risk`, `get_port_trend`, `get_ports_risk`, `get_port_state`, `get_physical_events`, analytics | `-32004` ao estourar; header `X-Observation-Quota-Left` |
| **Decision** | Bearer M2M válido (trial 7d ou enterprise) | `evaluate_charter_risk`, `evaluate_routing_alternatives`, `evaluate_corridor_risk` | `-32003` com hint `request_m2m_key` |
| **REST Decision** | Bearer M2M válido | `/v1/gp5/charter-risk`, `/routing-eval`, `/corridor-risk`, `/port-exposure` | `403` + hint |

Autenticados (Bearer válido) e portador do `RAPIDAPI_PROXY_SECRET` não consomem quota.
Quota é in-memory por (IP, dia UTC) — aceitável para v1 (grace under load), mas
**não escala multi-instância**; migrar para conta externa quando houver multi-replica.

## Diagnóstico do funil

O funil experimental já media `discovery → mcp_connect → tool_call → repeat_tool → paid`.
Em v1.3.0 adicionamos **onde o funil vaza**, exposto em `/internal/metrics` → `gates`:

- `decision_denied` — anônimos que tentaram Decision Tool sem credencial.
  É a principal medida de **interesse de conversão** (upsell trigger).
- `quota_exceeded` — anônimos que estouraram a quota diária de observação.
- `trial_keys_issued` — trial keys self-service emitidas via `request_m2m_key`.

Leitura recomendada do número:

```
discovery > mcp_connect >> tool_call  → descoberta saudável, produto pouco usado (OK para v1)
tool_call > trial_keys_issued         → interesse de decisão ainda não vira trial (revisar mensagem)
trial_keys_issued > paid              → trial não converte em pagamento (gargalo de vendas)
quota_exceeded crescente              → cobrança de quota funcionando; sinalizar upgrade no -32004
```

## Segurança (operacional)

- `M2M_API_SECRET` (env, Railway) é a chave-mestra — trial keys são `gp5_trial_*`,
  expiram em 7 dias (`M2M_TRIAL_VALIDITY_DAYS`). A chave default anterior foi exposta
  no histórico git e está **filtrada no load** (`access.py`).
- `RAPIDAPI_PROXY_SECRET` **não** está no git (`config/.env` gitignored). Rotação exige
  coordenação com o dashboard do RapidAPI (origin header) — não rotacionar no código
  isoladamente, senão o gateway REST quebra o forward-auth. Revisar periodicamente.
- `MCP_ALLOWED_HOSTS` (env) + default fixo do transporte (`aetherx.aether-grid.io`,
  `aether-x-oracle-production.up.railway.app`, localhost, testserver) protegem contra
  DNS rebinding. O validar do fork só aceita match exato ou padrão `host:*` — para novos
  domínios, adicionar o host literal no env.
- Contadores persistem em `data/metrics_state.json` (gitignored). **Sobrevive a restart,
  não a redeploy** (Railway sem volume). Para histórico duradouro além de deploy, migrar
  para banco externo ou pipeline de logs `AETHERX_METRIC`.

## Estado do build

- `APP_VERSION` (env `AETHERX_APP_VERSION`, default `1.3.0`) no `/internal/metrics`
  permite diagnosticar rollout sem confiar no uptime.
- Matriz `data_quality` padronizada em `{port_id, live, grade, label, source,
  queue_observable, paired}` — derivada do DuckDB em cada snapshot, nunca mockada.