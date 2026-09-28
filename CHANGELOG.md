# Changelog

Histórico de mudanças relevantes do **Aether-X Oracle Engine**. Formato baseado em
[Keep a Changelog](https://keepachangelog.com/).

## [1.3.0] — 2026-09-28

### Adicionado
- **Gate de acesso MCP (monetização):** decision tools (`evaluate_charter_risk`,
  `evaluate_routing_alternatives`, `evaluate_corridor_risk`) passam a exigir credencial
  M2M válida (Bearer) — erro `-32003` com hint `request_m2m_key`. Antes respondiam
  `-32603` sem orientação de upsell.
- **Quota de observação diária por IP** em `src/api/mcp_quota.py`
  (`MCP_OBSERVATION_QUOTA_PER_DAY`, default 60). Anônimos que estouram a quota recebem
  `-32004`. Autenticados e proxy-secret não têm quota. Header `X-Observation-Quota-Left`
  indicando o saldo.
- **`request_m2m_key`** self-service (MCP) gera trial key de 7 dias que desbloqueia as
  decision tools — função já existia, agora conectada ao funil de métricas.
- **Diagnóstico do funil:** snapshot `/internal/metrics` agora expõe
  `app_version`, `gates.{decision_denied, quota_exceeded, trial_keys_issued}` e a matriz
  `data_quality` padronizada (`grade`, `label`, `source`, `queue_observable`, `paired`).
- **Persistência de contadores:** `_paid_plans`/`_paid_users` e os novos contadores de
  gate sobrevivem a restarts via `data/metrics_state.json`.
- **Hardening MCP:** allow-list de Hosts do transporte inclui
  `aether-x-oracle-production.up.railway.app`; `MCP_ALLOWED_HOSTS` (env) para host
  adicional; `M2M_API_SECRET` (env) como chave-mestra, sem fallback hardcoded.
- CTA de **Access & Pricing** na landing (Observation free / Trial M2M / RapidAPI).

## [1.2.0] — 2026-09-27

### Corrigido (antifake)
- **Ficção de 18 portos "live" removida:** o engine não entrega mais 18 LIVE globais
  fabricadas; apenas BRSSZ/BRPNG/BRRIO/BRNIT/BRITG têm fila viva de autoridade
  (`live:appa+santos+lachmann`, `live:portosrio_silog`).
- **Portos globais** passam a `calibrated_reference_seed` / `static_reference_seed`
  (explícito em `data_source`, `decision_grade=reference`, `live_observation=false`).
- Rótulos de landing/referências (`data_source_label`, meta tags, `/public/ports`)
  refletem a verdade: nada finge ser telemetria viva.
- `live:shipinfo_ais` só aparece quando o sensor AIS entrega dados no ciclo.

## [1.1.0] — 2026-09-21

### Corrigido (segurança/auditoria)
- DNS rebinding protection ativa no transporte MCP (allow-list de Hosts).
- Erros de tool MCP atribuíveis (tool/porto/tipo de erro + client_id mascarado).
- Segredo master M2M movido para env `M2M_API_SECRET`; chave default comprometida
  filtrada no load e substituída.
- CORS restrito; documentação honesta das tools MCP; mitigação do bloqueio de mock RUMO.

### Adicionado
- Persistência dos contadores M2M (`data/metrics_state.json`, tolerante a restart).
- Funil por máquina (discovery → mcp_connect → tool_call → repeat_tool → paid).

## [0.x] — histórico anterior

Ver `git log` para o histórico completo antes da disciplina de changelog.