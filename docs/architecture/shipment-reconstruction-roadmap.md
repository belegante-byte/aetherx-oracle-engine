# Shipment Reconstruction Layer — Roadmap Executável

## Phase 0: Architecture (Atual)
- **Objetivo:** Definir os contratos, invariantes, e a estrutura do pipeline de reconstrução.
- **Dependências:** Motor atual operando de forma estável.
- **Conclusão:** Documentos de arquitetura aprovados e fundação de modelos (`src/reconstruction/models.py`) testada.

## Phase 1: Evidence Foundation
- **Objetivo:** Implementar o fluxo `OperationalOrder -> Evidence` usando os dados reais de `assess_logistics_disruption`.
- **Arquivos:** `src/reconstruction/engine.py`, `src/reconstruction/extractor.py`.
- **Testes:** Validação rigorosa de proveniência, temporalidade e idempotência.
- **Conclusão:** O sistema consegue extrair evidências de uma chamada MCP do BRSSZ e armazená-las em memória/mock DB.

## Phase 2: Entity Resolution
- **Objetivo:** Capacidade de normalizar nomes de navios e portos para identificar quando duas evidências falam da mesma coisa.
- **Dependências:** Phase 1.
- **Arquivos:** `src/reconstruction/resolvers/`
- **Risco:** Falsos positivos no matching. Resolução deve preferir gerar duas entidades a mesclar entidades erradas.

## Phase 3: Shipment Reconstruction
- **Objetivo:** O motor (`ReconstructionEngine`) agrupa as evidências validadas em uma "Synthetic BL" (`ShipmentReconstruction`).
- **Testes:** Resolução de conflitos, detecção de contradições, reconstrução parcial.
- **Conclusão:** Objeto `ShipmentReconstruction` completo (mesmo que com campos `UNKNOWN`) gerado a partir de múltiplas fontes.

## Phase 4: Operational Integration
- **Objetivo:** Integrar a extração de evidências no fluxo real da API/MCP sem introduzir latência síncrona.
- **Arquivos:** `src/api/mcp_app.py` (adicionando hooks fire-and-forget).
- **Risco:** Impacto na performance do motor M2M.

## Phase 5: M2M Enrichment
- **Objetivo:** Desenvolver agentes leves (Light Agents) que operam em background sobre as evidências, enriquecendo o `ShipmentReconstruction`.
- **Arquivos:** Scripts independentes que lêem a base de reconstrução e injetam novas evidências do tipo `INFERRED`.

## Phase 6: Commercial Intelligence
- **Objetivo:** Utilizar os embarques reconstruídos para tomada de decisão (Marketplace, Arbitragem Fiscal, Roteirização Preditiva).
- **Dependências:** Base de embarques populada com nível aceitável de `OBSERVED` e `INFERRED` facts.
