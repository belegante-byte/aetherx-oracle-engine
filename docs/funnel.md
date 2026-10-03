# Funil de Adesão — Medição por Canal

> Norte-estrela (30 dias): **usuários externos com ≥2 chamadas em 7 dias**.
> Meta de saída: `0 → 10 → 50 → 100` usuários. Objetivo inicial não é receita — é descobrir qual canal gera os primeiros usuários.
>
> **Modelo de aquisição M2M:** a lista de prospects humanos foi substituída por superfícies de integração — ver [`m2m/README.md`](m2m/README.md) e [`m2m/surfaces.csv`](m2m/surfaces.csv).
>
> **Protocolo do experimento de 7 dias:** [`m2m/ritual-7d.md`](m2m/ritual-7d.md) — dia 0 = baseline, só distribuição, nenhuma mudança de produto.
> **Métrica decisiva:** *External Second Call Rate* (`repeat_machines`/`unique_machines`, do `/internal/metrics`).
> **Bots/crawlers não contam:** canais `bot` são medidos à parte e excluídos do funil (SentinelOracle, mcpbeat, Googlebot, …).

## Ritual
A cada **7 dias**, preencher a tabela abaixo e guardar o snapshot. Fonte de cada métrica indicada na coluna "Fonte".

| Canal | Detail | Fonte de dados |
|---|---|---|
| **RapidAPI** | page views, impressions, subscribes, chamadas, key ativas | RapidAPI Analytics (painel do listing) |
| **PyPI SDK** (`aetherx-oracle`) | downloads 7d | https://pypistats.org/packages/aetherx-oracle |
| **PyPI MCP** (`aetherx-mcp`) | downloads 7d | https://pypistats.org/packages/aetherx-mcp |
| **MCP remote** (`/mcp`) | initialize/tools calls, machines únicas | `/internal/metrics` + logs `AETHERX_METRIC` (serviço `aether-x-oracle`) |
| **SEO** | landing + páginas de intenção + portos | logs `AETHERX_METRIC` channel=seo (`/port-congestion-*`, `/mcp-page`, etc.) |
| **Display/discovery machines** | LLM bots, liveness, crawlers | logs `AETHERX_METRIC` channel=mcp/... (ex.: SentinelOracle, mcpbeat) |
| **GitHub** | visitantes/clones por repo | GitHub Insights (cada repo) |
| **M2M surfaces** | submissões por superfície → first/repeat calls | [`m2m/surfaces.csv`](m2m/surfaces.csv) (colunas `first_calls`/`repeat_calls`) |
| **Marketplaces MCP** | Glama, Smithery, PulseMCP, mcp.so | painéis de cada plataforma |

## Tabela semanal

### Snapshot 2026-10-03 (semana 27/09–03/10) — baseline pós-deploy `9f9ee7c1`

Fontes: logs Railway `AETHERX_METRIC` (janela ~46 min pós-boot: 88 eventos, 12 máquinas únicas) + pypistats.org API. Bots/crawlers excluídos do funil por política (`mcpbeat` 30, `SentinelOracle` 12, `Golemreach` 4, `agent-market-probe` 3, `Googlebot` 2 = 5 máquinas, 51 eventos).

| Canal | Visitors | Installs | First Call | Repeat (≥2/7d) | Paid |
|---|---:|---:|---:|---:|---:|
| RapidAPI | n/d¹ | n/d¹ | n/d¹ | n/d¹ | 0 |
| PyPI SDK (`aetherx-oracle`) | — | 25² | — | — | 0 |
| PyPI MCP (`aetherx-mcp`) | — | 61² | — | — | 0 |
| MCP remote (`/mcp`) | 4³ | — | 4³ | n/d⁴ | 0 |
| SEO | 2⁵ | — | 7⁶ | n/d⁴ | 0 |
| GitHub | n/d⁷ | — | — | — | — |
| Outbound | 0 | — | 0 | — | 0 |

Notas de fonte:
- ¹ RapidAPI contabiliza no painel do listing (page views / impressions / subscribes / chamadas / keys ativas); não acessível por CLI — preencher manualmente.
- ² `pypistats.org/api/packages/<pkg>/recent` → `last_week`. `aetherx-oracle`=25 (last_day=1, last_month=426); `aetherx-mcp`=61 (last_day=4, last_month=776).
- ³ Máquinas MCP distintas não-bot: `node`(1), `capdiff`-observatory(1), `python-sdk/aiohttp`(1), `curl`(1).
- ⁴ Janela de ~46 min insuficiente para repeat de 7d; contadores `/internal/metrics` resetaram no deploy de hoje. Re-medir em **2026-10-10** com log contínuo.
- ⁵ Visitantes humanos reais por UA de browser: Chrome/Windows(1) + Safari/Mac(1).
- ⁶ Eventos `channel=seo`: landing `/`(2), `/port-congestion-ningbo-zhoushan`(1), `/port-congestion-singapore`(1), `/robots.txt`(1), `/sitemap.xml`(1), google-verification(1 → **404, bug P1-novo**).
- ⁷ GitHub Insights por repo — preencher do painel.

### Snapshots anteriores

_(nenhum — este é o primeiro preenchimento; a tabela estava vazia desde a criação do arquivo)_

## Heurística de decisão (depois de ~30 dias)
- Canal com ≥10 usuários e ≥30% de repeat → **dobrar esforço**.
- Superfície M2M com ≥1 first call externa em 7d → **avançar**; zero após submissão publicada → **depriorizar**.
- Não ampliar SDKs (Node/TS etc.) nem produzir conteúdo em massa até existir evidência de qual canal converge.

## Fronteiras atuais de medição
- O endpoint REST passa pelo gateway RapidAPI (RapidAPI já contabiliza tudo). O `/mcp` remoto e os paths de SEO/discovery são diretos no Railway e agora instrumentados: **cada requisição de máquina gera um log `AETHERX_METRIC`** e contadores em `/internal/metrics` (protegido pelo proxy secret; em memória, resetam no deploy).
- Contadores de `/internal/metrics` são do processo atual; o log `AETHERX_METRIC` no Railway é a fonte durável para janelas longas.
- Landing/SEO sem pixel de analytics (sem cookie/GDPR). Aproximação via UA nos logs é suficiente para o funil inicial.