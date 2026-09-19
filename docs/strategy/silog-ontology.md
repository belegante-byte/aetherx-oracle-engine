# Ontologia SILOG PortosRio — o que a pré-pauta realmente observa (2026-09-19)

> Fase 1 do PVA. Documenta a semântica operacional da pré-pauta SILOG antes de
> qualquer calibração. Conclusão: o sinal BRRIO/BRNIT/BRITG atual deriva de uma
> variável de entrada semanticamente incorreta (`SAÍDA+MUDANÇA` como
> `atracados`). Este documento é a base para a correção.

## 1. Fonte e escopo

- URL pública:
  `silog.portosrio.gov.br/silog/pesquisa.aspx?WCI=relPrePautaSimplificado&Mv=Link&sqlCodDominio={1,2,3}&sqlFLG_PUBLICO_EXTERNO=1`
- Domínios: 1 = Rio de Janeiro (BRRIO), 2 = Niterói (BRNIT), 3 = Itaguaí/Sepetiba (BRITG).
- **Pré-pauta = AGENDA de manobras futuras**, não posição atual nem fila ao largo.
- Estado atual (`relFundeado`, `relLinhaBerco`, `relPrePauta` expandida) exige
  login — **não público** (verificado em 2026-09-19).

## 2. Colunas reais da pré-pauta

| Coluna | Exemplo | Observável? |
|---|---|---|
| INICIO | `18/09/2026 00:00` | programação temporal da manobra |
| IMO/CAPITANIA | `1094979` | sim (IMO) |
| NAVIO | `STARNAV ELEKTRA (CADASTRO PROVISÓRIO - PSP)` | sim |
| TIPO | `MUDANÇA` | tipo da manobra |
| DE | `2N04 - Armazém 4 e 5` | local de origem |
| PARA | `Fundeio - 2F6A - LARGO` | local de destino |
| AGENTE | `STARNAV SERVIÇOS MARITIMOS LTDA` | sim |
| CABEÇO PROA/POPA, CALADO, PRATICADO | — | técnico (não usado) |

## 3. Ontologia dos eventos (TIPO × DE × PARA)

Observação censurada em 2026-09 (dom. 1=90, dom. 2=7, dom. 3=21 linhas):

| TIPO | DE | PARA | Semântica operacional real | Contagem BRRIO |
|---|---|---|---|---|
| ENTRADA | MAR | BERCO | chegando, atraca (agenda) | 16 |
| ENTRADA | MAR | FUNDEIO/LARGO | chega e vai ao fundeadouro → **fila futura** | 15 |
| SAÍDA | BERCO | MAR | deixa o porto → **saindo, não atracado** | 22 |
| SAÍDA | FUNDEIO | MAR | larga o fundeadouro e parte | 10 |
| MUDANÇA | BERCO | FUNDEIO | deixa o berço → **passa a aguardar ao largo** | 14 |
| MUDANÇA | FUNDEIO | BERCO | sai do fundeadouro → **atraca** | 10 |
| MUDANÇA | BERCO | BERCO | troca de berço | 3 |

Total de fila "ao largo" **real observável** pela pré-pauta: as manobras cujo
PARA = FUNDEIO/LARGO (ENTRADA→FUNDEIO + MUDANÇA→FUNDEIO) e cujo estado vigente
seja de espera. **Não existe campo "fundeados agora".**

## 4. O que a pré-pauta NÃO permite observar

```text
esperando / ao largo (estado atual)   ❌ NÃO observável
programado                        ✅ ENTRADA→BERCO (agenda)
atracado (agora)                  ❌ não confiável: SAÍDA/MUDANÇA não é "atracado"
em operação                       ❌ não há coluna de operação
saindo                            ✅ SAÍDA→MAR / MUDANÇA→FUNDEIO
```

Erro atual do A/B: mapeia `SAÍDA→atracado` e `MUDANÇA→atracado` (em
`_SILOG_STATUS_MAP`), produzindo `atracados = SAÍDA + MUDANÇA`. Por exemplo
BRRIO reportou `atracados=58` sendo que a pré-pauta tinha 32 SAÍDA + 27 MUDANÇA
(59) — ou seja, "58 atracados" é, na verdade, o conjunto de **saídas e mudanças
agendadas**, não navios no berço. `waiting` derivado disso é enganoso.

## 5. Ontologia correta proposta para SILOG

```text
SILOG (pré-pauta) → eventos de manobra agendados:
  arriage     = ENTRADA ∧ PARA ∈ {berço}            → programado_atracar
  anchoring   = ENTRADA ∧ PARA = fundeio            → vai_ao_largo (fila futura)
  berthing    = MUDANÇA|SAÍDA ∧ PARA = berço        → atracando (se MUDANÇA→berço)
  unberthing  = SAÍDA→MAR | MUDANÇA→MAR            → saindo
  shifting    = MUDANÇA ∧ DE=berço ∧ PARA=fundeio  → passando_a_aguardar
```

SILOG **suporta observação**: IMO real, agendamento temporal, movimentos
entrada/saída/mudança. **Não suporta**: contagem de fila atual, tempo de espera,
posição presente. Portanto não pode alimentar `waiting_vessels` nem
`congestion_score` tal como hoje.

## 6. Declaração de observações por fonte (aplicável às demais)

| Fonte | IMO | fila atual | programação | posição/berço | operação | observação suportada |
|---|---|---|---|---|---|---|
| APPA (BRPNG) | sim | ✅ ao_largo/esperados | parcial | atracados (seções) | parcial | **fila** |
| Lachmann (BRPNG) | não | parcial (ETA) | ✅ | — | — | **programação** |
| Santos atracações | sim | ❌ | ✅ | programação | — | **programação** |
| Santos painel | não | ❌ | — | ❌ | ✅ em operação | **operação (contagem)** |
| SILOG (BRRIO/BRNIT/BRITG) | sim | ❌ | ✅ manobras | ❌ | ❌ | **eventos de manobra** |

Regra de produto (a partir de agora): **o Oracle não inventa semântica que a
fonte não possui.** `waiting_vessels` só é emitido quando a fonte declara fila
(APPA). Para SILOG, o payload deve dizer "pré-pauta de manobras" e expor os
eventos — não um número de "esperando".

## 7. Impacto no A/B atual

- `congestion_score` de BRRIO/BRNIT/BRITG é **não-confiável** (entrada
  contaminada). Manter como está por enquanto (congelado), mas marcar como
  `semantic-pending`.
- `waiting_vessels` de BRRIO/BRNIT/BRITG **deve ser null/ausente** — não existe
  fila observada.
- BRPNG permanece o único com `waiting` confiável → **calibration anchor**
  (Fase 2).