# Shipment Reconstruction Layer — Architecture

## 1. Visão Geral e Missão
O AETHER-X já possui um Oracle consolidado para inteligência logística e ingestão de dados físicos. A **Shipment Reconstruction Layer** (Camada de Reconstrução de Embarques) é uma superestrutura desenhada para transformar chamadas operacionais episódicas em um grafo de evidências persistente. 

O objetivo não é forjar documentos (BL falsas), mas sim criar uma **representação probabilística** de uma operação logística (Shipment) com base nas evidências coletadas pelo motor.

## 2. Princípio Central: Evidence-First
A unidade atômica da arquitetura não é o navio, nem a carga, nem o porto, mas a **Evidência (`Evidence`)**.
Qualquer asserção sobre o mundo físico precisa responder a:
- **WHAT:** O que foi observado? (ex: "Navio atracado", "ETA 14:00")
- **WHO:** Qual entidade está relacionada? (ex: IMO 9123456)
- **WHEN:** Quando o fato ocorre/ocorreu?
- **WHERE:** Onde? (ex: BRSSZ)
- **SOURCE:** Quem originou a informação? (ex: "live:santos_painel")
- **OBSERVED_AT:** Quando a fonte registrou o dado?
- **RETRIEVED_AT:** Quando o AETHER-X coletou?
- **EPISTEMIC STATE:** Qual o grau de inferência? (Observed, Inferred, Hypothesis)

## 3. Epistemologia Operacional (Regra de Ouro)
Um estado epistêmico nunca pode ser promovido silenciosamente. A escada epistêmica é rígida:
1. `OBSERVED`: Visto diretamente na fonte (ex: fila de navios no porto).
2. `DERIVED`: Calculado deterministicamente a partir de observações (ex: delay_days = queue / throughput).
3. `ESTIMATED`: Calculado probabilisticamente (ex: demurrage_usd).
4. `INFERRED`: Deduzido logicamente com alta confiança (ex: Navio graneleiro no terminal de soja -> Carga é soja).
5. `HYPOTHESIS`: Suposição testável (ex: Navio indo para China -> Consignee provável COFCO).
6. `UNKNOWN`: Ausência de dados.

**Regra:** `UNKNOWN` nunca vira `INFERRED` sem evidência; `INFERRED` nunca vira `OBSERVED` sem constatação física.

## 4. Pipeline Proposto

1. **SOURCE / COLLECTOR (Existente):** `live_sources.py` captura dados do mundo real.
2. **OPERATIONAL ORDER:** Uma requisição ao MCP (`assess_logistics_disruption`) gera uma ordem.
3. **EVIDENCE EXTRACTOR:** Agentes leves extraem "claims" (asserções) do resultado da ordem.
4. **ENTITY RESOLVER:** Agentes normalizam nomes, IMOs e UN/LOCODEs.
5. **EVIDENCE STORE:** Evidências são salvas de forma imutável (append-only).
6. **RECONSTRUCTION ENGINE:** Agrupa evidências em um `ShipmentReconstruction`. Identifica contradições e calcula a confiança de cada campo.
7. **INTELLIGENCE:** O MCP consome a reconstrução para responder perguntas complexas ("Onde está a carga X?").

## 5. Modelagem Conceitual

- **OperationalOrder:** O gatilho. Registra *por que* o AETHER-X buscou a informação (ex: consumer="m2m_123", objective="routing").
- **Evidence:** O fato bruto ou inferido. Pode colidir com outras evidências.
- **ShipmentReconstruction:** A "Synthetic BL". Um objeto dinâmico que consolida as melhores evidências atuais para Vessel, Port Calls, Cargo, Shipper, Consignee e Route, sem descartar o histórico.

## 6. Tratamento de Contradições e Idempotência
- Se Fonte A diz ETA 14:00 e Fonte B diz ETA 17:30, ambas as evidências são mantidas. O campo no `ShipmentReconstruction` recebe o estado `CONTRADICTION`, aguardando resolução por um agente (ou por peso de confiança da fonte).
- Se a mesma evidência (mesmo source, mesmo fato, mesmo observed_at) entra duas vezes, o sistema ignora a duplicação silenciosamente (Idempotência).
