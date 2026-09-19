# Market Scan — Setembro 2026 · A/B (decisão pós-D7)

> Contexto: varredura externa rodada em 2026-09-18 para fundamentar a dobra do produto.
> Fontes: MCP Registry oficial (crawl 1.128 servidores únicos) · mcpbeat.com (33.465 servidores
> rastreados, installs reais/semana por npm/PyPI, rebuilt 2026-09-18 04:37 UTC) · Gartner ·
> MarketsandMarkets · mcpmanager.ai (volume de busca global) · scans no GitHub/registry/web.
> Regra: **inputs aqui não tocam o artefato medido até o D7** (firewall do experimento M2M).

## 1. Nicho port-risk: competidores e dono

**Registry oficial (oficial = onde clientes descobrem hoje):** entre ~1.128 servidores únicos
amostrados, praticamente **nenhum** de risco portuário/congestion. `aetherx-mcp`
(`io.github.belegante-byte/aetherx-mcp`, v0.2.1 active, remote streamable-http) é praticamente o
único remote de risco portuário publicado — vantagem de posição existente, não conquistada.

**Fora do registry (competição real):**

| Player | Cobertura | Observação |
|---|---|---|
| SupplyMaven MCP | 26 portos + GDI global; "level: ELEVATED"; port disruption (7 US) | Competidor direto mais próximo; 1 star; raso em cobertura/detalhe |
| Datalastic MCP | 25 tools; 750k navios; posições/port data/weather | Vessel data, não risco de decisão |
| tools-mcp/vessel-traffic-mcp | AIS + schedules + `schedule_delay_predict`; BYOK; 92 commits | Mesmo playbook nosso (registry + llms.txt + landing); sem risco/demurrage |
| Kpler MCP (jan/2026) | Inteligência comercial/marítima proprietária, gov/defesa | Incumbente grande entrando via MCP |
| GoComet (web) | Congrats index 700+ portos, AIS+carrier+ML, **gratuito** | Camada de *dados*, sem objeto de decisão agent-native |
| Portcast (web) | Snapshots P50/P75/P90, long-tail; inclui Santos/Rio | Idem — dados públicos acessíveis, não MCP |

**Conclusão:** a camada "dados de congestionamento" é competitiva e crescente; a camada
"**decisão agent-native com histórico**" está sem dono. O SupplyMaven é o mais perto e é raso.

## 2. O que recebe adoção recorrente em MCP (installs reais/semana — mcpbeat)

| Padrão | Exemplo | Installs/semana |
|---|---|---|
| Dev-tool commodity | Playwright, Chrome DevTools, Storybook | 1,5–6M |
| Docs canônicos | Context7 (remote #1) | 1,05M |
| **Estado canônico de um lugar/mercado** | UK Property 3,7k · PubMed 5,9k · Amazon data 6,3k · **IBGE Brasil 1,06k** · UK Legal 440 | 0,4–6,3k |
| **Workflow transacional** | warpfreight quote→book→track (LTL/FTL) 1,3k · Twilio · Stripe | 1–260k |
| **Dado machine-payable** | Run402 (x402 pay-per-call) 3,8k · ibanforge · TensorFeed | 0,3–3,8k |

**"Viralizar" em M2M ≠ viral humano.** Máquina adota quando é invocada em workflow de alta
frequência, valor óbvio na 1ª chamada, dado que o modelo não tem, integração zero. Três padrões
que convertem: **estado canônico de um lugar**, **workflow transacional**, **dado pagável por máquina**.

## 3. Demanda de mercado (por que o timing é agora)

- Gartner (abr/2026): SCM com agentic AI **US$2B → US$53B por 2030 (CAGR 93,5%)**; adoção 5% → 60%.
- Agentic AI SCM (MarketsandMarkets): **US$1,85B → US$88B (CAGR 74%)** 2025→2032.
- Vertical agents = maior CAGR das ofertas (62,7%); 42/50 dos MCP mais buscados são para engenheiros.
- **Brasil lidera adoção enterprise de agentes** (Jitterbit/501 CIs: 9% das empresas já operam
  >100 agentes; planejam dobrar até 2027).
- Demanda BR já provada: **MCP Brasil 1,7k stars** (70 APIs públicas BR p/ agentes); `ibge-br-mcp`
  1,06k installs/semana mesmo com 7 stars.

## 4. Realidade atual do produto (firewall honesto)

- Dataset: **seed estática de 16 portos** (`src/engine/init_prod_db.py`), DuckDB, valores fixos.
- Demurrage = derivado sintético (`DEMURRAGE_BASE * (1+1.25*score)`) · trend = reversão à média com
  constante 48h (`risk_model.py`). Sem fonte viva contínua nem histórico.
- `santos_scraper.py` = dados mockados (line-up fixo), não scraper real.
- Consequência: o pipeline `dado → normalização → histórico → regime → sinal proprietário →
  validação → Oracle` **ainda não existe**. Esse é o moat temporal a construir — e a justificativa
  central de "começar a persistir já".

## 5. Ficha A — Port-risk como decisão + moat temporal

**Proposta:** evoluir o `aetherx-mcp` de "dados de 16 portos" para **estado de decisão LatAm**:
- Objeto de risco: `risk_state: ELEVATED · direction: DETERIORATING · expected_delay · confidence ·
  recommended_action (review ETA / alternate routing)` + exposição em US$.
- **Histórico diário acumulando desde já** (via snapshot de `port_metrics` → tabela de séries) →
  detecção de regime proprietária que ninguém copia rápido.
- Cobertura: 16 → ~40–60 portos estratégicos do Atlântico Sul + hubs globais críticos; prioridade
  LatAm (Santos, Paranaguá, Itajaí, Rio, Suape, Manaus, Buenos Aires, Montevidéu, San Antonio,
  Colón, Panamá, Valparaíso, Callao, Manzanillo...). Concorrentes globais cobrem 26–700 portos
  **rasos**; nosso diferencial é decisão + profundidade LatAm + gratuidade.

**Valida o que falta:** responder "por que uma máquina chamaria isto amanhã de novo?" — porque o
estado **mudou** desde ontem (histórico + regime), não porque o seed é bonito.

**Custo/Escala (estimativa):** ~1–2 semanas de engenharia ligeira (schema de séries + snapshot
diário + objeto de decisão + cobertura). Storage trivial (DuckDB/SQLite em Rails volume).

## 6. Ficha B — Brasil/logística canônico p/ agentes

**Proposta:** servidor MCP novo (separado, para não contaminar o funil do `aetherx-mcp`):
wrapper remoto, gratuito, sem chave, em tempo real, de dados oficiais de comércio/logística BR —
UN/LOCODE BR, NCM, câmbio/B3, CNPJ/CEI, Aduana/ANTAQ/Siscomex/rastreio. Padrão **estado canônico
de um lugar**, que é o que mais converte installs (IBGE 1,06k/wk; UK Property 3,7k/wk; Amazon 6,3k/wk).
A comunidade prova a fome (BrasilAPI, MCP Brasil 1,7k stars), mas ninguém faz a versão **remota +
tempo real + sem key + agent-native** — esse é o formato que aparece nos "best of" e que agente usa
todo dia (regime 2).

**Valida o que falta:** cobertura de decisão BR (identificadores + câmbio + tarifa) para agentes de
trade/aduana/logística; fonte canônica única em vez de N fontes frágeis (portal gov down, PDFs).

**Custo/Escala (estimativa):** ~1–3 semanas por fonte integrada (BrasilAPI é grátis e agrega CNPJ/CEP/
câmbio/holidays/IBGE; ANTAQ/Siscomex exigem parsing). Servidor separado publica depois do D7.

## 7. Plano operacional: começar já, expor no D7

| Agora (não contamina a medição) | D7 em diante (libera pro ecossistema) |
|---|---|
| Snapshot diário de `port_metrics` → histórico (moat temporal começa) | Nova versão do `aetherx-mcp` (objeto de decisão + cobertura) |
| Schema de séries/regime (análise/design, sem endpoint novo) | Publicar servidor B (Brasil canônico) |
| Docs (este + fichas de viabilidade + Red Team) | Product Value Audit + Red Team formal em `relatorio-d7.md` |
| Mapa de fontes reais (AIS público, ANTAQ, Marinha) p/ substituir dados sintéticos | Monetização: pay-per-call / RapidAPI tiers |

**Regra da dobra:** nada do acima toca `/mcp`, `/v1/` nem os seeds em produção até o relatório D7
— o funil D3→D7 continua comparando o mesmo artefato.