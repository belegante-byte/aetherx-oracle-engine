# Relatório de Estado Final — 2026-10-03 14:30 BRT

> **Propósito:** snapshot verificável do estado do produto após a sessão de hoje.
> Cada número tem comando de reprodução na §4. Não confie na narrativa — rode.

---

## 1. TL;DR

- **Produção saudável, versão unificada.** `/health` → `1.5.0`, MCP `serverInfo` → `1.5.0`, SEO verification → HTTP 200, auth boundary → 401, 22 tools MCP live, landing `as_of 17:28 UTC` (~2 min de idade), Santos 32 atracados / 122 programados.
- **Tudo que foi feito hoje está no origin e deployado.** `main` 0 commits ahead/behind. Suíte 293/293 verde.
- **Dois problemas novos descobertos (não bloqueantes):** (a) `funnel.md` linka `m2m/surfaces.csv`, `m2m/README.md`, `m2m/ritual-7d.md` — o diretório `m2m/` **não existe** nem no git nem no disco; (b) 11 arquivos detrito de agentes na raiz não estão no `.gitignore`.
- **Fila restante:** persistência de métricas (repeat rate reseta a cada deploy), limpeza dos detritos, correção dos links quebrados do `funnel.md`.

---

## 2. O que foi feito nesta sessão (cronologia verificada)

| Commit | O quê | Status produção |
|---|---|---|
| `0b31f8f` | untrack `data/oracle.duckdb` + `.gitignore` (causa raiz das 2 falhas de teste) | ✅ deployado |
| `3e82294` | relatório de estado inicial + adendo P0 | ✅ no origin |
| `307ecb3` | primeira tabela semanal do `funnel.md` com dados reais (PyPI + logs Railway) | ✅ no origin |
| `479057a` | fix SEO: mover verificação Google de `data/` para `static/` (volume sombreava) | ✅ deployado, HTTP 200 confirmado |
| `30e139d` | fonte única de versão: arquivo `VERSION` = `1.5.0`, consumido por `/health`, MCP, landing, cockpit, spec RapidAPI | ✅ deployado, `/health` 1.5.0 confirmado |

Deploy mechanism descoberto: **auto-deploy está desligado** neste serviço Railway. Push para `main` não trigga nada. Deploy é via `railway up` (CLI) ou Redeploy no painel. Três deploys manuais disparados e verificados nesta sessão.

---

## 3. Estado real do produto (verificado 14:30 BRT / 17:30 UTC)

### 3.1 Produção
```
/health                              → {"status":"ok","version":"1.5.0"}
/google4110ae6f1f7c3af0.html         → HTTP 200 (corpo: google-site-verification:...)
/v1/port-risk (sem auth)             → HTTP 401 (fronteira fechada)
MCP initialize → serverInfo.version  → "1.5.0"
MCP tools/list                       → 22 tools
Landing as_of                        → 2026-10-03 17:28 UTC (~2 min)
Santos line-up                       → 32 atracados / 122 programados
Volume Railway                       → vol_3d7f38b9ezpiy90x montado (P0.3 ✅)
Init prod                            → 38 portos, 5 sources live preservadas, seed idempotente OK
```

### 3.2 Repositório
```
Branch:    main
Ahead:     0 commits
Behind:    0 commits
Working tree clean (excluindo 11 detritos não versionados)
Suíte:     293 passed, 0 failed, 19 warnings (FastAPIDeprecationWarning — cosmético)
```

### 3.3 Funil (dados reais coletados hoje)
| Canal | Visitors | Installs | First Call | Repeat | Paid |
|---|---:|---:|---:|---:|---:|
| RapidAPI | n/d (painel) | n/d | n/d | n/d | 0 |
| PyPI SDK (`aetherx-oracle`) | — | 25/sem | — | — | 0 |
| PyPI MCP (`aetherx-mcp`) | — | 61/sem | — | — | 0 |
| MCP remote | 4 máq não-bot | — | 4 | n/d | 0 |
| SEO | 2 humanos | — | 7 eventos | n/d | 0 |
| Outbound | 0 | — | 0 | — | 0 |

Bots excluídos por política: mcpbeat(30), SentinelOracle(12), Golemreach(4), agent-market-probe(3), Googlebot(2) = 5 máquinas, 51 eventos.

**Repeat rate não calculável:** janela de ~46 min pós-deploy insuficiente para medir 7 dias. Contadores `/internal/metrics` resetam a cada deploy — e foram feitos 3 deploys hoje. Re-medir em 2026-10-10.

### 3.4 Versionamento (antes vs depois)
| Ponto | Antes | Depois |
|---|---|---|
| `/health` | `0.2.1` hardcoded | `1.5.0` via `VERSION` |
| MCP `serverInfo` | `1.3.0` hardcoded | `1.5.0` via `VERSION` |
| Landing footer | `v0.2.1` literal | `v{APP_VERSION}` |
| Cockpit interno | `0.4.x / api 0.2.1` | `{_SERVICE_VERSION}` |
| Spec RapidAPI | `0.2.0` hardcoded | `APP_VERSION` |
| Pacotes PyPI | `aetherx-mcp 0.2.4`, `aetherx-oracle 0.4.1` | inalterados (ciclo próprio por design) |

---

## 4. Problemas descobertos (não resolvidos)

### 4.1 Links quebrados no `funnel.md`
O arquivo referencia `m2m/README.md`, `m2m/surfaces.csv` e `m2m/ritual-7d.md` em 3 lugares — mas o diretório `m2m/` **não existe** (nem no git, nem no disco). Ou foi removido em algum momento, ou nunca foi criado. Os links são mortos.

**Ação:** ou criar o diretório `m2m/` com os três arquivos, ou remover as referências do `funnel.md`. Decisão de produto — não implementar sem alinhamento.

### 4.2 Detritos de agentes na raiz (11 arquivos)
```
artifacts_mcp_diff_final.patch
artifacts_tests_diff.patch
docs/agents/
docs/architecture/
final_audit.patch
make_md_patch.py
mega_patch.py
mega_patch_tests.py
pytest_final_audit.txt
pytest_output_final.txt
scripts/mock_db_weather_delay.py
```
Nenhum está no `.gitignore`. São artefatos de sessões anteriores de agentes. Não afetam o produto, mas poluem o working tree e podem ser acidentalmente commitados.

**Ação:** adicionar ao `.gitignore` ou deletar. Baixo risco, pode ser feito sem alinhamento.

### 4.3 Persistência de métricas
`/internal/metrics` é em memória e reseta a cada deploy. O repeat rate (métrica decisiva do funil) não é persistido em lugar durável. Os logs `AETHERX_METRIC` no Railway são a fonte durável, mas precisam de agregação contínua (não há processo que faça isso hoje).

**Ação:** gravar contadores no DuckDB periodicamente, ou agregar dos logs de forma contínua. Escopo de WU separada.

### 4.4 FastAPIDeprecationWarning (cosmético)
`main.py:1162` e `:1200` usam `example=` (singular, deprecated) em vez de `examples=` (plural). Gera 19 warnings na suíte e 2 linhas vermelhas nos logs de produção. Não bloqueia nada.

**Ação:** trocar `example=` por `examples=` nas duas linhas. Trivial.

---

## 5. Fila de prioridades atualizada

**P1 — agora**
1. Corrigir links quebrados do `funnel.md` (criar `m2m/` ou remover refs)
2. Limpar detritos: `.gitignore` ou delete dos 11 arquivos
3. Fix cosmético: `example=` → `examples=` (2 linhas)

**P2 — esta semana**
4. Persistência de métricas no DuckDB (repeat rate sobrevivendo a deploys)
5. Wire-up da reconstruction layer a endpoint (valor novo ainda não consumível)
6. Definir gatilho de graduação do shadow pipeline

**P3 — quando houver tração**
7. Preencher RapidAPI e GitHub Insights manualmente no `funnel.md`
8. Re-medir repeat rate em 2026-10-10 (7 dias de log contínuo)

---

## 6. Verificação independente (rode tudo)

```bash
cd "/Users/AETHER - X"

# Produção
curl -s https://aetherx.aether-grid.io/health
curl -s -o /dev/null -w "%{http_code}\n" https://aetherx.aether-grid.io/google4110ae6f1f7c3af0.html
curl -s -o /dev/null -w "%{http_code}\n" https://aetherx.aether-grid.io/v1/port-risk

# MCP version
curl -s -X POST https://aetherx.aether-grid.io/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' \
  2>/dev/null | grep -oE '"version":"[^"]*"'

# Repo
git log -5 --oneline
git rev-list --count origin/main..HEAD  # deve ser 0
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q --tb=no 2>&1 | tail -3

# VERSION file
cat VERSION  # deve ser 1.5.0

# Links quebrados
ls m2m/ 2>&1  # deve falhar — diretório não existe

# Detritos
git status --short | grep "^??" | wc -l  # deve ser 11
```

---

## 7. O que NÃO fazer (reiterado)

- Não criar Cron no Railway para ingestão (loop interno já existe).
- Não rodar ingestão local e relatar como mudança de produção.
- Não comparar timestamps sem converter UTC→BRT.
- Não expor shadow pipeline a clientes antes do gatilho de graduação.
- Não mexer em middlewares de auth/monetização (AGENTS.md).
- Não afrouxar tolerância do golden test sem diagnóstico de causa raiz (WU-001, AETHER-GRID_RUNTIME).

---

*Fim. Divergências: registre neste arquivo com data e evidência.*