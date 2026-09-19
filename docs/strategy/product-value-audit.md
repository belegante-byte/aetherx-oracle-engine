# Product Value Audit — A/B do Signal (2026-09-19)

> Distribuição CONGELADA em v0.4.0 (Registry) / 0.2.4 (PyPI). Este documento
> é análise, não muda superfície. Objetivo: fechar o A+B e responder à pergunta
> dura — **"uma empresa de logística recebe este sinal às 08:00; toma decisão
> melhor às 08:05?"**

## 1. Fechamento do A+B: proveniência de cada campo

Pipeline executado no ciclo de 6h (`lifespan.ciclo_ingestao`):
`coletar_tudo()` → `_score_from_status()` → UPSERT `port_metrics`
→ `snapshot_history` (1 linha/porto/dia) → API lê `risk_model.calculate_port_risk`.

| Campo | Tipo de dado | Derivado de | Temporalidade |
|---|---|---|---|
| `congestion_score` | **modelado** (heurística) | contagens reais do line-up | instantânea (ciclo 6h) |
| `waiting_vessels` | **lido** (fiável) | fila real: ao_largo+esperados | instantânea |
| `eta_delay_days` | **modelado** (heurística) | waiting_vessels | instantânea |
| `freight_volatility_index` | **modelado** (proxy) | variedade de fontes+carga | instantânea |
| `estimated_daily_demurrage_usd` | **modelado** | congestion_score (US$32k base) | instantânea |
| `live.{ao_largo,esperados,atracados,programados}` | **lido** | contagens reais da fonte | instantânea |
| `data_source` / `data_source_label` | **informação** | proveniência real da fonte | — |
| `validation` | **histórico/validado** (ANTAQ) | espelho Estatístico Aquaviário, por porto/mês | **média mensal histórica** |
| `trend` (port-trend) | **sintético** | projeção de reversão à média | projeção 24/48/72h |
| portos não-BR (14) | **seed estático** | `init_prod_db.PORTS` | estática (nunca muda) |

### Como `congestion_score` é calculado (BR vivos)
`_score_from_status` (`scripts/run_ingestion_live.py:84`):
```
waiting    = ao_largo + esperados
total_fora = waiting + programados
razao      = total_fora / max(atracados, 1)
score      = clamp(0.25 + 0.35 * min(razao, 2.0), [0.05, 0.97])
```
- Não há calibração contra ground-truth; é uma pressão relativa (fora/berçado).
- Depende **inteiramente** de a fonte expor fila (`ao_largo`/`esperados`).

### Onde entra a temporalidade
- **Não entra no score**: o score é um instantâneo do último ciclo (6h). Não há
  memória, médias móveis, nem série temporal alimentando A/B.
- **Histórico existe mas não é consumido**: `port_metrics_history` acumula 1
  linha/porto/dia, mas nada no `risk_model` lê essa tabela para A/B atual.
- `trend` é uma projeção sintética de reversão à média — **não** é tendência
  derivada do histórico real.
- `validation` (ANTAQ) é média **mensal histórica**, com lag de dados:
  a janela mais recente disponível no espelho é **2026-01** (~8 meses).

### Onde existe incerteza
1. **SILOG não expõe fila**. A pré-pauta PortosRio contém apenas manobras
   futuras (SAÍDA 32 / ENTRADA 31 / MUDANÇA 27 em BRRIO; 15/1/7 em BRITG;
   6/1/4 em BRNIT). O `atracados` é, na verdade, **SAÍDA+MUDANÇA** (navios
   que saem/mudam de berço), não navios atracados agora. Não há `ao_largo`/
   `esperado`. → O score de BRRIO/BRNIT/BRITG é derivado de um proxy frágil.
2. **Santos**: `waiting=0` sempre — `santos` (135 programados) e `santos_painel`
   (591 em_operacao) não trazem fila. `ao_largo=0, esperados=0`.
3. **APPA (BRPNG)** é a única fonte BR que expõe fila real (`ao_largo` 33,
   `esperados` 169) → é a única com `waiting>0` e score discriminante.
4. **Validação ANTAQ** usa o complexo "Rio de Janeiro - Niterói" para ambos;
   a separação BRRIO/BRNIT é por terminal (Niterói = margem leste / estaleiros).
5. **IMOs**: 51% das linhas ANTAQ têm IMO; usamos agregados por porto (não
   reconciliação navio-a-navio).

## 2. Teste de discriminação — sinal vs. ANTAQ (ground-truth)

Config atômica do A/B agora (produção, 2026-09-19) vs. última janela ANTAQ:

| Port | score(A/B) | sinal A/B | ANTAQ espera avg (2026-01) | ANTAQ espera med (2025) | veredito |
|---|---|---|---|---|---|
| BRPNG | 0.95 | fila 202 (33+169) | 140.5h | 61.0h | ✅ discrimina |
| BRSSZ | 0.33 | waiting 0 | 51.4h | 18.1h | ❌ **subestima** |
| BRITG | 0.39 | waiting 0 | 67.8h | 29.2h | ❌ **subestima** |
| BRRIO | 0.44 | waiting 0 | 30.1h | 5.9h | ⚠️ plausível por acaso |
| BRNIT | 0.31 | waiting 0 | 15.4h | 0.4h | ⚠️ overestimate leve |

### Interpretação
- **BRPNG é o único caso onde o sinal discriminaria uma decisão** (espera real
  140h é compatível com score 0.95 + fila 202). Nesse porto, a fonte (APPA)
  expõe fila explicitamente — o "acerto" vem da fonte, não do modelo.
- **Falso negativos**: BRSSZ e BRITG têm espera real maior que BRRIO, mas
  scores menores (0.33 / 0.39 vs 0.44). O score não ordena os portos como a
  ANTAQ ordena.
- **Falso positivo potencial**: BRNIT (espera mediana real 0.4h) com score 0.31
  acima do piso — sinaliza tensão onde quase não há fila.
- Os três portos SILOG têm score ~0.31–0.44 "empurrado" pela heurística, não
  por pressão de fila real.

### Teste da decisão (08:00 → 08:05)
- **BRPNG**: sim, daria suporte a decisão (evitar a vaga, renegociar berço,
  precificar demurrage alto). ✅ **Único caso com evidência hoje.**
- **BRSSZ/BRITG/BRRIO/BRNIT**: não — o sinal PODE induzir a erro (subestimar
  Santos e Itaguaí, superestimar calma em Niterói). ❌/⚠️
- **Portos globais (14)**: seed estático, sem valor decisório operacional —
  é referência, não sinal.

## 3. Verdade (para quando automatizar ANTAQ)
- Automatizar `validate_antaq.py` (cron 90d/cache) só TÊM valor quando (a) o
  espelho MX estiver com janela recente (hoje só 2026-01) e (b) o A/B passa a
  consumir a série para recalibrar `_score_from_status` ou ao menos ordenar.
- Recomendação: **antes de automatizar**, reagregar a validação de forma que
  a comparação seja sinal↔espera no MESMO período (janela móvel), e reavaliar a
  heurística `0.25+0.35*...` com calibração BR (APPA já fornece fila real).
- Não virar a interface enquanto o A/B não ordenar os 5 BR como a ANTAQ.

## 4. Decisão de produto sugerida
- **Não adicionar cobertura antes de calibrar**: "10 portos bem observados >
  100 portos plausíveis."
- Próximo alvo de calibração: **BRPNG como caso de estudo** (fonte com fila
  real ↔ ANTAQ 140h de espera) para derivar a função score→experiência real.
- Para SILOG, documentar publicamente `live` como **pré-pauta (agendamento)**,
  não como posição atual — ou substituir a origem do `atracados`.
- Manter congelamento até a próxima iteração do A/B.

## 5. Fase 2 concluída — crosswalk observação → experiência (BRPNG)

Implementado em `src/engine/calibration.py` (núcleo) + `scripts/calibrate_brpng.py`
(registrador). **Nenhuma mudança de superfície.**

O princípio que rege a Fase 2: o score não pode nascer de uma heurística cega.
Ele nasce da resposta a uma pergunta empírica — *"quando o porto esteve nesse
regime de fila, qual distribuição de espera ANTAQ ocorreu?"* — emparelhando
janelas de observação.

### O que foi construído
- Tabela **`calibration_pairs`** em `data/processed/aether_oracle.duckdb`: acumula
  pares `(fila observada hoje ↔ janela ANTAQ vigente)`. Primeiro par realizado
  em 2026-09-19: fila=202 (ao_largo=33, esperados=169) ↔ ANTAQ 2026-01 avg=140.5h.
- **`calibrate(port_id)`** projeta o PORT STATE calibrado:
  - `historical_expected_wait_h`: mediana da distribuição ANTAQ mensal do porto
    (37 meses BRPNG: avg 91.7–275.3h; p90 248.6–1090.2h).
  - `eta_delay_days`: espera histórica convertida a dias.
  - `confidence`: `0.30/0.45` base por recência da janela + `+0.07` por par
    emparelhado (máx 0.95) — impede falso senso de precisão com 1 ponto.
  - `congestion_score`: **só emitido quando há fila observada** (per fonte que
    declara fila). Sem observação → `None` + `fonte="...distribuicao_somente"`,
    enforçando o princípio *o Oracle não inventa semântica que a fonte não possui*.
- BRPNG hoje: score 0.579 (não mais o 0.95 da heurística), espera esperada
  197.3h, p90 636.7h, confidence 0.52, 1 janela emparelhada.

### Limitações conhecidas (honestas)
- **1 par apenas**: a relação fila→espera ainda é dominantemente histórica.
  O ajuste por fila é conservador (até +15% em fila ≥ 200) e **não é regressão**
  até existirem ≥ 3 janelas emparelhadas (evita overfit de ponto único).
- **Janela ANTAQ desatualizada (~8 meses)**: última janela 2026-01; a espera
  "hoje" é ancorada em distribuição até jan/2026.
- **Fila é instantânea** (ciclo 6h) e ANTAQ é mensal agregado: o acoplamento
  temporal é por mês, não por manobra individual.
- Os demais BR (SSZ/RIO/ITG/NIT) entregam **referência histórica** (score=None,
  confidence 0.30) até que uma fonte com fila real esteja emparelhada.

### Próximo passo (Fase 2-b)
- Alimentar `calibrate_brpng.py` na agenda de snapshot diário para acumular
  pares ao longo do tempo (1 par/dia → em ~30 dias, relação estatística real).
  **Não** programar no cron de distribuição; fica no lado de observação.