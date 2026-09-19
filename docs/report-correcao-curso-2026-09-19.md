# Correção de Curso — Auditoria GP5, Integridade de Ingestão e Paid Calls

**Data:** 2026-09-19  
**Escopo:** auditoria read-only dos conectores GP5, diagnóstico da ingestão Aether-X, fluxo paid/RapidAPI e correções mínimas em branch isolada.

## 1. Estado observado antes da correção

- Produção pública respondia com **19 portos**:
  - **5 BR live:** `BRSSZ`, `BRPNG`, `BRRIO`, `BRNIT`, `BRITG`
  - **14 globais:** `static_reference_seed`
- `paid_plans = {}`, `paid_users = []`, `cum_paid_calls = 0`.
- Tool calls acumuladas: **6** (`get_port_risk=4`, `get_ports_risk=1`, `get_port_trend=1`).
- Nenhum tool repeat consolidado na janela observada.
- RapidAPI listing acessível e OpenAPI público servido em `/openapi.rapidapi.json`.

## 2. Achados críticos

### 2.1 ShipInfo estava quebrado e consumindo rate limit inutilmente

`src/ingestion/live_sources.py` usava `json.loads()` no coletor ShipInfo sem importar `json` no módulo. O coletor falhava em runtime, mas o erro era engolido pelo isolamento de falhas do `coletar_tudo()`.

Pior: cada ciclo podia tentar resolver os 14 portos via `ports/search`, consumindo o tier anônimo (documentado como **6 requests/dia**) sem atualizar nenhum porto global, porque `scripts/run_ingestion_live.py` só aplica métricas ao `GRID` brasileiro.

**Correção aplicada:**
- `import json` adicionado.
- ShipInfo **desabilitado por padrão** (`SHIPINFO_ENABLED=1` para ligar).
- Mapa de portos cacheado em `data/shipinfo_port_map.json` é usado sem busca remota.
- Batch limitado (`SHIPINFO_MAX_PORTS_PER_RUN`, default 4) para não estourar o limite anônimo se o operador habilitar manualmente.

### 2.2 Painel de Santos contava histórico como operação atual

O parser do painel de Santos classificava **594 linhas históricas** (inclusive registros de 2024 e 2025) como `em_operacao`. O payload público chegou a expor `atracados: 595`, um número operacionalmente implausível.

**Correção aplicada:**
- filtro de status ativo;
- filtro de data de atracação (janela default de 7 dias);
- filtro de estimativa de fim de operação (default 24h de tolerância);
- deduplicação por navio/local/viagem/data.

Probe após correção: **32 operações correntes**, em vez de 594.

### 2.3 Conectores GP5 não resolvem AIS global

Auditoria dos 25 arquivos baixados do Drive (`04_CONNECTORS`) mostrou:

- `ais_connector.py`: **não é AIS real**; usa Yahoo Search + Ollama para tentar inferir destino declarado.
- `vessel_tracking_connector.py`: **não é AIS real**; usa DuckDuckGo Search para inferir tipo de navio.
- `vtmis_itaguai_connector.py` e `itaguai_parser.py`: fontes reais de Itaguaí/PortosRio, úteis, mas o Aether-X já possui SILOG PortosRio para `BRRIO/BRNIT/BRITG`.
- `appa_lineup_connector.py`: mesma família de fonte já integrada no Aether-X para `BRPNG`.
- `equasis_connector.py`: potencial enriquecimento de navio (flag/type/owner/manager), mas exige conta, tem rate limit e foi encontrado com credencial hardcoded no GP5. A cópia local foi **sanitizada** e não deve ser commitada com segredo.

**Conclusão:** não existe conector GP5 pronto para transformar os 14 portos globais em live AIS. O caminho real continua sendo key/tier pago ou registro em fontes oficiais/agregadores AIS.

## 3. Fluxo paid

Paid call não é gerada por tráfego direto, MCP local ou plano BASIC. Ela exige:

1. chamada via **RapidAPI gateway**;
2. header `X-RapidAPI-Subscription` em `PRO`, `ULTRA`, `MEGA` ou `CUSTOM`;
3. idealmente `X-RapidAPI-User` para identificar o pagador.

O código de detecção está correto em `src/api/metrics.py`. O problema atual é de funil, não de instrumentação:

```text
discovery → connect → tool_call → tool_repeat → free limit → subscription → paid
```

Hoje há tool calls históricas, mas **zero paid**. Não faz sentido alterar pricing ou criar paywall antes de demonstrar `tool_repeat`.

## 4. Correções implementadas nesta branch

Branch: `fix/ingestion-integrity-audit`

- `src/ingestion/live_sources.py`
  - importa `json`;
  - desabilita ShipInfo por padrão;
  - usa port map cacheado;
  - limita batch ShipInfo;
  - corrige filtro/deduplicação do painel de Santos;
  - adiciona label da fonte ShipInfo.
- `tests/test_live_sources.py`
  - regressão do filtro de data/status do painel de Santos;
  - parser de datas mistas;
  - ShipInfo desabilitado não chama rede.
- `.gitignore`
  - ignora estado local e a pasta sanitizada de conectores GP5 para evitar commit acidental de segredos/logs.

**Testes:** `71 passed`.

## 5. O que NÃO foi alterado

- Nenhum seed de porto.
- Nenhum schema do DuckDB.
- Nenhum pricing/paywall.
- Nenhum endpoint público.
- Nenhuma descrição de tool MCP.
- Nenhum deploy/push até aprovação explícita.
- Os 14 portos globais continuam honestamente `static_reference_seed`.

## 6. Próxima decisão recomendada

### Opção A — Aprovar deploy das correções de integridade (recomendado)

Efeito:
- Santos deixa de expor 595 atracados históricos.
- ShipInfo para de queimar rate limit anonimamente.
- Dados BR continuam live; globais continuam seed honesto.

### Opção B — Buscar fonte AIS global real

Requisitos:
- key/tier pago ou registrado (ShipInfo tier maior, VesselFinder, MarineTraffic, Datalastic, Kpler, Spire etc.), **ou**
- registros oficiais porto a porto (Rotterdam, HVCC Hamburg, MPA Singapore, TNPA Cape Town).

Isso é o único caminho para os 14 globais deixarem de ser seed. Deve ser tratado como decisão de custo/contrato, não como patch de código.

### Opção C — Enriquecer BR com GP5/Equasis

Potencial:
- operador/terminal, tipo de navio, owner/manager, validação CNPJ.
- Não resolve paid calls diretamente, mas aumenta profundidade do produto BR.

Recomendação: **A agora**, depois **B apenas com orçamento/key aprovados**, e **C como fase de enriquecimento** sem contaminar o experimento de funil.
