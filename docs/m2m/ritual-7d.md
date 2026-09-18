# Ritual M2M — 7 dias (dia 0 = baseline)

> Regra dura: **nenhuma alteração de produto durante os 7 dias, exceto correção de bug.**
> Distribuição é a única atividade. O objetivo é colher (a) first calls, (b) second calls,
> (c) repeat usage por canal — e, ao final, **combinar economics + comportamento real**.

## Dia 0 — baseline registrada

| Métrica | t=0 |
|---|---|
| `external_first_calls` | 0 |
| `external_second_calls` | 0 |
| `external_repeat_users` | 0 |
| `paid_users` | 0 |
| `revenue` | US$ 0 |
| Custos de infraestrutura | ≈ US$ 0–20/mês [pendente] |
| HF / PyPI / GitHub | US$ 0 |
| Produto / API / MCP | live |
| Distribuição M2M | em execução |
| Testes | 42/42 — commit `216d1d3` |

### Distinção obrigatória
```
BOT / CRAWLER            ≠          EXTERNAL MACHINE USER
SentinelOracle, mcpbeat,          agente/software/px de verdade
Googlebot, liveness bots           chamando o produto
```
Bots/crawlers não são aquisição. São medidos à parte (channels `bot`) e **não entram** no funil M2M.

## Funil (canal → paid)

```text
SURFACE
   ↓
DISCOVERY        (impressões, page views, openops)
   ↓
DOCUMENTATION    (llms.txt, docs, README, SEO pages)
   ↓
FIRST MACHINE CALL
   ↓
SECOND MACHINE CALL
   ↓
REPEAT USAGE
   ↓
PAID
```

> 1000 visitas e 0 calls ≠ 20 visitas e 5 calls. A segunda é mais valiosa.

## Métrica decisiva

**External Second Call Rate** = `repeat_machines[channel] / unique_machines[channel]`
(fonte: `/internal/metrics`, com proxy secret, ou logs `AETHERX_METRIC` channel≠bot).

| Valor | Leitura |
|---|---|
| first→second alta (≥40%) | sinal de utilidade real |
| first→second baixa | um utilitário de teste, não de valor |
| repeat→paid | sinal econômico (cenário D) |

## Dias 1–7 — só distribuição

**Lote 1 (formulários, ~2–5 min cada — parte do usuário):**
1. mcp.so → https://mcp.so
2. mcpservers.org → https://mcpservers.org
3. Cursor MCP directory → https://cursor.directory/mcp
4. Continue.dev Hub → https://hub.continue.dev
5. OpenTools → https://opentools.com

(Detalhes por lote: `docs/m2m/submissions.md`.)

**Deixar trabalhando (sem ação diária):** MCP Registry · Glama · Smithery · PulseMCP ·
awesome-remote-mcp-servers (PR #403) · RapidAPI · PyPI SDK/MCP · GitHub · Hugging Face · SEO (16 portos + sitemap).

## Log diário

| Dia | Superfícies submetidas | Discovery | First calls | Second calls | Repeat users | Notas |
|---|---|---|---|---|---|---|
| D0 | — | — | 1 | 0 | 0 | **Marco D0**: 1ª external machine call (channel `mcp`, path `/mcp`, `ua=Python/3.11 aiohttp/3.14.3`, `ip_hash=a66721dc1c181b2e`, ts ≈ 1789751525, slot Brasil). Evento preservado; sem identificação, sem conclusão. |
| D1 | — | 0 | 1 | 1 | 1 | A máquina do D0 **voltou** — 2ª chamada `/mcp` (mesma UA, mesmo `ip_hash`, ts +569s). Funil MCP: first=1, second=1, External Second Call Rate=1.0 (**observação única, sem conclusão**). Bots exc luídos (mcpbeat, SentinelOracle — liveness). `seo`=2 é ruído próprio (nossos curls de verificação). RapidAPI/PyPI/GitHub/SEO externo = 0. |

(fazer nova linha por dia; fechar tabela no D7)

## Registro do evento D0 → D1 (fac-símile preservado)

| Campo | Valor |
|---|---|
| Timestamp D0 (first) | 1789751525 (slot Brasil) |
| Timestamp D1 (second) | 1789752094 |
| Intervalo | **569 s** (< 10 min) |
| Canal | `mcp` |
| Endpoint | `/mcp` (inaugural; ferramentas invocadas: **n.d.** — log atual não registra tools) |
| Client | `aiohttp` (Python/3.11) |
| Resultado HTTP | **n.d.** (logs atuais não capturam status) |
| Região | Brasil [HIP — inferido de timezone] |
| Classificação | external machine |
| Identificação | anônima (`ip_hash=a66721dc1c181b2e`) |
| Status | **observação positiva, evidência insuficiente (n=1)** |

## Comparação D0 → D1

| Métrica | D0 | D1 | Variação |
|---|---|---|---|
| External machine | 1 | 1 | — |
| Canal | MCP | MCP | — |
| First call | 1 | 1 | — |
| Second call | — | 1 | **+1** |
| Repeat | — | 1 | **+1** |
| Paid | 0 | 0 | — |
| Receita | $0 | $0 | — |

## Instrumentação operacional (autorizada; a partir de D2)

- `scripts/m2m_ritual.py` lê `/internal/metrics` com **User-Agent próprio**
  (`belegante-aetherx-operational/0.1`) → o produto o exclui dos contadores
  (token `_SELF_TOKENS`).
- **Regra:** o header serve exclusivamente para identificar tráfego
  operacional/teste interno e é **excluído dos indicadores de aquisição**,
  sem reclassificar retrospectivamente eventos já registrados (D0/D1 preservados).
- Comparações de D2 em diante são **acumulativas** (D0→D1→D2, …), não
  só "últimas 24h".

## Interpretação dos resultados

| Cenário | Observado | Provável causa | Ação |
|---|---|---|---|
| A | 0 first calls em tudo | discovery/distribution | investigar canais; não o produto |
| B | discovery abundante, 0 calls | conversão técnica: docs/CTA/setup | revisar onboarding técnico |
| C | 20 first → 0 second | valor do produto | debater hipóteses de valor |
| D | 20 first → 10 second → 5 repeat | sinal de valor real | combinar com economics → decisão de dobra |

**Zero chamadas em 7 dias ≠ fracasso do produto.** 7 dias é janela de aquisição, não validação definitiva.

## Saída do ritual

Relatório D7 (`docs/m2m/relatorio-d7.md`): first/second/repeat por canal + atualizar
`surfaces.csv` (status/`first_calls`/`repeat_calls`) + fechar os 4 valores econômicos pendentes
(Railway, comissão RapidAPI, outros custos, valor-hora) + baseline econômica v2 combinada com comportamento real.