# Changelog

Histórico de mudanças relevantes do **Aether-X Oracle Engine**. Formato baseado em
[Keep a Changelog](https://keepachangelog.com/).

## [1.5.0] — 2026-09-29

### Corrigido (ingestão real do Porto de Santos — a fonte oficial funciona)
- **TLS sem fallback inseguro.** `src/ingestion/live_sources.py` tinha
  `ALLOW_INSECURE_TLS=1` como **default** e, em qualquer `ssl.SSLError`,
  refazia a requisição com `ssl._create_unverified_context()` — para qualquer
  fonte, não só Santos. Removido: `_fetch` agora delega a
  `src/ingestion/tls_chain.py` (trust store do sistema, `check_hostname=True`,
  `CERT_REQUIRED`), e uma falha de cadeia registra `failed` em vez de produzir
  leitura "viva".
- **Cadeia da APS completada pela via oficial, sem mexer no trust store global.**
  `www.portodesantos.com.br` envia só o leaf e omite a
  `Sectigo Public Server Authentication CA OV R36`. A intermediaria oficial
  (`certs/sectigo_ovr36.pem`, sha256 DER `6542d176…78530`, AKI do leaf = SKI da
  intermediaria `E3:66:…:92`, raiz R46 no trust store) é carregada **em cima**
  das raízes do sistema, num contexto **próprio por fonte** — carregar no
  contexto padrão cacheado vazaria a CA da APS para as outras fontes.
  `scripts/capture_aps_fixtures.py` reproduz a captura com proveniência.
- **Parser semântico por página** (`src/ingestion/aps_santos.py`), a partir das
  respostas reais: `atracados-porto-terminais` → `ATRACADO` (45),
  `navios-fundeados` → `AO_LARGO` (86: 52 na fila, 34 com chegada antiga),
  `navios-esperados-carga` → `ESPERADO` (286: 213 agendados, 73 antigos),
  `navios-esperados-passageiros` → `ESPERADO` (32 agendados). Antes,
  `atracacoes-programadas` era lido como se fosse o line-up e as quatro páginas
  se confundiam.
- **Barreira de promoção a `live:*`.** O coletor marcava `ok: True` mesmo com
  zero linhas e o runner rotulava o porto como `live:` a partir dessa flag.
  Agora: sem linha real (`rows > 0`) **e** sem observação utilizável, o porto
  **não** vira live; `stale` nunca entra no cálculo; fonte oficial do porto tem
  precedência sobre coletor legado do mesmo porto (misturar os dois contava o
  mesmo navio duas vezes — 27 `EM_OPERACAO` + 45 `ATRACADO` inflavam o berço e
  subestimavam a congestão); porto com `live:*` sem observação há mais de
  `LIVE_FRESH_HOURS` (6h) é rebaixado à referência calibrada, registrando em
  `live_detail` quando foi a última observação real.
- **Persistência não destrutiva.** `gravar_raw` fazia
  `DROP TABLE IF EXISTS raw_port_lineup` a cada execução, destruindo o
  histórico. Agora a tabela é criada se faltar, colunas novas entram de forma
  aditiva (`run_id`, `page`, `source_timestamp`, `observed_at`, `fetched_at`,
  `observation_state`, `terminal`, `berth`, `cargo_group`, `peso_t`) e as linhas
  são **acumuladas**. Fonte legada grava `observation_state='unspecified'` em vez
  de fingir leitura atual.
- **`ingestion_runs`:** uma linha por fonte por execução com url, status HTTP,
  `Date` do servidor, versão de TLS, fingerprint do leaf, emissor, fingerprint da
  intermediaria, `tls_chain_verified`, contagem de linhas por estado
  (`current`/`scheduled`/`stale`), IMOs distintos e `state`
  (`ok`/`empty`/`failed`/`unverified`). `empty` = HTTP 200 sem linha, que antes
  contava como sucesso.
- **Corrigido no caminho:** `DATABASE_PATH` explícito era ignorado quando o
  arquivo ainda não existia, e o script caía no `data/oracle.duckdb` do
  repositório; o IMO da APS vem com 8 dígitos (zero à esquerda) e quebrava a
  deduplicação; `_fetch` aceitava HTTP 404/500 como se fosse conteúdo.
- Testes: `tests/test_aps_santos.py` (20 casos: semântica das 4 páginas, IMO,
  `stale` contra a data do servidor, pin da intermediaria, contexto APS sem
  contaminar o padrão, falha fechada, ausência de `verify=False` verificada na
  AST) e `tests/test_ingestion_promotion_gate.py` (11 casos: zero linhas não é
  evidência, `stale`, precedência da autoridade, acúmulo de histórico,
  `ingestion_runs`, rebaixada). Suíte: **176 testes passando**.

## [1.4.1] — 2026-09-29

### Corrigido (integridade do banco de produção — a descoberta do dia)
- **Produção nasceu sem `antaq_validation` nem `calibration_pairs`.** Causa raiz:
  em produção `data/` é um **volume persistente do Railway** que *sombreia* o
  `data/` da imagem, então o `init_prod_db` rodava contra o volume vazio e criava
  só o esqueleto (`port_metrics`, `port_metrics_history`, `freight_rates`,
  `tax_rules`). As duas tabelas que o produto consome
  (`risk_model.load_antaq_validation` → bloco `validation` de `/v1/port-risk`;
  `control_tower` e `metrics` → portas de calibração) **não existiam**: o bloco
  `validation` voltava vazio em produção.
- **Seed curado fora do volume** (`seed/oracle_seed.duckdb`, 1,5 MB, gerado por
  `scripts/build_seed.py` a partir do banco commitado, sha256 e regras gravados
  em `_seed_manifest`): `antaq_validation` 185 (5 portos × 37 meses, 2023–2026),
  `calibration_pairs` 6, `port_metrics` 32 e `port_metrics_history` 64.
- **Hidratação aditiva e idempotente** (`src/engine/seed_hydration.py`, chamada
  pelo bootstrap a cada boot): cria/migra o schema, insere **somente o que falta**
  por chave natural (`port_metrics(port_id)`, `antaq_validation(port_id,ano,mes)`,
  `calibration_pairs(port_id,observed_at)`, `port_metrics_history(port_id,captured_at)`),
  **nunca** sobrescreve observação existente, **nunca** faz drop/delete, e
  **nunca** ressuscita sensor morto (`data_source LIKE 'live:%'`). Cada execução
  vira uma linha em `seed_hydration_log` com contagens e sha256 do seed.
- **Sensor morto fora do seed:** `santospainel.com.br` e `web3.antaq.gov.br`
  estão em NXDOMAIN público, então as 5 linhas `live:*` de `port_metrics` e as 10
  de `port_metrics_history` do banco commitado foram **excluídas do seed** — não
  podem ser reexibidas como leitura atual.
- Rehearsal contra o backup do volume (off-box, sha256
  `19910a9d…c4636`): `antaq_validation` 0→185, `calibration_pairs` 0→6,
  `port_metrics_history` 0→64, `port_metrics` 36→38 (entraram `HORMUZ` e
  `ITGOA`); `freight_rates` 35 e `tax_rules` 14 intactos; 0 linhas `live:*`;
  3 execuções seguidas → só a 1ª insere; reabertura do arquivo mantém tudo.
- Testes: `tests/test_seed_hydration.py` (7 casos: banco vazio, idempotência,
  não-sobrescrita, sensor morto, seed ausente, migração aditiva de coluna,
  proveniência no log). Suíte: **145 testes passando**.

### Corrigido (promessas que a evidência não sustentava)
- **`/v1/port-history` responde 503 `FEATURE_IN_VALIDATION` por padrão.** As
  capturas em `port_metrics_history` são pontuais/de referência (2 instantes), não
  uma série observada contínua de 90 dias. O endpoint só é servido com
  `PORT_HISTORY_ENABLED=1`, depois de cobertura operacional comprovada. O
 1.4.0 havia anunciado "série observada de até 90 dias" como recurso Pro.
- **Copy que prometia fila ao-vivo saiu do ar** (home/destaque, `upgrade_hint`
  de plano e páginas de conteúdo): agora diz **estatística oficial ANTAQ
  (37 meses) + sinais de referência calibrada** para os 5 portos BR, e os 37
  portos globais como **cobertura de referência**. A linha ao vivo volta quando a
  fonte oficial voltar a responder.
- Honestidade do Enterprise: `calibration_pairs` cobre **4 dos 5 portos BR**
  (BRPNG, BRRIO, BRITG, BRNIT) — **BRSSZ não tem par de calibração**, só a série
  mensal ANTAQ. Nenhum texto afirma validação de BRSSZ.

## [1.4.0] — 2026-09-29

### Adicionado (controle de acesso por plano — engenharia de produto)
- **Três níveis aplicados no servidor: Free/Trial, Pro e Enterprise.** A chave
  carrega um nível persistido (`_KEY_LEVELS` em `m2m_keys_meta.json`) e cada
  endpoint pago declara o nível mínimo em `MIN_LEVEL_BY_PATH`
  (`src/runtime/access.py`). Antes, Pro e Enterprise recebiam a mesma chave com a
  mesma permissão — não havia diferença de produto.
- **Pro** = sinais dos 5 portos BR com estatística oficial ANTAQ (`port-risk`,
  `port-trend`, `ports-risk`, índice físico, charter/corridor risk, PCI/CDR/VQPM/
  IRDI/SCDEW) **+ `/v1/port-history`**, que foi entregue aqui em validação e só
  é servido com cobertura contínua comprovada (ver 1.4.1).
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