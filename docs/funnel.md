# Funil de Adesão — Medição por Canal

> Norte-estrela (30 dias): **usuários externos com ≥2 chamadas em 7 dias**.
> Meta de saída: `0 → 10 → 50 → 100` usuários. Objetivo inicial não é receita — é descobrir qual canal gera os primeiros usuários.

## Ritual
A cada **7 dias**, preencher a tabela abaixo e guardar o snapshot. Fonte de cada métrica indicada na coluna "Fonte".

| Canal | Detail | Fonte de dados |
|---|---|---|
| **RapidAPI** | page views, impressions, subscribes, chamadas, key ativas | RapidAPI Analytics (painel do listing) |
| **PyPI SDK** (`aetherx-oracle`) | downloads 7d | https://pypistats.org/packages/aetherx-oracle |
| **PyPI MCP** (`aetherx-mcp`) | downloads 7d | https://pypistats.org/packages/aetherx-mcp |
| **MCP remote** (`/mcp`) | initialize/tools calls | Logs do Railway (serviço `aether-x-oracle`) |
| **SEO** | landing + páginas de intenção acessos | Railway logs (paths `/port-congestion-api`, `/santos-port-congestion-api`, `/port-congestion-python`, `/mcp-page`) |
| **GitHub** | visitantes/clones por repo | GitHub Insights (cada repo) |
| **Outbound** | enviados → respostas → conversas → churn | planilha de prospects |
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
- Canal com zero first call → **pausar**.
- Não ampliar SDKs (Node/TS etc.) nem produzir conteúdo em massa até existir evidência de qual canal converge.

## Fronteiras atuais de medição
- O endpoint REST passa pelo gateway RapidAPI (RapidAPI já contabiliza tudo). O `/mcp` remoto é direto no Railway (sem contador). Para "first call / repeat" de agentes, o caminho confiável hoje é o log do Railway filtrado por `/mcp` e sessões `mcp-session-id`.
- Landing/SEO sem pixel de analytics (sem cookie/GDPR). Aproximação via logs de path é suficiente para o funil inicial.