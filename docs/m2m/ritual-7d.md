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
|---|---|---|
| first→second alta (≥40%) | sinal de utilidade real |
| first→second baixa | um utilitário de teste, não de valor |
| repeat→paid | sinal econômico (cenário D) |

**Pergunta do ritual (desde D2):**
> "O comportamento observado no D2 persiste depois do pico inicial de descoberta?"

Persistência observada por vários dias = **uso M2M recorrente** (mais valioso que first call única).

**Definições (precisão metodológica):**
- `new = unique_machines − repeat_machines` **NÃO** significa "máquinas descobertas hoje". Significa
  "máquinas que, **nesta janela de boot**, estão classificadas como unique e ainda não como repeat".
  No D7, preservar essa distinção — contadores em memória impedem função temporal (não virar falsa série).
- `returning = repeat_machines` (máquinas com ≥2 chamadas no boot).
- Mapeamento canônico de canais: **RapidAPI → `rest`** (paths `/v1/`) · PyPI/GitHub install/clone
  **não** geram chamada de servidor (repo/webhook = 0 por padrão).
- **21 máquinas MCP ≠ 21 clientes.** São identidades observadas pela instrumentação. A cadeia de adoção:
  `descoberta → 1ª chamada → 2ª chamada → repetição → consumo pago`.

**Regimes possíveis nas próximas leituras (classificar antes de concluir):**
1. Novas máquinas **continuam** + retornos **continuam** → distribuição + retenção inicial.
2. Novas **param**, retornos **continuam** → pico de descoberta acabou, mas existe persistência (**o sinal mais interessante**).
3. Novas **continuam**, retornos **param** → distribuição existe, retenção não demonstrada.
4. Ambos **congelam** → distinguir "experimento sem tráfego" de "pico de sincronização terminado" (só com gap de horas/dias).

**Sobre uso dos números (doutrina — experimento não valida produto):**
O M2M responde "existe interesse espontâneo no ecossistema?", **não** "o produto é irresistível?".
Não usar "21 MCP" para concluir que o produto já é forte: 21 ≠ 21 clientes. Máquina que
`descobre → chama → nunca mais volta` pode indicar: (1) sinal não é necessário; (2) resultado
não é útil; (3) cobertura insuficiente; (4) agente só explorando; (5) máquina de diretório/bot.
**Observabilidade** (série B, logs `AETHERX_METRIC`): (4) ≈ máquinas com só 1 chamada; (5) ≈ assinatura
de UA + burst único; (1)/(2) não observável por calls — exige Product Value Audit; (3) parcial
(padrão de repetição inter-portos). `descobre → volta amanhã → volta de novo` = evidência de
**utilidade recorrente**.

**Barra de produto pós-D7 (não tocar antes):** "Se eu remover o Aether-X, uma máquina perde uma
informação que **altera uma decisão**." O problema atual não é a API — é **densidade de valor** e
**cobertura de decisão** (16 portos ≠ dependência em supply chain), além de origem do sinal
(moeda: dado → normalização → histórico → detecção de regime → sinal proprietário → validação → Oracle).

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
| D2 | Cursor published; PRs #14670/#403 corrigidos p/ repo público; L1 fechado | 1 | 24 | 13 | 13 | **External Second Call Rate = 0.54** (n=24). MCP first=21, second=12 (0.57); seo first=2, second=1; discovery first=1. Janela de leitura = **~2h de uptime** (redeploy reseta contadores) — não é 24h. Bots excluídos: 80 calls/6 máquinas (liveness). Top path `/mcp` (182). Paid=0. **Sem alteração de produto** (regra D1–D7 respeitada). |
| D3 | — (mesmo boot do D2; uptime +143s (~2,4 min)) | 0 | 0 | 0 | 0 | **LEITURA SEM DELTA** — estatisticamente ainda dentro da mesma janela de observação do D2 (contadores e uptime idênticos fora do relógio). **Sem intervenção.** `new`/`returning`/intervalo first→second: **n.d./gap conhecido** — timestamp por máquina não é exposto; só nos logs `AETHERX_METRIC` do Railway (série B no D7). |

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

### Nota de rigor estatístico (2026-09-19)

Observação pós-redeploy (~69 min de uptime): `mcp: unique 16, repeat 11` (equivalente a 68,8% na janela de boot). **Formulação correta:** "11 das 16 máquinas MCP observadas foram classificadas como repeat pela instrumentação atual nesta janela de boot" — evidência de **comportamento de retorno**, NÃO inferência de "valor percebido" (uma máquina pode retornar por razões técnicas). Contexto mais informativo que o D2 original: produto com dados reais, calibração, ANTAQ, domínio próprio, registry v0.4.2, public-apis aceito.

**Próxima pergunta (próximo nível de instrumentação):** "o que exatamente essas máquinas fazem depois de encontrar o Aether-X?" — ferramentas invocadas, resultados, latência, erros.

**Congelamento (decisão 2026-09-19):** não perseguir mcp.so/PulseMCP, não adicionar superfícies novas, não fazer marketing. Observar se o comportamento de retorno sobrevive por horas/dias após o efeito de sincronização/indexação inicial. Se `repeat` crescer enquanto `unique` estabiliza → regime 2.

**Zero chamadas em 7 dias ≠ fracasso do produto.** 7 dias é janela de aquisição, não validação definitiva.

## Saída do ritual

Relatório D7 (`docs/m2m/relatorio-d7.md`): first/second/repeat por canal + atualizar
`surfaces.csv` (status/`first_calls`/`repeat_calls`) + fechar os 4 valores econômicos pendentes
(Railway, comissão RapidAPI, outros custos, valor-hora) + baseline econômica v2 combinada com comportamento real.
Duas séries no relatório — **A**: observação do boot · **B**: eventos persistidos (logs duram);
**não misturar**, e **não corrigir** contadores em memória durante o experimento.

**Entregáveis pós-D7 (após a decisão de dobra):**
1. **Product Value Audit** — por campo (`congestion_score`, `eta_delay_days`, `waiting_vessels`,
   `freight_volatility`, `demurrage exposure`, `updated_at`): *"muda alguma decisão?"*; por endpoint:
   *"por que uma máquina deveria chamar isto amanhã de novo?"*. Se não há resposta forte → problema.
2. **Red Team do Produto** — assumir agente externo hostil recém-descoberto e responder sem gentileza:
   *"por que eu usaria isto em vez de qualquer outra fonte?"*. Se fraca, **não maquiar** — identificar
   qual camada precisa ficar mais forte: sinal, cobertura, temporalidade, confiança, explicabilidade ou ação.

Objetivo referência: não "um MCP que máquinas conseguem encontrar", e sim **"um sinal que máquinas
têm motivo para continuar consultando"**.