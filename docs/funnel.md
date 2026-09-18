# Funil de Adesão — Medição por Canal

> Norte-estrela (30 dias): **usuários externos com ≥2 chamadas em 7 dias**.
> Meta de saída: `0 → 10 → 50 → 100` usuários. Objetivo inicial não é receita — é descobrir qual canal gera os primeiros usuários.
>
> **Modelo de aquisição M2M:** a lista de prospects humanos foi substituída por superfícies de integração — ver [`m2m/README.md`](m2m/README.md) e [`m2m/surfaces.csv`](m2m/surfaces.csv).

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

## Tabela semanal (copiar)

| Canal | Visitors | Installs | First Call | Repeat (≥2/7d) | Paid |
|---|---:|---:|---:|---:|---:|
| RapidAPI | | | | | |
| PyPI SDK | | | | | |
| PyPI MCP | | | | | |
| MCP remote | | | | | |
| SEO | | | | | |
| GitHub | | | | | |
| Outbound | | | | | |

## Heurística de decisão (depois de ~30 dias)
- Canal com ≥10 usuários e ≥30% de repeat → **dobrar esforço**.
- Superfície M2M com ≥1 first call externa em 7d → **avançar**; zero após submissão publicada → **depriorizar**.
- Não ampliar SDKs (Node/TS etc.) nem produzir conteúdo em massa até existir evidência de qual canal converge.

## Fronteiras atuais de medição
- O endpoint REST passa pelo gateway RapidAPI (RapidAPI já contabiliza tudo). O `/mcp` remoto e os paths de SEO/discovery são diretos no Railway e agora instrumentados: **cada requisição de máquina gera um log `AETHERX_METRIC`** e contadores em `/internal/metrics` (protegido pelo proxy secret; em memória, resetam no deploy).
- Contadores de `/internal/metrics` são do processo atual; o log `AETHERX_METRIC` no Railway é a fonte durável para janelas longas.
- Landing/SEO sem pixel de analytics (sem cookie/GDPR). Aproximação via UA nos logs é suficiente para o funil inicial.