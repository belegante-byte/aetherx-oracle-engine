# Shipment Reconstruction Agents — Guia de Integração

## 1. O Princípio de Delegação
No ecossistema AETHER-X, agentes pesados (como Claude Sonnet 4.6) atuam como Arquitetos e Orquestradores: eles desenham schemas, planejam o sistema e resolvem conflitos complexos.
**Agentes Leves** (como Gemini Flash ou scripts automatizados) são os executores operacionais da *Shipment Reconstruction Layer*. Eles pegam tarefas tipadas, repetitivas e delimitadas.

**Regra Principal:** O agente leve executa o que está especificado. Não tenta adivinhar o raciocínio ambíguo.

## 2. Tipos de Agentes Leves Mapeados

### 2.1. Evidence Extractor Agent
- **Responsabilidade:** Consumir o output de ferramentas (ex: `assess_logistics_disruption`), ler os blocos de "observations" e extrair objetos `Evidence` atômicos.
- **Input:** `OperationalOrder` (contendo o JSON de resposta da API).
- **Output:** Lista de `EvidenceCandidate`.
- **Limites:** Não resolve entidades. Apenas traduz texto livre/JSON bruto para o schema de Evidence.

### 2.2. Entity Linker & Normalizer Agent
- **Responsabilidade:** Receber evidências e normalizar os identificadores WHO/WHERE (ex: "Santos" -> "BRSSZ").
- **Input:** `EvidenceCandidate[]`.
- **Output:** `NormalizedEvidence[]` (com entity IDs resolvidos).
- **Fallback:** Se a confiança na resolução for baixa (<0.8), manter como entidade não resolvida (`UNKNOWN_ENTITY_XYZ`).

### 2.3. Contradiction Detector Agent
- **Responsabilidade:** Varrer um `ShipmentReconstruction` periodicamente para encontrar evidências mutuamente exclusivas no mesmo campo.
- **Input:** `ShipmentReconstruction`.
- **Output:** Marcadores de `CONTRADICTION` anexados aos campos problemáticos, ou alerta para o Arquiteto.

### 2.4. Shipment Enricher (Inference Agent)
- **Responsabilidade:** Elevar o conhecimento de `UNKNOWN` para `INFERRED` ou `HYPOTHESIS`. (Exemplo: Se Vessel_Type == "Dry Bulk" e Port == "BRSSZ", Cargo_Inferred = "Soja/Milho").
- **Input:** `ShipmentReconstruction` parcial.
- **Output:** Novas `Evidence` com estado epistêmico `INFERRED` ou `HYPOTHESIS`.
- **Limites:** NUNCA emitir evidências como `OBSERVED`.

## 3. Contratos e Schemas
Agentes Leves não escrevem no banco de dados diretamente. Eles comunicam através de Contratos Fortemente Tipados.
O fluxo é sempre: `Agente -> Pydantic Model (Validator) -> Persistence Layer`.

## 4. O que NÃO fazer (Agentes Leves)
1. **Não deduza timestamps:** Se a fonte não deu timestamp da observação, o `age_seconds` é nulo.
2. **Não altere contratos:** Se o schema pede `List[str]`, não mande `str`.
3. **Não crie tabelas SQL arbitrariamente.** Use os adaptadores fornecidos pelo Core.
4. **Não silencie contradições:** Se A e B são diferentes, relate A e B.
