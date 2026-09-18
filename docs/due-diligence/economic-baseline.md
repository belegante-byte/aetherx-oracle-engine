# Due Diligence Econômica — Aether-X Port Congestion Oracle

> Linha de base econômica (t=0), antes de iniciar o ciclo de medição M2M de 7 dias.
> Compilado em 2026-09-18. Tudo que é hipótese está marcado como **[HIP]**; o que precisa
> de confirmação do operador está marcado como **[CONFIRMAR]**.

## 1. Produto

| Item | Estado |
|---|---|
| O que é | API REST + SDK Python + MCP server de congestão portuária preditiva (score, ETA delay, waiting vessels, frete volatility, demurrage modelada, trend 24/48/72h) para 16 portos |
| Estágio | Operacional, monetizado, distribuído. **Zero usuário externo real** no t=0 |
| Fase | Adoção via aquisição M2M (não vendas humanas) |
| Proposta de valor | Sinal único e barato, self-serve, primeiro consumível por IA/agentes (MCP) no segmento long-tail |
| Cliente-alvo | Desenvolvedores, agentes/workflows, quants de commodities, startups/supply-chain, plataformas de dados |
| Não é | Plataforma enterprise de visibilidade marítima (e não compete no mesmo mercado de PortCast/project44/Kpler) |

## 2. Ativo tecnológico

| Bloco | Detalhe | Estado |
|---|---|---|
| API | FastAPI, 3 endpoints (`/v1/port-risk`, `/v1/port-trend`, `/v1/ports-risk`), guard via header proxy secret | Live (RapidAPI) |
| Feed público | `/public/ports` — 16 portos JSON, sem chave (widget/embed) | Live |
| SDK | `aetherx-oracle` 0.4.0 (PyPI) — síncrono, assíncrono, batch, models tipados | Publicado |
| MCP | `aetherx-mcp` 0.2.1 (PyPI) + endpoint remoto `/mcp` + registro oficial `io.github.belegante-byte/aetherx-mcp` | Live |
| Distribuição | 16 páginas SEO por porto, sitemap 21 URLs, robots.txt, llms.txt, openapi, ai-plugin.json, HF dataset + static Space, exemplos LangChain/LlamaIndex/CrewAI/PydanticAI | Live |
| Código | Monorepo `aetherx-oracle-engine` (GitHub), MIT | Commit `216d1d3` |
| Testes | 42 (API 24, SDK 13, MCP 5) | Passando |
| Qualidade/portabilidade | Dependências leves (DuckDB, Pydantic, HTML puro); sem lock-in de nuvem |

**Riscos do ativo:**
- Dados são **snapshot modelado** (seed estático em DuckDB), não telemetria real-time. Para comprador corporate isso é o principal bloqueio.
- Único sinal/16 portos; sem séries históricas longas; sem garantia SLA/uptime formal.
- Depende de um deploy em Railway (subdomínio gratuito) e de disponibilidade do serviço — não há redundância/multi-região.

## 3. Dados

| Item | Detalhe |
|---|---|
| Fonte | Conjunto público (line-ups/telemetria portuária) consolidado em snapshot DuckDB + modelo sintético de demurrage (US$32k base × fator de congestão) |
| Cobertura | 16 portos estratégicos (BR, CN, SG, NL, US, DE, MA, AE, KR, UK, ZA, MX) |
| Cadência | Estática (recriada no seed); fallback global para portos desconhecidos |
| Licença | CC BY 4.0 (dataset HF) |
| Honestidade | Páginas expõem "computed in-process"; o dado subjacente é snapshot — deve ser comunicado assim em due diligence de comprador |

## 4. Custos

> Estrutura atual é **quase marginal-zero**. A intenção é manter custo o menor possível até haver receita.

| Item | Custo estimado | Tipo |
|---|---|---|
| Railway (container API + DB) | US$0–20/mês [HIP]; Hobby/Developer [CONFIRMAR plano e fatura] | Fixo + uso |
| Hugging Face (dataset + static Space) | US$0 | Fixo |
| PyPI (2 pacotes) | US$0 | Fixo |
| GitHub (repos privados/públicos) | US$0 | Fixo |
| Domínio/e-mail | US$0 (subdomínio Railway; e-mail contato) | Fixo |
| Dados (DuckDB, fontes públicas) | US$0 | Fixo |
| **TOTAL recorrente assumido** | **US$0–20/mês** | — |

**Custo por chamada:** ~US$0 (servidor ocioso na maior parte do tempo; consumo dentro do plano). **[CONFIRMAR]** se o plano cobra por uso/CPU acima do limite.

## 5. Pricing e unidades

Plano RapidAPI (atual): BASIC $0 (50 req/mês) · PRO $0.02/uso · ULTRA $29/mês · MEGA $199/mês · overage $0.001/req.

**Economia por unidade:**
- Custo marginal por request: ≈0.
- Margem bruta por subscriber: ~100% menos comissão da RapidAPI **[CONFIRMAR % da plataforma, HIP: 20%]**.

**Correção conceitual (break-even):** o break-even de **infraestrutura direta** pode ser atingido com ~1 assinante pago. Isso NÃO é break-even do negócio — não incorpora tempo do operador, desenvolvimento, manutenção, aquisição, suporte, dados futuros e custo de oportunidade. Usar internamente:

> **Direct infrastructure break-even: potentially 1 paid subscriber.**

(Economia do negócio só é avaliada combinando custos completos + comportamento real de aquisição do ciclo M2M.)

## 6. Mercado

| Dimensão | Leitura |
|---|---|
| Problema | Validado: congestão move frete/spreads/SLA; dezenas de players financiados |
| Concorrentes | PortCast (600+ portos, Series A, ~US$1,1M receita), SeaVantage, project44 (Ocean Insights), Kpler, Tradlinx (PCI 1.238 portos), IMF PortWatch (aberto), Traqo, SeaRates |
| Posição | Long-tail speed: self-serve, free tier, agent-first, barato — **não compete em dados/escopo enterprise** |
| TAM/SAM/SOM | Não modelado formalmente; proxy: mercado de API/data de visibilidade marítima + agent ecosystems. **[HIP]** |
| Tendência | Corrida por distribuição e dados; agentes/IA são novo canal de descoberta — a favor de quem é MCP-first |

**Fatores críticos**: credibilidade de dados (fonte/cadência) e alcance de distribuição — serão decididos nos 7 dias de M2M.

## 7. Cenários de receita (12 meses; ASSUMIDO, não previsto)

Cenários expressos em **subscribers pagos** (assinatura mensal) + overage.

| Cenário | Premissa (t≤12m) | Receita anual estimada |
|---|---|---|
| Conservador | 5 pagos (misto Pro/Ultra), pouca repetição | US$1–3 mil (~R$5–16 mil) |
| Base | 25 pagos (12 Ultra, 4 Mega, resto Pro), alguma repetição via agents | US$15–25 mil (~R$80–135 mil) |
| Otimista | 100+ pagos, embed/saas usando o feed, ~30% vindo de agentes | US$50–90 mil (~R$270–490 mil) |

Conversão BRL a R$5,45/USD [HIP]. **Decisão do ciclo M2M (7 dias):** observar qual canal gera first/repeat calls; cenário Base depende de a distribuição converter em assinatura — não de mais código.

**Regra de corte:** se após ~45–60 dias houver 0 first call externa em todos os canais, reavaliar o produto (dados/cobertura), não acrescentar features.

## 8. Linha de base (t=0) — a medir de novo a cada 7 dias

| Métrica | t=0 |
|---|---|
| Usuários externos com ≥2 chamadas/7d | 0 |
| External machines (unique, via logs) | 0 reais (apenas liveness bots SentinelOracle, mcpbeat) |
| Downloads PyPI (7d) | [numerar no 1º ritual] |
| RapidAPI: impressões/subscribes/chamadas | [painel] |
| Subscribers pagos | 0 |
| Receita | US$0 |
| Despesa fixa | US$0–20/mês [CONFIRMAR] |

## Inputs pendentes (NÃO bloqueiam o experimento)

| # | Input | Status |
|---|---|---|
| 1 | Plano/fatura Railway (US$/mês) | pendente |
| 2 | Comissão RapidAPI no listing (HIP 20%) | pendente |
| 3 | Outros custos (domínio, e-mail, serviços) | pendente |
| 4 | Valor-hora do operador (opcional) | pendente |

> Decisão: não travar a aquisição por esses valores. Serão fechados no relatório D7 do ritual M2M,
> junto da baseline econômica v2 combinada com comportamento real. Protocolo do experimento: `docs/m2m/ritual-7d.md`.