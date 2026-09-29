# Changelog

Histórico de mudanças relevantes do **Aether-X Oracle Engine**. Formato baseado em
[Keep a Changelog](https://keepachangelog.com/).

## [1.4.0] — 2026-09-29

### Adicionado (controle de acesso por plano — engenharia de produto)
- **Três níveis aplicados no servidor: Free/Trial, Pro e Enterprise.** A chave
  carrega um nível persistido (`_KEY_LEVELS` em `m2m_keys_meta.json`) e cada
  endpoint pago declara o nível mínimo em `MIN_LEVEL_BY_PATH`
  (`src/runtime/access.py`). Antes, Pro e Enterprise recebiam a mesma chave com a
  mesma permissão — não havia diferença de produto.
- **Pro** = sinais dos 5 portos BR com fila de autoridade (`port-risk`,
  `port-trend`, `ports-risk`, índice físico, charter/corridor risk, PCI/CDR/VQPM/
  IRDI/SCDEW) **+ novo endpoint `/v1/port-history`** (série observada de até 90
  dias, com cobertura real declarada: `observations`, `span_days`, `first_seen`,
  `last_seen`, `coverage_note` — sem interpolação onde falta observação).
- **Enterprise** = tudo do Pro + arbitragem (`routing-eval`, `fiscal-routing`) e
  evidência validada (`verified-queue`/ANTAQ).
- **Slots = integrações/consumidores simultâneos, não chamadas.** Limite de
  concorrência por chave (`SLOT_LIMITS`: Pro 1, Enterprise 5) aplicado na REST
  paga e liberado em `finally` (inclusive em erro de rota). As **quotas de
  chamadas são independentes dos slots** (`DAILY_CALL_QUOTA`: Pro 5.000/dia,
  Enterprise 50.000/dia, sobrescrevível por `GP5_DAILY_CALL_QUOTA_*`).
- **Erros de plano são explícitos e acionáveis:** 403 `PLAN_REQUIRED` com
  `required_plan`, `plan`, `feature` e `upgrade_hint`; 429 `SLOT_LIMIT_EXCEEDED` /
  `CALL_QUOTA_EXCEEDED` (com `used`, `limit`, `quota_resets`). Sucesso devolve
  `X-Plan`, `X-Slot-Limit` e `X-Call-Quota-{Used,Limit,Remaining}`.
- **Medição por plano:** `ClientContext.plan` e `UsageEvent.plan` (nível no
  registro de uso). Sem exposição de chave ou PII — o `client_id` segue
  mascarado por sha256 no log.
- **Chaves Pro emitidas com prefixo `gp5_pro_*`** (Enterprise segue
  `gp5_enterprise_*`); fulfillment Stripe/webhook leem `metadata.plan`
  (default `enterprise` para sessões legadas).
- Testes: `tests/test_tier_restrictions.py` (16 casos — um por regra: trial não
  abre REST, matriz de níveis, 403+upgrade_hint, slots por concorrência, quota
  independente, proxy do marketplace, plano na medição, integridade do
  histórico). Suíte: 137 testes passando.

### Integridade comercial
- Nenhum plano anuncia SLA: quotas e slots são **best-effort por instância de
  deploy** (contadores em memória; reseta em restart), documentado aqui e no
  `AGENTS.md`.
- `/v1/port-history` retorna somente observações persistidas e declara a lacuna —
  histórico nunca é apresentado como previsão nem como dado ao vivo.
- O proxy do marketplace (rail ativo) segue passando como enterprise-equivalente:
  o tier é aplicado no gateway do RapidAPI, preservando o fluxo de cobrança atual.

## [1.3.3] — 2026-09-29

### Alterado (pivô do Giovanni — bloqueio documental no Stripe)
- **RapidAPI volta como merchant-of-record ATIVO.** O Stripe travou na verificação
  da conta (giro de documentação de comprovante de endereço). Giovanni decidiu
  operar na RapidAPI até a conta liberar e então migrar. Restaurados o card
  "Acesso Pago via RapidAPI" no `/m2m-keys`, CTA do fiscal-demo e o card
  Pay-as-you-go da landing apontando para a listing
  (`https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle`).
- **Stripe é mantido CONGELADO (migração futura):** checkout/fulfillment/webhook e
  as chaves `gp5_enterprise_*` continuam wireados e aceitos pela REST, só não são
  mais o funil. Migração = trocar CTAs quando a verificação passar.
- **Governança** atualizada no `AGENTS.md` (RapidAPI ativo, Stripe congelado até
  verificação; não trocar rail antes). Constante `RAPIDAPI_URL` restaurada em
  `content_pages.py`; `docs/llms.txt` reescrito para refletir o pipeline atual.

## [1.3.2] — 2026-09-29

### Alterado (decisão do Giovanni — Stripe é o ÚNICO merchant-of-record)
- **Stripe como cobrança oficial da API.** Assinatura direta via
  `/checkout/gp5-pro` (US$ 499/mo, US$ 4.990/ano) e `/checkout/gp5-monthly`
  (US$ 5.000/mo, US$ 50.000/ano). Confirmado o pagamento, `/m2m-keys/fulfillment`
  e `/webhook/stripe` entregam a chave paga `gp5_enterprise_*` (idempotente por
  `session_id`) no cofre que o `authenticate_client` lê.
- **Credencial paga abre a REST.** `RapidAPIGuard` agora aceita `Authorization:
  Bearer <chave paga>` (Stripe) OU `X-RapidAPI-Proxy-Secret` (requests do proxy
  do marketplace). Trial (30 dias) NÃO abre a REST paga — só MCP.
- **Playground corrigido:** `monetization.py` passou a ler `STRIPE_SECRET_KEY`
  (antes `STRIPE_API_KEY`, que nunca era setado → checkout sempre 503 em prod).
- **Landing/funil 100% Stripe:** removidos os CTAs e o card "RapidAPI
  Pay-as-you-go" da landing, páginas SEO/API e footer; `/m2m-keys` volta com o
  gride de 2 tiers (checkout Stripe) + trial 30 dias; CTA do fiscal-demo volta
  ao `/checkout/gp5-pro`. A listing RapidAPI continua existindo, mas só como
  storefront que direciona para o checkout Stripe.
- **Testes:** suíte Stripe do histórico restaurada (16) + coexistência de
  credencial paga (Bearer abre REST, trial NÃO abre); 121 testes passando.
- **Governança:** `AGENTS.md` atualizado — Stripe merchant-of-record único,
  RapidAPI não volta a cobrar sem aprovação explícita.

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