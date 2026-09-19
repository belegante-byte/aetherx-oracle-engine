# Relatório de Estado — Aether-X Port Congestion Oracle

> Gerado em 2026-09-18. Objetivo: contextualizar assistentes/parceiros sobre o estado atual e apoiar a estratégia de distribuição/adesão.
> **Atualização 2026-09-19**: domínio de marca no ar (`aetherx.aether-grid.io`), Google Search Console verificado, sitemap enviado, registry republicado v0.4.2 apontando para o novo domínio.

## 1. Contexto e objetivo
Produto: **Aether-X Port Congestion Oracle** — API preditiva de congestão portuária, atraso de ETA e estimativa de demurrage diária, para trade global, supply chain e finanças quantitativas. Já está **publicado, monetizado e registrado** nos principais canais. A prioridade número 1 agora é **ADESÃO/DISTRIBUIÇÃO (gerar usuários e consumo real)**.

- Hoje há **2 chamadas de teste (200)** da própria conta e **zero uso externo**.
- O produto está no ar mas é novo: indexação de buscadores/marketplaces leva dias/semanas.

## 2. Produto e API
- **Base URL**: `https://aetherx.aether-grid.io` (custom domain de marca; CNAME `aetherx` → `gsxtyhih.up.railway.app` + TXT `_railway-verify.aetherx`, TLS Let's Encrypt automático, HTTP 200). O URL Railway antigo (`aether-x-oracle-production.up.railway.app`) continua funcionando em paralelo como infra.
- **Docs interativos**: `.../docs` (Swagger UI) · **OpenAPI**: `.../openapi.json`
- Endpoints REST (via gateway RapidAPI):
  - `GET /v1/port-risk?port_id=BRSSZ` — risco por porto
  - `GET /v1/ports-risk?port_ids=BRSSZ,CNSHA,NLRTM` — batch
  - `GET /v1/port-trend?port_id=BRSSZ` — projeção 24/48/72h
- Campos: `congestion_score` (0–1), `eta_delay_days`, `waiting_vessels`, `freight_volatility_index`, **`estimated_daily_demurrage_usd`**, `updated_at`.
- **16 portos** com dados: BRSSZ, BRRIO, CNSHA, CNNGB, CNTAO, SGSIN, NLRTM, USLAX, USNYC, DEHAM, MPTNG, AEDXB, KRPUS, GBLGP, ZACPT, MXZLO. Portos não cadastrados retornam estimativa global.
- **Performance**: cache em memória (0 ms local; ~200 ms de rede Brasil → N. Virginia).

## 3. Canais de distribuição (todos já vivos)
| Canal | Onde | Estado |
|---|---|---|
| **RapidAPI Marketplace** | https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle | Publicado, monetizado, health check PASS |
| **MCP Registry oficial** | `io.github.belegante-byte/aetherx-mcp` v0.2.1 | **status active** (pacote PyPI + servidor remoto) |
| **MCP servidor remoto** | `https://aetherx.aether-grid.io/mcp` | Público, streamable-http, handshake OK |
| **PyPI — SDK** | `aetherx-oracle` **0.4.0** | Publicado (Python 3.10+, extra async) |
| **PyPI — MCP server** | `aetherx-mcp` **0.2.1** | Publicado (instalação `uvx aetherx-mcp`) |
| **Landing/SEO** | `.../` (landing) + `.../llms.txt` + `.../.well-known/ai-plugin.json` | No ar, aguardando indexação |
| **Termos** | `.../terms` | Público |

- **Monetização RapidAPI**: BASIC **$0** (50 req/mês) · PRO pay-per-use **$0.02/uso** (Recomendado) · ULTRA **$29/mês** · MEGA **$199/mês** · overage **$0.001/req**. 4 features sem endpoints gateados.
- **MCP tools**: `get_port_risk`, `get_ports_risk` (batch), `get_port_trend`.
- **SDK**: `OracleClient` com sync + async (`get_port_risk`, `get_ports_risk`, `get_port_trend`), campo `estimated_daily_demurrage_usd`, timeout configurável.

## 4. Infraestrutura e operação
- **Hosting**: Railway — conta `ag@osinc.com.br`, projeto `aether-platform-api`, serviço `aether-x-oracle`. Deploy via CLI. Região N. Virginia.
  - ⚠️ **Organização (pendência longo prazo)**: o serviço `aether-x-oracle` (id `67c62a7b`) vive dentro do projeto `aether-platform-api` (id `23dd7aef`), que também abriga o serviço do app "aether-platform" (id `c52c9055`). Nada foi sobrescrito — os dois serviços são independentes. **Decisão 2026-09-19: manter como está por ora; estudar a longo prazo os prejuízos** (URL base Railway, 29 arquivos referenciando o domínio, registry/SDK/RapidAPI apontando para ele). Caminho de migração seguro se decidirmos mover: 1º fixar custom domain (`aetherx.aether-grid.io`) para a URL pública não depender do projeto; 2º criar projeto novo e mover o serviço; 3º atualizar refs que apontam para o domínio Railway interno.
- **Segurança**: rota REST protegida por `RapidAPIGuard` (requer `X-RapidAPI-Proxy-Secret`); públicas: `/`, `/health`, `openapi`, `/llms.txt`, `/terms`, `/.well-known/*`, `/docs`, `/redoc`, `/mcp*`, OPTIONS.
- **Credenciais** (nunca expor): `PYPI_TOKEN` + `RAPIDAPI_PROXY_SECRET` em `config/.env` (gitignored); cópia do proxy secret em nota-cofre local.
- **GitHub**: conta `belegante-byte` · monorepo `aetherx-oracle-engine` (+ repo `aetherx-mcp`). CLI `mcp-publisher` instalado e logado (Go 1.27).
- **Qualidade**: testes 100% verdes — API 15/15, SDK 13/13, engine 29/29.

## 5. O que ainda NÃO foi feito / riscos de descoberta
- **RapidAPI**: o backend do listing ainda aponta para o domínio Railway antigo — atualizar no dashboard do RapidAPI para `https://aetherx.aether-grid.io` (ação manual, conta RapidAPI). O listing continua funcionando (o Railway URL responde), mas por consistência de marca deve apontar para o custom domain.
- Nenhum B2B/parceiro contatado; sem listagem em marketplaces agregadores terceiros (PulseMCP, ToolFinder etc.) — agregam do MCP Registry, mas levam tempo/agendamento.
- SEO orgânico: **Google Search Console verificado (2026-09-19)**, sitemap enviado — indexação em progresso (24 URLs). Dar tempo para o Google rastrear.
- mcp.so: submissão via issue `chatmcp/mcpso#4236` aberta (0 comentários) — aguardando processamento humano; issue atualizada com repo público + registry v0.4.2.
- PulseMCP: bloqueado por Cloudflare 403 (submissões pausadas).
- Sem conteúdo/artigos/LinkedIn/GitHub stars; sem casos de uso documentados por público-alvo.
- Sem blog/tutorial/notebook demonstrando valor.
- Só 1 linguagem de SDK (Python).
- Plano gratuito existe, mas não está destacado como porta de entrada.