# AGENTS.md — Regras de governança do Aether-X Oracle Engine

Este arquivo é leitura OBRIGATÓRIA para qualquer agente (IA ou humano) que vá
alterar o código. Elas existem porque o fluxo de monetização/auth foi quebrado
repetidamente por agentes que "melhoraram" middlewares sem entender o modelo.
**LEIA ANTES DE EDITAR. NÃO reescreva os middleware de auth como "efeito
colateral".**

## 1. Modelo de monetização (IMPORTANTE — não inventar outro)

- **RapidAPI é o merchant-of-record ATIVO (cobrança) da API** — decisão de
  Giovanni em 2026-09-29 (pivô por bloqueio documental do Stripe; reverteu a
  decisão anterior de Stripe-solo). A listing RapidAPI é quem cobra/mede o uso;
  requests do proxy autenticam a REST paga via `X-RapidAPI-Proxy-Secret`.
- **Stripe está FORA do produto.** Não é canal ativo nem "congelado aguardando
  verificação" — está fora. RapidAPI é o ÚNICO merchant-of-record ativo. Não
  implementar, reativar, migrar ou preparar fluxo Stripe (checkout, fulfillment,
  webhook) sem nova decisão explícita do Giovanni. Chaves `gp5_enterprise_*`
  já emitidas continuam aceitas pela REST (compatibilidade de credencial), mas
  nenhum fluxo novo de emissão via Stripe existe ou deve ser criado.
- **Credenciais da REST paga** (`/v1/port-risk`, `/v1/port-trend`,
  `/v1/ports-risk`, `/v1/gp5/*`): chave paga via `Authorization: Bearer
  <chave>` OU `X-RapidAPI-Proxy-Secret` (requests do proxy do marketplace — o
  **canal ativo hoje**). NÃO aceitar trial na REST paga.
- Escada de preços (vive no `PLANS` de monetization.py; o canal de cobrança
   é a listing RapidAPI): Pro US$ 499/mo (US$ 4.990/ano) e Enterprise
   US$ 5.000/mo (US$ 50.000/ano).
- **Níveis de acessoapplied no servidor (1.4.0):** cada chave carrega um nível
  (`trial` | `pro` | `enterprise`) persistido em `m2m_keys_meta.json`
  (`_KEY_LEVELS`). O que cada nível entrega está em `MIN_LEVEL_BY_PATH`,
  `SLOT_LIMITS` e `DAILY_CALL_QUOTA` em `src/runtime/access.py` — **esses mapas
  são a referência única do contrato comercial**; mudou o que o cliente paga,
  muda o mapa + teste em `tests/test_tier_restrictions.py`.
  - `trial`: só MCP (funil free). NUNCA abre REST paga.
  - `pro`: sinais dos 5 portos BR ao-vivo (`port-risk`, `port-trend`,
    `ports-risk`, `port-history` até 90d observados, índice físico, charter/
    corridor risk, PCI/CDR/VQPM/IRDI/SCDEW) + 1 slot + quota diária própria.
  - `enterprise`: Pro + `routing-eval`/`fiscal-routing` (arbitragem) +
    `verified-queue` (evidência ANTAQ) + até 5 slots + quota maior.
  - Slots são **integrações simultâneas**, nunca quantidade de chamadas; a quota
  de chamadas é independente. Ambos são best-effort POR INSTÂNCIA (memória,
  reseta em restart) — **não anuncie SLA de cota**.
  - Requests do proxy do marketplace (rail ativo) passam como
    enterprise-equivalente: quem cobra e mede o tier é o RapidAPI.
- Trial M2M (30 dias) é só lead-gen: `POST /m2m-keys` e o tool MCP
  `request_m2m_key` emitem APENAS trial, que dá acesso SÓ ao MCP. Nunca
  transforme trial em chave paga nem deixe trial abrir a REST paga.
- **Não reintroduza nenhum rail de pagamento** (Stripe, Pix, gateways, moedas)
  sem aprovação explícita do Giovanni. O rail ativo é RapidAPI e só.

## 2. Fronteiras de segurança/monetização (não mexer de passagem)

- `RapidAPIGuard` (src/api/main.py) e `M2MGatewayMiddleware` são a fronteira de
  segurança E monetização. **Não reordene, não burle permissão, não adicione
  exceção em `is_public_path`** sem aprovação + ajuste de testes.
- Ordem real do middleware (do mais externo para o mais interno): CORS →
  PublicRateLimit → RapidAPIGuard → Metrics → M2MGateway → rota. REST sem
  secret é barrado pelo guard ANTES do M2M gateway.
- Lista pública deve manter: `/m2m-keys`, `/demo`, `/fiscal-demo`,
  `/internal/control-tower`, `/aetherx-mcp.json`, `/mcp*`, `/v1/m2m/request-key`,
  `/checkout/*`, `/webhook/stripe`, `/m2m-keys/fulfillment` (checkout/fulfillment
  precisam ser públicos; o webhook recebe POST do Stripe sem segredo) e tudo de
  SEO/docs (`/docs`, `/redoc`, `/public/`, `/port-congestion-*`,
  `/arbitragem-logistica/*`, verificação Google/Bing, `/openapi*.json`).
- REST pago NUNCA público: `/v1/port-risk`, `/v1/port-trend`, `/v1/ports-risk`,
  `/v1/port-history`, `/v1/verified-queue`, `/v1/gp5/*`.

## 3. Regras de commit

- **NUNCA** commite `config/.env` (contém `RAPIDAPI_PROXY_SECRET`) ou segredos.
- **SEMPRE** restaure o binário rastreado antes de commitar:
  `git checkout -- data/oracle.duckdb`. Ele muda a cada teste/boot.
- Rode a suíte completa antes do commit:
  `.venv/bin/python -m pytest tests/ -q` (117+ testes; pode haver 1 flake de
  fonte live, rode de novo).
- Commit assinado: `-c user.name="Giovanni" -c user.email="giovanni@aether-grid.io"`.
  Commits assinados `Giovanni <Apple@MacBook-Pro.local>` são de OUTRO agente.
- Cada mudança de segurança/monetização: commit dedicado com testes + entrada
  no `CHANGELOG.md`.

## 4. Deploy

- Deploy é SEMPRE manual: `railway up --service aether-x-oracle --detach`
  (projeto `aether-platform-api`, domínio `https://aetherx.aether-grid.io`).
- Um `git push` NÃO deploya nada por conta própria.
- Confirme `RAPIDAPI_PROXY_SECRET` setado nas variáveis de ambiente do Railway —
  sem ele o guard fica inerte e a REST paga abre.

## 5. Aviso geral

- Se você não entende uma área, LEIA os testes e o CHANGELOG, não reescreva.
- Não "arrume" coisas que não foram pedidas. Mudança de auth/monetização sem
  necessidade documentada = bug em produção.