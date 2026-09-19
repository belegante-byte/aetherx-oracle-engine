# Contingências — Pausa da Distribuição por Integridade de Dados

> Criado em 2026-09-18. Motivo: o oráculo servia um seed estático apresentado como "live telemetry".
> Ação tomada: (1) código tornou a proveniência explícita em todas as respostas; (2) distribuição em análise de pausa.
> ESTADO ATUALIZADO (2026-09-18, noite): **fontes reais conectadas** para BRPNG/BRSSZ
> (`data_source=live:appa+santos+lachmann`). Demais 15 portos seguem com seed referenciado.
> Pausa **total** (remover das listagens) exige ações manuais em dashboards — checklist reavaliado.

## Status atual (2026-09-18, após ingestão viva)

| Frente | Estado |
|---|---|
| Servidor live (Railway) | ✅ Deploy honesto no ar. Landing, /v1/*, /mcp, /public/ports, llms.txt, ai-plugin, OpenAPI, Terms, README corrigidos. |
| Fonte viva BR | ✅ APPA Paranaguá + Porto de Santos + Lachmann conectados; ingestão periódica (6h) no Procfile/railway.json; `scripts/run_ingestion_live.py` grava `raw_port_lineup` + `port_metrics` com `data_source=live:...`. |
| Porto Paranaguá | ✅ BRPNG adicionado ao oracle (17 portos) com score 0.95, 203 aguardando (34 ao largo + 169 esperados). |
| Porto Santos | ✅ BRSSZ agora vivo: 595 atracados + 135 programados (score 0.329, fila refletida em `live`). |
| Testes | ✅ 35 green (incl. `tests/test_live_sources.py` contra fontes reais; `test_api.py` ajustado p/ proveniência mista). |
| MCP Registry `io.github.belegante-byte/aetherx-mcp` | ⏸ server.json atualizado p/ v0.3.0 (description ≤100). Republish PENDENTE (login interativo do mcp-publisher). |
| PyPI `aetherx-mcp` / `aetherx-oracle` | ⏸ Código corrigido. Release/yank é manual. |
| RapidAPI marketplace | 🔒 Dashboard manual (não acessível via CLI). |
| Cursor Directory / Glama / Smithery | 🔒 Dashboards/manuais. |

## O que a correção de integridade NÃO mudou nos dados

- Os **valores numéricos para os 15 portos globais** continuam seed de referência (`init_prod_db.py`).
- O que mudou: **todo** payload agora declara `data_source`, `as_of` e `data_source_label`.
- **BRSSZ/BRPNG passam a ter `data_source=live:appa+santos+lachmann`** (line-ups reais de APPA, painel da CODESP/Porto de Santos e cronograma Lachmann), com detalhe em `live` (`ao_largo`/`esperados`/`atracados`/`programados`).
- Ainda **não existem chaves comerciais** (AIS/MarineTraffic/VesselFinder/Datalastic) no ambiente — só fontes abertas.
- PortosRio SILOG (URL mudou) e ANTAQ `dadosabertos` (DNS) continuam fora de alcance; anotados no `backlog_fontes_portuarias.md` do GP5.

## Checklist de contingências

### 1. Fonte real — PARCIALMENTE RESOLVIDO (BR open sources)

### 1. Fonte real — PARCIALMENTE RESOLVIDO (BR open sources)
- [x] Conectar fontes abertas BR (APPA line-up, painel Porto de Santos, Lachmann XLS) — `src/ingestion/live_sources.py`.
- [x] Implementar ingestão real (`scripts/run_ingestion_live.py`, respaldo `src/ingestion/live_sources.py`) e agendar (loop asyncio no lifespan do FastAPI, 6h).
- [x] Trocar `data_source` de `static_reference_seed` para `live:appa+santos+lachmann` em BRSSZ/BRPNG.
- [x] Adicionar BRPNG ao seed (17 portos) e aos metadados SEO/MCP (`PORT_METAS`, `mcp_app`, `llms.txt`).
- [ ] Expandir cobertura: PortosRio SILOG (URL nova), ANTAQ datasets, demais autoridades BR.
- [ ] Considerar chave comercial (MarineTraffic/Kpler/VesselFinder/Datalastic) para AIS global.
- [ ] Agendar `scripts/snapshot_history.py` (histórico diário interrompido durante a contingência).

### 2. Republish do MCP Registry (server.json v0.3.0)
- [ ] Rodar `mcp-publisher publish` (login: GitHub `belegante-byte` — sessão JWT expirada, requer `mcp-publisher login github` interativo).
- [ ] Validar que a nova versão mantém `remotes` e `packages` e reflete a descrição honesta.
- NOTA: o schema oficial NÃO tem campo `status` (active/hidden) — remover a listagem = ação no portal do registry, manual.

### 3. PyPI
- [ ] Decidir: yank das versões ou publicação corrigida com bump de versão.
- [ ] `aetherx-mcp` e `aetherx-oracle` com descrições/proveniência já corrigidas no código.
- [ ] Publicação = manual (twine) ou pipeline. Chave `PYPI_TOKEN` existe local.

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

1. **Fonte real conectada com `data_source=live:<fonte>` em produção** — FEITO para BRSSZ/BRPNG.
2. Backfill/validação de que os números mudam (delta real entre janelas) — acompanhar via `port_metrics_history`.
3. Depois disso, reativar RapidAPI (novo example), MCP Registry (republish v0.3.0) e agregadores.