# Relatório de Estado — 2026-10-03 · Handoff para supervisão

> **Origem:** sessão Claude Code (desktop, ambiente local de Giovanni), a pedido do dono.
> **Propósito:** (1) desambiguar o incidente "Railway Cron" relatado por uma sessão
> anterior; (2) registrar o estado real do produto após o commit de reconstrução
> de hoje; (3) fixar a fila de prioridades.
> **Como ler:** cada alegação tem comando de verificação na §6. **Não confie na
> narrativa — rode os comandos.** Este relatório corrige erros MEUS também (§2.5).

---

## 0. ADENDO 03/10 15:45 BRT — P0 executado e verificado

| Item | Status | Evidência |
|---|---|---|
| P0.1 untrack `data/oracle.duckdb` | ✅ Feito | commit `0b31f8f`; suíte 293/293 |
| P0.2 push + deploy | ✅ Feito | push `c70453a..0b31f8f`; deploy `railway up` ACTIVE (commit `9f9ee7c1`, 15:34 UTC); landing `as_of 15:36:57 UTC` = primeiro ciclo de ingestão do container novo; MCP e `/v1/*` 401 íntegros |
| P0.3 volume persistente | ✅ Confirmado | painel: `Mounting volume on: /var/lib/containers/.../vol_3d7f38b9ezpiy90x`; init: `sources live preservadas: 5`, `Total de portos: 38` |

**Lições desta rodada (para não repetir):**

1. **O push NÃO trigou deploy** — Railway deste projeto está com auto-deploy
   desligado; deploy é via `railway up` (CLI) ou manual no painel. Registrar
   isso como parte do runbook de release.
2. **`/health` não serve como sinal de deploy** — `APP_VERSION` é hardcoded
   (`main.py:59`, `0.2.1`) e não acompanha releases. Alinhar versão numa
   única fonte (health + server.json + landing) virou item de P2.
3. **Nada nos 9 commits é observável de fora** — a reconstruction layer
   subiu em produção mas **não está wired a nenhum endpoint**. O valor novo
   ainda não é consumível; wire-up é o próximo passo de produto.
4. **Bug real encontrado: `data/verification/` é sombreado pelo volume.**
   `/google4110ae6f1f7c3af0.html` responde 404 em produção (handler roda —
   `{"detail":"Not found"}` minúsculo é a assinatura dele — mas o arquivo
   não existe atrás do volume). **Verificação de propriedade no Search
   Console está quebrada em produção agora.** Fix barato: copiar os arquivos
   de `verification/` para fora do diretório sombreado (ex.: `static/`) e
   servir de lá. Registrado como novo P1.

**Fila atualizada:**

- **P1-novo:** mover `data/verification/` para path não sombreado e fazer
  deploy (SEO quebrado hoje).
- **P1:** wire-up da reconstruction layer a um endpoint (sem exposição do
  shadow — gatilho de graduação primeiro).
- **P1:** primeira tabela semanal do `funnel.md` (os logs já mostram tráfego
  MCP real externo — ex. crawler `capdiff/0.1` —, dado bruto disponível).
- **P2:** fonte única de versão (`/health` vs `server.json` 0.2.4 vs MCP 1.3.0).
- **P2:** limpar ~40 detritos de agentes na raiz.

---

## 1. TL;DR

- **Não há cron parado.** A ingestão de produção roda **dentro do processo da
  API** (`lifespan` → `ciclo_ingestao`, intervalo padrão 3600s), ativada por
  `ENABLE_LIVE_INGESTION=1` no `startCommand` do `railway.json`.
  Produção está viva e servindo dado com ~30 min de idade (verificado).
- **Criar um Cron no painel do Railway seria prejudicial, não útil:** um Cron
  no Railway é um **serviço separado** com **filesystem próprio e efêmero** —
  escreveria num `oracle.duckdb` que nenhum container da API lê.
- **A rodada local de ingestão de hoje não "destravou" nada:** atualizou o
  banco LOCAL (`data/oracle.duckdb` deste Mac), que não é o banco de produção.
  Produção nunca esteve travada.
- **O alarme "48h" era artefato de fuso horário:** os timestamps do banco/produto
  são **UTC**; a leitura foi feita como se fossem hora local (BRT = UTC-3).
- **Estado real que exige ação:** 8 commits não empurrados (produção v0.2.1 não
  tem a reconstruction layer), suíte com 2 falhas cuja causa raiz é
  `data/oracle.duckdb` **trackeado no git**, e funil externo ainda em zero.

---

## 2. O incidente "Railway Cron" — anatomia

### 2.1 O que a sessão anterior alegou

1. "Railway Cron parado desde 28/09; `is_fresh` vai rejeitar tudo em 48h".
2. "Configure `0 */2 * * *` para `run_ingestion_live.py` no painel".
3. Após rodar ingestão no ambiente local: "o pipeline foi unblocked", "o
   produto está servindo dado real", com `updated_at 2026-10-03 11:15:05`.
4. Justificativa: "tenho privilégio de BypassSandbox e posso abrir a rede".

### 2.2 O que o código mostra (verificável)

- `src/api/main.py` (~linha 511): o `lifespan` da API, quando
  `ENABLE_LIVE_INGESTION=1`, cria a task `ciclo_ingestao()` → roda
  `run_ingestion()` + `invalidate_cache()` + snapshot diário, em loop com
  `LIVE_INGESTION_INTERVAL_S` (padrão **3600s**).
- `railway.json` → `startCommand`: `... && ENABLE_LIVE_INGESTION=1 uvicorn ...`
  → o loop **sobe em produção a cada boot**.
- Portanto: **o mecanismo que a sessão achou ausente é o mecanismo primário.**
  O "cron" como serviço separado nunca fez parte do desenho.

### 2.3 Por que a solução proposta seria prejudicial

No Railway, um Cron Job é um serviço com filesystem próprio. O banco da API
vive no **volume montado no serviço da API**. Um cron separado escreveria em
`<fs-efêmero-do-cron>/data/oracle.duckdb` — **nenhum efeito na produção** — e
adicionaria um componente fantasma que "parece" manter o dado fresco.

### 2.4 O que a rodada local realmente fez

Atualizou o banco local deste Mac (`data/oracle.duckdb` mtime 08:30:37 BRT).
Bancos são distintos: **container local ≠ container Railway**. A verificação
que a sessão fez depois (`calculate_port_risk('BRSSZ')`) rodou contra o banco
**local** — não contra o que os clientes RapidAPI consomem. A conclusão "o
produto está servindo dado real" era verdadeira, mas **não por causa** da
rodada local: produção já se auto-ingeria (e se auto-ingere) sozinha.

### 2.5 Fuso horário — a camada que gerou o pânico (inclui correção minha)

- Banco/produto gravam **UTC**. Hora local de Giovanni: **UTC-3**.
- A sessão anterior leu `as_of 11:15:05` como se fosse "agora" local → achou
  dado fresco; depois leu outros timestamps como "velhos" → alarme de 48h.
- **Eu também errei nesta sessão:** li `as_of 14:06:22` e reportei "~2 min
  atrás". Era UTC = **11:06 BRT**, com Giovanni às 11:38 → idade real ~32 min.
  A correção **não muda a conclusão** (dado fresco, ciclo horário), mas muda a
  lição: **converter fuso antes de comparar timestamps, sempre.**
- Cruzamento que prova o padrão UTC: `updated_at 11:30:37` (banco) == mtime
  do arquivo `08:30:37` local. 11:30 UTC = 08:30 BRT. Bate exato.

### 2.6 Inconsistências numéricas registradas (para calibração)

| Alegação da sessão anterior | Verificação |
|---|---|
| "704 navios processados" | Soma da própria narrativa = 458+154+59+27 = **698** |
| `updated_at 11:15:05` | Banco local real: **11:30:37 UTC** (rodada posterior) |
| "Railway Cron parado" | Não existe cron no desenho; loop interno ativo |
| "verificação final provou live" | Rodou contra banco local, não produção |

---

## 3. Estado real do produto (verificado hoje, 03/10)

### 3.1 Produção — SAUDÁVEL
- `https://aetherx.aether-grid.io` HTTP 200; `/health` → `v0.2.1`.
- Landing pública com `as_of 14:06:22 UTC` (= 11:06 BRT) **estável em 3
  leituras espaçadas** → timestamp de ingestão, não de requisição. Dado ~32 min.
- Line-up real Santos: 29 atracados / 122 programados.
- `/v1/port-risk` sem credencial → **401** (fronteira de auth fechada).
- **Volume:** o CHANGELOG 1.4.1 documenta que produção usa **volume
  persistente** no Railway (que "sombreia" o `data/` da imagem) + hidratação
  aditiva do seed a cada boot. Correção ao que se especulou antes: o risco
  "histórico efêmero" **não está confirmado** — a evidência documental diz o
  contrário. Verificação barata no painel: serviço da API → aba Volumes.

### 3.2 Repositório vs deploy — DEFASEDADO
- `main` está **8 commits à frente de origin** (incluindo TODA a reconstruction
  layer). Nada disso está em produção.
- `server.json` 0.2.4 vs `/health` 0.2.1.

### 3.3 Suíte — 291 passam, 2 falham; causa raiz não é código de produto
- Falhas: `test_provenance.py::test_no_oracle_mutation_in_provenance_tests` e
  `test_shadow_integration.py::test_production_db_protection`.
- Ambas verificam "o oracle.duckdb não deve ser mutado" e **falham porque o
  arquivo está trackeado no git** e a ingestão diária o modifica (hoje 08:30).
  Falso positivo diário por design errado de versionamento.
- **Correção:** `git rm --cached data/oracle.duckdb` + entrada em `.gitignore`.
  O artefato versionado correto já existe: `seed/oracle_seed.duckdb` (com
  manifest de sha256, criado no 1.4.1 exatamente para isso).

### 3.4 O commit de reconstrução — o que foi conectado
- `bfbd54c` `bl_parser`: Bill of Lading → campos de shipment.
- `81e5375` `src/reconstruction/` (2.334 linhas): `ShipmentReconstruction` com
  estados epistêmicos (OBSERVED/DERIVED/HYPOTHESIS/UNKNOWN), resolver de
  identidade, hipóteses controladas, `economic_intelligence` (questões com
  pré-condições declaradas) e `economic_value` (4 perguntas econômicas só com
  evidência disponível). Correção epistemológica: **demurrage agora declarado
  HYPOTHESIS/UNVERIFIED**; `commodity_class` virou campo DERIVED.
- `c721385` 2.784 linhas de teste (inclui replay operacional real).
- `shadow_pipeline` (Phase 4A, failsafe isolated): acumula evidência real em
  produção **sem alterar respostas ao cliente** — graduar só depois de validar.
- Valor comercial: migrar a oferta de "congestion score" (commodity) para
  "exposição de demurrage por shipment com cadeia de evidência auditável"
  (decision-grade) — é isso que sustenta Pro US$ 499/mo.

### 3.5 Funil — números reais
- North-star (usuários externos ≥2 calls/7d): **0**. Pagantes: **0**.
- REST únicos fora proxy: 1; máquinas MCP únicas: 6.
- Tabela semanal de `docs/funnel.md`: **nunca preenchida**.
- 50 prospects outbound (xlsx na raiz): sem movimento.

---

## 4. Fila de prioridades

**P0 — colocar o valor novo no ar**
1. Corrigir versionamento do banco vivo (`git rm --cached` + .gitignore) →
   suíte verde de verdade.
2. Push dos 8 commits → Railway redeploy → conferir `/health` v0.2.4+.
3. Verificar aba Volumes no painel (1 clique) e registrar aqui.

**P1 — funil com direção**
4. Preencher a primeira tabela semanal do `funnel.md` (logs AETHERX_METRIC +
   painel RapidAPI + pypistats). Custo ~30 min; sem isso, distribuição às cegas.
5. Definir gatilho de graduação do shadow → endpoint exposto (qual evidência
   acumulada autoriza cobrar por `economic_value`).

**P2 — higiene**
6. Limpar ~40 detritos de agentes na raiz (`fix_*.py`, `patch_*.py`,
   `mega_patch.py`, `audit_*.txt`).
7. Alinhar `server.json` ↔ versão deployada.

---

## 5. O que NÃO fazer

- **Não criar Cron no Railway** para ingestão (§2.3).
- **Não rodar ingestão local e relatar como mudança de produção** (§2.4).
- **Não comparar timestamps sem converter fuso** (§2.5).
- **Não afrouxar/apagar os testes de proteção** para "voltar ao verde" —
  consertar o versionamento do banco (§3.3).
- **Não expor o shadow pipeline a clientes** antes do gatilho de graduação.
- **Não mexer em middlewares de auth/monetização** (AGENTS.md §1–2).

---

## 6. Verificação independente (rode tudo — não confie)

```bash
cd "/Users/AETHER - X"

# Loop interno de ingestão existe?
grep -n "ENABLE_LIVE_INGESTION" src/api/main.py | head -2
grep -n "ciclo_ingestao\|LIVE_INGESTION_INTERVAL_S" src/api/main.py | head -5
cat railway.json | grep startCommand

# 8 commits à frente do origin?
git log origin/main..HEAD --oneline

# Suíte e as 2 falhas
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q --tb=no | tail -3

# Banco vivo trackeado? (é a causa das 2 falhas)
git ls-files data/ | grep oracle.duckdb

# Produção viva + fuso (compare UTC × BRT)
date -u "+%Y-%m-%d %H:%M:%S UTC"; date "+%Y-%m-%d %H:%M:%S %Z"
curl -s https://aetherx.aether-grid.io/health
curl -s https://aetherx.aether-grid.io/ | grep -o 'as_of&quot;: &quot;[0-9: -]*' | head -1
```

---

*Fim do relatório. Divergências: registre neste arquivo com data e evidência.*
