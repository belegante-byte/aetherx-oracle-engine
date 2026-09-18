# Estratégia de Adesão — 30 dias

> Plano de distribuição/adesão proposto (2026-09-18). Princípio central: **não "fazer marketing do Aether-X", mas criar mecanismos que coloquem o produto diante de pessoas/agentes que já procuram exatamente esse tipo de dado.**

## Mudança de mentalidade
Funil de **INTENT → DISCOVERY → EXPERIMENT → VALUE → ADOPTION** em vez de **BRANDING → AWARENESS → MAYBE INTEREST**.

Cada alteração deve responder: _"Isso aumenta a probabilidade de alguém descobrir, experimentar ou continuar usando o Aether-X?"_ Se a resposta for não, fica fora do sprint de adesão.

## Motores dos próximos 30 dias
| Prioridade | Motor | Objetivo |
|---|---|---|
| **P0** | MCP discovery | Fazer agentes descobrirem o Aether-X |
| **P0** | Developer discovery | Fazer desenvolvedores chegarem ao SDK |
| **P1** | Use-case SEO | Capturar buscas com intenção |
| **P1** | Outbound B2B | Colocar o produto diante de potenciais usuários |
| P2 | Multi-language SDK | Reduzir barreira de integração |
| P2 | Branding próprio | Aumentar confiança e autoridade |

NÃO começar por Node/R/mais SDKs antes de saber qual canal gera os primeiros usuários.

## Meta operacional (30 dias)
```
VISITOR → DISCOVERY → INSTALL/SIGNUP → FIRST CALL → SECOND CALL → REPEATED USAGE → PAID
```
**North-star**: usuários externos com **≥2 chamadas em 7 dias** (1 chamada = curiosidade; 2 = experimentação; recorrente = utilidade).

Hoje: `external users = 0`. Objetivo de saída: `0 → 10 → 50 → 100` (não receita).

## 1. P0 — MCP Discovery
Infra pronta (Registry + PyPI + Remote MCP + 3 tools). Falta distribuição da existência.

- Alvos: PulseMCP, Smithery, mcp.so, ToolFinder, Awesome Remote MCP Servers, outros diretórios MCP.
- Regra: **não cadastrar dezenas de diretórios sem medir resultado** (5–10 agregadores → tracking → medição).

## 2. MCP como "produto demonstrável"
Criar página **Aether-X MCP** com:
- O que ele faz: "Query real-time port congestion, ETA delays, vessel queues and modeled demurrage exposure through an MCP-compatible AI agent."
- Available tools: `get_port_risk`, `get_ports_risk`, `get_port_trend`.
- Exemplos:
  - "What's the congestion risk at Santos?"
  - "Compare Santos, Shanghai and Rotterdam."
  - "Which of these ports currently has the highest modeled demurrage exposure?"
  - "Show me the 72-hour congestion trend for Santos."

## 3. P0 — Developer Discovery (Python)
Dominar buscas: `python port congestion api`, `python port risk api`, `port congestion API`, `shipping congestion API`, `port delay API`, `demurrage API`, `ETA delay API`.
Primeiro com conteúdo extremamente específico, não publicidade.

### 10 páginas de intenção (não um blog inteiro)
1. Port Congestion API
2. Port Congestion API for Python
3. Santos Port Congestion API
4. Container Port Delay API
5. Port ETA Delay API
6. Demurrage Exposure API
7. Port Congestion MCP Server
8. Port Intelligence for AI Agents
9. Port Congestion Monitoring with Python
10. Global Port Risk API

Estrutura de cada página: `problema → explicação → exemplo → API response → Python code → MCP → "Try Aether-X"`.

### Conteúdo técnico, não publicitário
Ex.: "How to monitor Santos port congestion with Python" + bloco de código real `OracleClient` + exemplo de response + "The same data can be consumed through MCP by AI agents."

### Hello World (Time to First Successful Call < 3 min)
`pip install aetherx-oracle` → `OracleClient(api_key=...)` → `client.get_port_risk("BRSSZ")`.

## 4. Free tier como porta de entrada
Posicionar BASIC $0 não como "Basic", mas **"Free Developer Tier — 50 API calls/month"**. Funil: anonymous visitor → developer → API key → 50 calls → aha moment → paid.

## 5. RapidAPI como distribuição
Tratar o listing como landing page no marketplace:
- Título: **"Aether-X Port Congestion Oracle — Port Risk, ETA Delay & Demurrage API"**
- Descrição iniciando com checklist: congestion score, ETA delay, waiting vessels, freight volatility, demurrage exposure, 24/48/72h trend, batch queries.

## 6. Explorar o Batch como diferencial comercial
`/v1/ports-risk` (compare 20 ports em 1 chamada) é mais próximo de workflow empresarial que o single-port. Criar conteúdo "Compare Global Port Congestion with One API Call".

## 7. P1 — Outbound B2B
Lista de ~50 prospects em 4 segmentos:
- **A — Supply Chain** (20): freight forwarders, importadores, exportadores, logistics intelligence.
- **B — Maritime** (10): ship brokers, vessel operators, port consultants, maritime analytics.
- **C — Quant/Finance** (10): commodity trading, systematic funds, freight derivatives, commodity research.
- **D — AI/Developers** (10): agent developers, MCP developers, AI infrastructure.

Abordagem: "Estamos disponibilizando uma API/MCP que transforma sinais de congestão portuária em dados estruturados. Temos Santos, Shanghai, Rotterdam, LA etc. e um free tier. Posso te mandar um exemplo?" — objetivo: **primeira utilização**, não venda imediata.

## 8. Aether-X Challenge
"MCP can find highest port congestion risk in 30 seconds" — página com 5 portos, usuário consulta, "Build this yourself with the Aether-X API." Chamar atenção em GitHub, LinkedIn, Reddit, Hacker News, Dev.to, comunidades MCP.

## 9. LinkedIn técnico
Posts pequenos e com dado, não institucionais:
1. "What does a port congestion score actually tell you?"
2. "We exposed port congestion intelligence through MCP." (exemplo de agente)
3. "Santos vs Shanghai vs Rotterdam: what the API sees."
4. "One API call, five ports."
5. "Can demurrage exposure be represented as an API signal?"

## 10. GitHub como aquisição
README como landing page para dev: título → Quick Start (Python) → MCP → REST → Supported Ports → Pricing → Documentation → "Try the Free Tier".

## 11. Marca própria (P2, depois de tração)
`aether-x.com` + `api.aether-x.com` / `docs.aether-x.com`. Não virar projeto de semanas.

## 12. Node/TypeScript (P2, só com evidência)
Ordem: Python → MCP → REST → Node/TS. Próximo SDK: `@aetherx/oracle` — só quando houver dados.

## Plano dos próximos 7 dias
- **DIA 1** — SDK: confirmar 0.4.0, testes, PyPI, README. llms.txt: adicionar RapidAPI URL.
- **DIA 2** — MCP: página "Aether-X MCP" (Install, Tools, Examples, Remote MCP, PyPI, Registry, GitHub).
- **DIA 3** — GitHub: reescrever README para aquisição (Quick Start, 3 exemplos, batch, trend, MCP, pricing, links).
- **DIA 4** — SEO: publicar 1. Port Congestion API, 2. Santos Port Congestion API, 3. Port Congestion Python.
- **DIA 5** — Distribution: cadastrar/verificar PulseMCP, Smithery, mcp.so, ToolFinder, Awesome Remote MCP.
- **DIA 6** — Outbound: montar 50 prospects (20 logistics, 10 maritime, 10 quantitative, 10 AI/dev).
- **DIA 7** — Measurement: tabela por canal (Visitors, Installs, Calls, Repeat, Paid) para RapidAPI, PyPI, MCP, SEO, GitHub, Outbound.

> Nota: muito do DIA 1 já está concluído (SDK 0.4.0 publicado; llms.txt com RapidAPI URL; MCP Registry live). Ver `docs/report-distribuicao-estado.md`.

## Backlog consolidado
- 🔴 **AGORA**: SDK 0.4.0 (feito) · README/GitHub · llms.txt (feito) · MCP discovery · 3 páginas SEO de alta intenção · 50 prospects · instrumentação do funil.
- 🟡 **DEPOIS**: domínio próprio, mais conteúdo, Node/TS SDK, mais agregadores, casos de uso, MCP Registry amplification.
- 🟢 **SOMENTE DEPOIS DE TRAÇÃO**: novos portos, novos endpoints, novos mercados, modelo preditivo mais sofisticado, dashboard, SaaS completo.

## Princípio final
Executar **3–5 canais simultaneamente durante 30 dias e medir de onde vêm as primeiras chamadas externas**, em vez de adivinhar o canal vencedor. RapidAPI + PyPI + MCP Registry já dão base para esse experimento. Não fazer desenvolvimento por desenvolvimento.