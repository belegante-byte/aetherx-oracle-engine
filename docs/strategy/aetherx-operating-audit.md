# Aether-X — Operating Audit

> Gerado em 2026-09-19. Auditoria operacional completa antes de novas features,
> conforme a Operating Doctrine. Todo estado é verificado em tempo real.

---

## 1. CURRENT STATE

### Produto
- **URL pública:** `https://aetherx.aether-grid.io` (custom domain de marca; CNAME → `gsxtyhih.up.railway.app`; TLS Let's Encrypt; HTTP 200)
- **URL legada:** `https://aether-x-oracle-production.up.railway.app` (funciona em paralelo, infra)
- **Health:** `ok`, service `aether-x-oracle`, version 0.2.1
- **Hosting:** Railway, projeto `aether-platform-api` (id `23dd7aef`), serviço `aether-x-oracle` (id `67c62a7b`). ⚠️ serviço coexiste com app "aether-platform" (id `c52c9055`) no mesmo projeto — decisão: manter por ora, estudar longo prazo.

### Endpoints REST
| Endpoint | Método | Descrição |
|---|---|---|
| `/v1/port-risk` | GET | Risco de um porto |
| `/v1/port-trend` | GET | Projeção 24/48/72h |
| `/v1/ports-risk` | GET | Batch (até 20 portos) |
| `/public/ports` | GET | Feed público read-only (widget/embed) |
| `/internal/metrics` | GET | Observabilidade M2M (protegido) |

### Endpoints web/SEO
`/`, `/health`, `/terms`, `/openapi.rapidapi.json`, `/llms.txt`, `/sitemap.xml`, `/robots.txt`, `/mcp-page`, `/port-congestion-api`, `/santos-port-congestion-api`, `/port-congestion-python`, `/port-congestion-{slug}` (24 páginas de portos), `/.well-known/ai-plugin.json`, `/google*.html` (verificação), `/BingSiteAuth.xml`.

### MCP tools (4)
| Tool | Descrição |
|---|---|
| `get_port_risk` | Sinal de um porto |
| `get_ports_risk` | Batch de portos |
| `get_port_trend` | Projeção sintética |
| `list_supported_ports` | Lista 19 portos |

### Portos (19)
- **BR vivos (5):** BRSSZ (`live:santos+santos_painel`), BRPNG (`live:appa+lachmann`), BRRIO/BRNIT/BRITG (`live:portosrio_silog`)
- **Seed de referência (14):** CNSHA, CNNGB, CNTAO, SGSIN, NLRTM, USLAX, USNYC, DEHAM, MPTNG, AEDXB, KRPUS, GBLGP, ZACPT, MXZLO

---

## 2. PRODUCT QUALITY

### Campos do payload (BRPNG, calibrado)
| Campo | Valor | Proveniência |
|---|---|---|
| `congestion_score` | 0.504 | calibrado (fila observada → ANTAQ) |
| `waiting_vessels` | 36 | **fila real ao_largo** (não soma com esperados) |
| `historical_expected_wait_h` | 182.4 | ANTAQ distribuição |
| `p90_wait_h` | 588.4 | ANTAQ p90 |
| `eta_delay_days` | 7.6 | derivado da espera calibrada |
| `expected_demurrage_usd` | 243200 | horas × US$32k/dia |
| `p90_demurrage_usd` | 784533 | p90 × US$32k/dia |
| `confidence` | 0.52 | f(pares, recência ANTAQ) |
| `fonte` | `calibracao_v1_antaq+observacao_fila` | provenance |
| `semantica` | `espera historica ANTAQ + fila observada` | provenance |
| `validation` | ANTAQ 2026-jan (140.5h avg / 42.9 med / 344.9 p90) | ground-truth tardio |

### Estado do sinal
- **BRPNG é o único porto com decisão plena** (fila observável + validação ANTAQ + calibração + 1 par emparelhado).
- Demais BR (BRSSZ/BRRIO/BRNIT/BRITG): fila observada + validação ANTAQ, mas **sem pares de calibração** → usam score heurístico da ingestão.
- **Portos seed:** referência estática, explicitamente marcados (`static_reference_seed`).

---

## 3. DATA QUALITY

### Matriz de qualidade por porto
| Port | Source | Live | Queue observable | Hist. validation | Decision grade |
| --- | --- | ---: | ---: | ---: | --- |
| BRPNG | APPA | yes | **yes** | yes | **decision** |
| BRSSZ | Santos | yes | no | yes | conditional |
| BRRIO | SILOG | yes | no | yes | conditional |
| BRNIT | SILOG | yes | no | yes | conditional |
| BRITG | SILOG | yes | no | yes | conditional |
| 14 outros | seed | no | no | no | reference |

### Calibração (BRPNG anchor)
- **1 par registrado:** 2026-09-19, fila=33 (ao_largo), ANTAQ 2026-jan (140.5h avg).
- Acúmulo diário via launchd (`com.aether.acumula-brpng`, 08:30) → `scripts/acumular_brpng_diario.py`.
- **Marco:** ≥30 pares antes de modelagem. Regra anti-overfit respeitada (v1 usa distribuição, sem regressão).

### Ontologia / semântica
- Estados canônicos: `AT_ANCHOR` (ao_largo) = fila real; `EXPECTED`/`SCHEDULED` = chegadas futuras (não contam como espera). Correção aplicada em 2026-09-19.
- SILOG: `SAÍDA`/`ENTRADA`/`MUDANÇA` mapeados a estados canônicos; `FUNDEADO`/`AGUARDANDO` → `AT_ANCHOR`. Não há equivalência direta SILOG → `waiting_vessels` sem evidência (limitação conhecida).

### Fontes
| Fonte | Cobertura | Tipo |
|---|---|---|
| APPA Paranaguá | BRPNG | line-up ao vivo (seções, IMO) |
| Porto de Santos | BRSSZ | atracações programadas + painel |
| Lachmann | BRPNG | ETAs reais (XLS) |
| SILOG PortosRio | BRRIO/BRNIT/BRITG | pré-pauta/agendamentos |
| Seed estático | 14 portos | referência |

---

## 4. DISTRIBUTION

### Estado das superfícies (verificado em tempo real)
| Surface | Status | HTTP | Última verificação |
| --- | --- | ---: | --- |
| MCP Registry | **live** | 200 | v0.4.2, pkg aetherx-mcp 0.2.4 |
| Glama | **live** | 200 | conector Grade A |
| Smithery | **live** | 200 | listado |
| public-apis | **PR #7432 OPEN** | — | re-adicionando (merge #7425 não persistiu) |
| RapidAPI | **live** | 200 | spec importada, health SUCCESS, 19 ports |
| GitHub (engine/mcp/sdk) | **live** | 200 | 3 repos públicos |
| Hugging Face (space/dataset) | **live** | 200 | ambos |
| PyPI | **live** | — | aetherx-oracle 0.4.1 · aetherx-mcp 0.2.4 |
| Google | **indexing** | 200 | Search Console verificado, sitemap enviado |
| mcp.so | **bloqueado** | 404 | issue #4236 aguardando humano |
| PulseMCP | **bloqueado** | 403 | Cloudflare / submissões pausadas |
| awesome-remote-mcp-servers | **PR #403 OPEN** | — | aguardando review |
| awesome-mcp-servers | **PR #14670 OPEN** | — | aguardando review |

---

## 5. DISCOVERY

### Tráfego M2M observado (janela ~92 min de boot)
| Canal | Unique | Repeat | Second-call rate |
| --- | ---: | ---: | ---: |
| MCP | **19** | **13** | 68.4% |
| SEO | 5 | 5 | 100% |
| Discovery | 6 | 3 | 50% |
| REST | 1 | 1 | 100% |
| Bots | 7 | 5 | 71.4% |

- **`/mcp` = 166 hits** — endpoint mais acessado.
- **Evidência de descoberta e retorno:** 19 máquinas MCP únicas, 13 repetindo. **Formulação rigorosa:** "13 das 19 máquinas MCP observadas foram classificadas como repeat pela instrumentação atual nesta janela de boot" — comportamento de retorno, não inferência de valor percebido.
- Google já rastreia o domínio (sitemap com 24 URLs enviado).

---

## 6. OBSERVABILITY

### O que o `/internal/metrics` expõe (HOJE)
- `uptime_seconds`, `total` por canal, `bot_calls`
- `unique_machines`, `repeat_machines`, `second_call_rate` por canal
- `top_paths`

### Log `AETHERX_METRIC`
- Campos: `channel`, `path`, `ua`, `ip_hash`, `ts`

### LACUNAS (o que falta — prioridade alta)
| Lacuna | Necessidade (doctrine §4) |
| --- | --- |
| **Tool invocada no MCP** | "qual ferramenta estão usando?" |
| **Porto consultado** | "qual porto estão consultando?" |
| **Status code** | "há erros?" |
| **Latência** | runtime health |
| **first→second intervalo** | return intervals |
| **Request rate (req/min)** | derivado apenas do total |

---

## 7. INCONSISTENCIES

| # | Inconsistência | Severidade | Status |
| --- | --- | --- | --- |
| 1 | public-apis: merge #7425 não persistiu no master atual | Média | PR #7432 aberta |
| 2 | public-apis antigo dizia "16 major ports" + URL Railway | Média | corrigido na PR #7432 |
| 3 | RapidAPI "16 major ports" em billing feature | Baixa | corrigido (19 ports) |
| 4 | Versões divergentes: registry v0.4.2 vs PyPI aetherx-mcp 0.2.4 vs SDK 0.4.1 | Baixa | aceitável (registry version ≠ pkg version) |
| 5 | Duas PRs awesome-lists ainda OPEN | Baixa | aguardando review |

---

## 8. RISKS

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| Persistência efêmera no Railway (sem volume) | pares perdidos a cada deploy | acúmulo é LOCAL via launchd |
| Dependência do CLI Railway auth (login interativo) | bloqueia `railway domain` via CLI | dashboard manual |
| Cache CDN de listings (RapidAPI/Google) | atraso na refletir mudanças | re-fetch periódico |
| Observabilidade insuficiente (sem tool/porto) | não sabemos o que máquinas fazem | instrumentar (próxima ação) |
| Portos seed podem parecer "reais" | confusão do consumidor | data_source explícito já presente |

---

## 9. OPPORTUNITIES

| Oportunidade | Frente | Impacto |
| --- | --- | --- |
| Instrumentar tool/porto/status/latência no MCP | Observabilidade | alto (responde "o que fazem?") |
| Inconsistency sweep automatizado (auditar URLs antigas/versões) | Inconsistência | médio (evita drift) |
| Matriz de qualidade por porto no payload | Produto | médio (transparência decisória) |
| Pares de calibração para BRSSZ (fila não observável hoje) | Dado | médio (via AIS futuro) |
| AIS quando houver hipótese de reconstruir fila | Dado | médio (não especulativo) |
| mcp.so/PulseMCP quando desbloquear | Distribuição | médio |

---

## 10. PRIORITY MATRIX

| Prioridade | Item | Frente |
| --- | --- | --- |
| **P0** | Nenhuma em aberto (produto correto, no ar, domínio novo) | — |
| **P1** | Instrumentar observabilidade MCP (tool, porto, status, latência) | Observabilidade |
| **P1** | Continuar acúmulo de pares BRPNG (até 30) | Dado |
| **P2** | public-apis PR #7432 acompanhar | Distribuição |
| **P2** | Inconsistency sweep automatizado | Inconsistência |
| **P2** | Matriz de qualidade por porto no payload | Produto |
| **P3** | Acompanhar PRs awesome-lists + mcp.so | Distribuição |
| **P4** | Cosmética em copy/páginas | — |

---

## 11. NEXT ACTIONS

1. **P1 — Instrumentar observabilidade** (próximo passo concreto): estender `/internal/metrics` + log `AETHERX_METRIC` para registrar no canal MCP a **tool invocada**, **porto**, **status code** e **latência**. Versionar a mudança de instrumentação com timestamp (preservando séries anteriores, doctrine §15).
2. **P1 — Manter acúmulo de pares** (launchd 08:30 rodando; não interromper).
3. **P2 — public-apis #7432**: aguardar merge; se rejeitada, ajustar formato.
4. **P2 — Inconsistency sweep**: script que audita URLs antigas (`aether-x-oracle-production`), contagem de portos, versões PyPI vs registry vs spec.
5. **P2 — Matriz de qualidade**: expor `decision_grade` por porto no payload (BRPNG=decision, BR demais=conditional, seed=reference).
6. **P3 — Canais travados**: acompanhar awesome PRs #403/#14670, mcp.so #4236.

---

*Auditoria executada em modo CONTINUOUS IMPROVEMENT (doctrine). Próxima re-auditoria: após instrumentação P1 ou em 7 dias.*