# Aether-X — Aquisição M2M (machine-to-machine)

> O Aether-X não precisa de um vendedor humano para iniciar o relacionamento. Ele pode ser **descoberto, instalado e chamado por software**. Este diretório substitui a lista de 50 prospects humanos por **50+ superfícies de integração M2M**.

## A pergunta certa
Deixou de ser "quem eu mando uma mensagem?" e passou a ser:

> **"Onde um agente, aplicação, workflow ou desenvolvedor pode encontrar e consumir o Aether-X sem falar conosco?"**

## O funil M2M

```text
BUSCA / AGENTE / DESENVOLVEDOR
          ↓
   encontra Aether-X (registry, directory, OpenAPI, llms.txt, SEO)
          ↓
   README / Docs / Spec
          ↓
   MCP / REST / SDK  (primeira chamada)
          ↓
   segunda chamada (repetição)
          ↓
   integração própria
          ↓
   uso recorrente
          ↓
   PAID
```

## KPI principal: External Machine Calls

Não medimos seguidores, mensagens ou conexões. Medimos **chamadas de máquina externas**, por ecossistema:

```text
External discovery → external first call → second call → recurring → paid
```

Atribuição por canal:
- **RapidAPI** — painel do listing (chamadas, key ativas, subscribers).
- **MCP remote (`/mcp`)** — instrumentado no próprio serviço (`src/api/metrics.py`), exposto em `/internal/metrics`.
- **PyPI SDK/MCP** — downloads (pypistats) como proxy de install, não de uso.
- **SEO/landing** — logs de path (sem cookie).
- **GitHub** — insights de visitantes/clones.

## Os 5 canais (ver `surfaces.csv`)

| Canal | Objetivo | Superfícies |
|---|---|---|
| **MCP ecosystems** | Agente descobre e instala | Registry, Glama, Smithery, PulseMCP, mcp.so, awesome lists |
| **API aggregators** | Dev descobre e testa | RapidAPI, APIs.guru, Public APIs, Postman, apilist.fun |
| **GitHub ecosystems** | Projeto incorpora | awesome lists, topics, Sourcegraph |
| **AI agent frameworks** | Aether-X vira ferramenta de agente | LangChain, LlamaIndex, CrewAI, PydanticAI, Composio, Pipedream, n8n, Dify |
| **Data/API ecosystems** | App incorpora o sinal | Hugging Face, Kaggle, Snowflake, AWS/GCP, Zenodo, IMF PortWatch |

`surfaces.csv` é a fonte de verdade: **Ecossistema → superfície → método M2M → ação de distribuição → URL → requisitos → status → first_calls → repeat_calls → paid → notes**.

## Onde publicar vs. onde integrar

**Onde publicar** (descoberta): MCP directories, API directories, AI tool directories, GitHub lists, developer/API marketplaces, data marketplaces.

**Onde integrar** (uso por máquina): LangChain, LlamaIndex, CrewAI, PydanticAI, Composio, Pipedream, OpenRouter, n8n, Dify, StackOne.

A pergunta operacional, por superfície:

> Existe uma forma **técnica** de um usuário desse ecossistema descobrir e usar o Aether-X? Se existir, fazemos.

## SEO para máquinas (já no ar)
`/llms.txt` · `/openapi.json` · `/openapi.rapidapi.json` · `/.well-known/ai-plugin.json` · `/docs` · `/mcp-page` · `/sitemap.xml` · `/robots.txt` · **16 páginas `/port-congestion-<porto>`** · **feed público read-only `/public/ports`** (widget/embed) · **Hugging Face Space estático** (https://huggingface.co/spaces/Aether-x/aetherx-port-congestion-dashboard).

O produto deve se vender pela interface técnica: agente → "port congestion API" → Aether-X → OpenAPI → endpoint → `BRSSZ` → JSON.

## Ritual semanal (7 dias)
1. Atualizar `first_calls` / `repeat_calls` por superfície (fonte na coluna do canal).
2. Marcar `status`: `not_started → submitted → live → generating`.
3. Regra de decisão: superfície com ≥1 first call externa em 7d → **avançar**; zero após submissão publicada → **depriorizar**.
4. Não abrir SDKs novos nem produzir conteúdo em massa até evidência de canal.

## Fronteiras de medição
- REST externo passa pelo RapidAPI (já contabiliza). O `/mcp` remoto é direto no Railway e agora é instrumentado.
- Contadores de `/internal/metrics` são em memória do processo (resetam em deploy); o log estruturado (`AETHERX_METRIC`) é a fonte durável no Railway.
- Sem pixel/cookie: atribuição de SEO é aproximada por path.
