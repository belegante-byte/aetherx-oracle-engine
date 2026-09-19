# Contingências — Pausa da Distribuição por Integridade de Dados

> Criado em 2026-09-18. Motivo: o oráculo servia um seed estático apresentado como "live telemetry".
> Ação tomada: (1) código tornou a proveniência explícita em todas as respostas; (2) distribuição em análise de pausa.
> ESTADO ATUALIZADO (2026-09-19, madrugada): **fontes BR conectadas** para BRPNG/BRSSZ/BRRIO/BRNIT/BRITG.
> (`data_source=live:appa+santos+lachmann` e `live:portosrio_silog`). Demais 14 portos seguem com seed referenciado.
> Pausa **total** (remover das listagens) exige ações manuais em dashboards — checklist reavaliado.

## Status atual (2026-09-19, após ingestão viva + releases)

| Frente | Estado |
|---|---|
| Servidor live (Railway) | ✅ Deploy honesto no ar. Landing, /v1/*, /mcp, /public/ports, llms.txt, ai-plugin, OpenAPI, Terms, README corrigidos. |
| Fonte viva BR | ✅ APPA Paranaguá + Porto de Santos + Lachmann + SILOG PortosRio (Rio/Niterói/Itaguaí) conectados; ingestão periódica (6h) no Procfile/railway.json; `scripts/run_ingestion_live.py` grava `raw_port_lineup` + `port_metrics` com `data_source=live:...`. |
| Portos BR vivos | ✅ 5: BRPNG, BRSSZ, BRRIO, BRNIT, BRITG (`live:appa+santos+lachmann` / `live:portosrio_silog`). |
| Snapshot histórico | ✅ `scripts/snapshot_history.py` integrado ao ciclo do lifespan (1 linha/porto/dia, preserva `data_source` real). |
| Testes | ✅ 36 green (incl. `tests/test_live_sources.py` contra fontes reais + SILOG; `test_api.py` ajustado p/ proveniência mista). |
| MCP Registry `io.github.belegante-byte/aetherx-mcp` | ✅ server.json v0.3.0 republished (token renovado). |
| PyPI `aetherx-mcp` 0.2.2 / `aetherx-oracle` 0.4.1 | ✅ Publicados via twine com descrições/proveniência honestas. |
| RapidAPI marketplace | 🔒 Dashboard manual (não acessível via CLI). |
| Cursor Directory / Glama / Smithery | 🔒 Dashboards/manuais. |

## O que a correção de integridade NÃO mudou nos dados

- Os **valores numéricos para os 15 portos globais** continuam seed de referência (`init_prod_db.py`).
- O que mudou: **todo** payload agora declara `data_source`, `as_of` e `data_source_label`.
- **BRSSZ/BRPNG passam a ter `data_source=live:appa+santos+lachmann`** (line-ups reais de APPA, painel da CODESP/Porto de Santos e cronograma Lachmann), com detalhe em `live` (`ao_largo`/`esperados`/`atracados`/`programados`).
- **BRRIO/BRNIT/BRITG têm `data_source=live:portosrio_silog`** — pré-pauta SILOG PortosRio (Rio, Niterói, Itaguaí) com IMO real.
- Ainda **não existem chaves comerciais** (AIS/MarineTraffic/VesselFinder/Datalastic) no ambiente — só fontes abertas.
- ANTAQ: `dadosabertos` segue com DNS fora; painel gov.br é Qlik/PowerBI sem CSV estático; dataset "Situação dos Portos em Tempo Real" (dados.gov.br) é app self-report de criticidade, sem line-up com IMO — não serve como fonte viva, mas é candidato a camada de validação/ground-truth.

## Checklist de contingências

### 1. Fonte real — PARCIALMENTE RESOLVIDO (BR open sources)

### 1. Fonte real — PARCIALMENTE RESOLVIDO (BR open sources)
- [x] Conectar fontes abertas BR (APPA line-up, painel Porto de Santos, Lachmann XLS) — `src/ingestion/live_sources.py`.
- [x] Implementar ingestão real (`scripts/run_ingestion_live.py`, respaldo `src/ingestion/live_sources.py`) e agendar (loop asyncio no lifespan do FastAPI, 6h).
- [x] Trocar `data_source` de `static_reference_seed` para `live:appa+santos+lachmann` em BRSSZ/BRPNG.
- [x] Adicionar BRPNG ao seed (17 portos) e aos metadados SEO/MCP (`PORT_METAS`, `mcp_app`, `llms.txt`).
- [x] Conectar BRRIO via SILOG PortosRio (`live:portosrio_silog`) e incluir no GRID de ingestão.
- [x] Expandir SILOG para Niterói (BRNIT) e Itaguaí (BRITG) — mesma fonte, catálogo agora com 19 portos.
- [x] Agendar `scripts/snapshot_history.py` no ciclo do lifespan (histórico diário com `data_source` real).
- [ ] ANTAQ como camada de validação/ground-truth (mapear datasets primeiro; `dadosabertos` fora do ar).
- [ ] Considerar chave comercial (MarineTraffic/Kpler/VesselFinder/Datalastic) para AIS global.

### 2. Republish do MCP Registry (server.json v0.3.0)
- [x] Rodar `mcp-publisher login github` (sessão JWT renovada) e `mcp-publisher publish` — v0.3.0 publicado com sucesso (`io.github.belegante-byte/aetherx-mcp`).
- [x] Validar que a nova versão mantém `remotes` e `packages` e reflete a descrição honesta.
- NOTA: o schema oficial NÃO tem campo `status` (active/hidden) — remover a listagem = ação no portal do registry, manual.

### 3. PyPI
- [x] Publicar bump corrigido: `aetherx-mcp` 0.2.2 e `aetherx-oracle` 0.4.1 (twine, `PYPI_TOKEN`), com PortRisk/PortTrend expondo `as_of`/`data_source`/`data_source_label`/`live`.
- [ ] Decidir se versões anteriores (0.1.x/0.2.1) devem ser yankadas (opcional; versões novas já corrigem).

### 4. RapidAPI
- [ ] Painel RapidAPI → listing `aether-x-port-congestion-oracle` → pausar/ocultar publicamente OU publicar nova descrição honesta + example com `data_source`.
- [ ] O `openapi.rapidapi.json` local já foi corrigido; precisa sync no portal.

### 5. Cursor Directory / Glama / Smithery
- [ ] Cada agregador: atualizar descrição da listagem (manual) ou remover.
- [ ] Glama grade A e Smithery espelham o repo/registry — corrigir descrição nos dashboards.

### 6. SEO / páginas públicas
- [x] Landing: "Remote MCP Server **Online**" (não "Live"), "Reference Snapshot", aviso de static seed.
- [x] Per-port pages: "reference" em vez de "live"; `as_of` visível.
- [x] `llms.txt`, `ai-plugin.json`, `openapi.rapidapi.json`, `TERMS_OF_SERVICE.md`, `README.md`.

## Critério para reativar distribuição cheia

1. **Fonte real conectada com `data_source=live:<fonte>` em produção** — FEITO para BRSSZ/BRPNG/BRRIO.
2. Backfill/validação de que os números mudam (delta real entre janelas) — acompanhar via `port_metrics_history`.
3. Depois disso, reativar RapidAPI (novo example), MCP Registry (republish v0.3.0 — FEITO) e agregadores.