# Auditoria de fontes globais — portos seed (2026-09-19)

> Objetivo: mapear fontes públicas reais de fila/congestionamento para os 14
> portos globais que hoje servem `static_reference_seed`, para substituir
> valores fixos por observação viva. Complementa `lineups-publicos-auditoria.md`
> (que cobria só os 5 BR).

## Resumo executivo

Os 14 portos seed **têm fontes públicas de dados de fila/chegada disponíveis**.
O bloqueio não é existência de dado — é que a maioria exige scraping de SPA/JS
ou API com registro. A auditoria abaixo classifica cada porto por:
- **Acessível agora** (HTTP 200 sem login, dados no HTML)
- **Requer scraping** (SPA/JS — os dados existem mas carregam via script)
- **Requer API/registro** (portal com key gratuita/paga)

## Mapa por porto

| Port | Fonte identificada | Tipo | Acessível hoje |
| --- | --- | --- | --- |
| **NLRTM** Rotterdam | `portal.api.portofrotterdam.com` (API oficial; anchorage, waiting, port-call data) | API oficial (guest account) | ⚠️ SPA/API |
| **DEHAM** Hamburg | `hvcc-hamburg.de/api-port-call-data` (API sailing list real-time; ETA/ATA/ETD) + `hhla.de/en/customers/information/ship-arrivals` | API oficial (3 pacotes) | ⚠️ SPA/API |
| **SGSIN** Singapore | `oceans-x.mpa.gov.sg` (MPA — real-time vessel/cargo/port data) | Plataforma oficial | ⚠️ SPA/API |
| **KRPUS** Busan | `pnitl.com` (Berth Schedule real-time) + `shipinfo.net/port/Busan` (260 vessels, endpoint `/topos/api/v1/ports/1809/congestion`) | Site oficial + API | ⚠️ SPA/API |
| **CNSHA** Shanghai | `shipdata.net/port/CNSHG` (21 anchored, 22 moored) + `exportparadip` + SeaRates | Agregador AIS | ✅ (scrape JS) |
| **CNNGB** Ningbo | `mykn.kuehne-nagel.com/seaexplorer/port-details/CNNGB/vessels-in-port` (wait time 3.45d) | Kuehne-Nagel | ⚠️ |
| **CNTAO** Qingdao | `shipdata.net/port/CNTAO` (mesmo padrão Xangai) | Agregador AIS | ✅ (scrape JS) |
| **USLAX** Los Angeles | `portoflosangeles.org/business/supply-chain/ships` (snapshot oficial: vessels in port, container ships due) | Site oficial | ✅ |
| **USNYC** New York/New Jersey | `panynj.gov/port/en/our-customers/ocean-carriers.html` (vessel schedules) | Site oficial | ✅ |
| **AEDXB** Dubai/Jebel Ali | `dpwdtjb2.dubaitrade.ae/pmisc1/vessel.do` (Vessels Anchorage/Alongside/Expected) | Portal oficial | 🔴 WAF bloqueia |
| **GBLGP** London Gateway | `dpworld.com/.../vessel-schedule` (DP World oficial) | Site oficial | ✅ |
| **MPTNG** Tanger Med | `tangermedport.com` + `tangermed-passagers.com/en/ferry-time-table/live-arrivals` (chegadas ao vivo) | Site oficial | ✅ |
| **ZACPT** Cape Town | `transnet.net/SubsiteRender.aspx?id=8185344` (**Anchorage Reports** + Vessel Updates + Terminal Berthing List) | TNPA oficial | ⚠️ timeout/lentidão |
| **MXZLO** Manzanillo | `en.contecon.mx/trafico-de-naves` (vessel traffic oficial) + `portcast.io` | Site oficial | ✅ |

## Achados-chave

1. **Três portos têm dados de âncora/fila EXPLÍCITOS** (não só chegada):
   - **Rotterdam**: API oficial com anchorage areas + average waiting time (dados de port dues/AIS)
   - **Dubai/Jebel Ali**: separação explícita "Vessels Anchorage / Alongside / Expected" (bloqueado por WAF)
   - **Cape Town (TNPA)**: tem seção "Anchorage Reports" dedicada

2. **Padrão comum:** a maioria dos portos globais usa **SPA/JS** — os dados existem no HTML/API do navegador mas não no HTML estático. Requer o mesmo approach do `santos_painel` (scrape com parsing).

3. **`shipinfo.net` e `shipdata.net`** são agregadores AIS abertos que expõem **anchorage/moored counts por porto** — uma fonte uniforme para os portos chineses e outros, com endpoint `/topos/api/v1/ports/{id}/congestion`.

## Próximo (decisão pendente do operador)

| Opção | Esforço | Cobertura |
| --- | --- | --- |
| **A. Agregador AIS (shipdata/shipinfo) para todos os 14** | Baixo (1 coletor, endpoints de porto) | 14 portos com anchorage/moored counts (fila derivada) |
| **B. Fontes oficiais por porto (Rotterdam API, HVCC, TNPA, MPA)** | Alto (14 integrações distintas) | Dados mais precisos, fila explícita |
| **C. AISHUB key (grátis) + bboxes de fundeadouro** | Médio (key + polígonos) | Todos os portos com navstat=ancorado |

**Recomendação:** começar com **A** (agregador AIS uniforme) para destravar os 14
de uma vez com `fonte="ais_derivado"` + confidence própria, e evoluir para **B**
nos portos onde a fonte oficial é robusta (Rotterdam, Hamburg, Cape Town).
A decisão de qual caminho segue a doutrina §9 (AIS só com hipótese clara —
aqui há: reconstruir fila que fontes oficiais não expõem em formato simples).

## Bloqueios identificados

- **Dubai Trade** (Jebel Ali): WAF rejeita requests de bot (Request Rejected) — requer browser real/headless.
- **Transnet** (Cape Town): timeout no probe — site lento, mas Anchorage Reports existe.
- **Rotterdam/HVCC/MPA**: APIs requerem registro (guest account / pacotes) — mas gratuito ou com tier livre.
- **Agregadores (shipdata/shipinfo)**: dados via JS — scraping necessário, verificar ToS/anti-bot.
## Resultado do probe real das fontes oficiais (2026-09-19, tarde)

| Fonte | Probe HTTP | Dados de fila acessíveis sem registro? |
| --- | --- | --- |
| Rotterdam `portal.api.portofrotterdam.com` | 200 | Não — SPA/Highcharts, guest account requerida |
| Rotterdam `portofrotterdam.com/port-performance` | 200 | Não — charts carregam via JS (Highcharts data module) |
| HVCC Hamburg `api-port-call-data` | 200 (301→HTTPS) | Não — API com 3 pacotes, requer contrato |
| MPA Singapore `oceans-x.mpa.gov.sg` | 200 | Não — plataforma com registro |
| PANYNJ `ocean-carriers.html` | 200 | Vessel schedules (chegada), não fila explícita |
| Dubai Trade `dubaitrade.ae/pmisc1/vessel.do` | **WAF Rejected** | Bloqueado (Request Rejected) |
| TNPA Transnet `SubsiteRender?id=8185344` | timeout | Anchorage Reports existe, site instável |
| Contecon Manzanillo `trafico-de-naves` | timeout | Vessel traffic, lento |
| **shipinfo `topos/api/v1`** | **200 ok** | **API anônima funcional** — `ports/search` (conf 0.92), `ports/{id}/congestion` (conf 0.88), mas congestion retorna `rows: []` (beta, não populado) |
| shipdata `port/CNSHG` | 200 | Dados via JS (scrape) — "21 Anchored" não está no HTML estático |

**Conclusão do probe:** Nenhuma fonte oficial entrega fila real em formato simples e
imediato hoje. As APIs oficiais existem mas exigem registro/pacote (Rotterdam, HVCC,
MPA) ou scraping de SPA (Rotterdam charts, shipdata). O shipinfo é a única API aberta
que responde anonimamente, mas o endpoint de congestion está vazio (beta).

**Estado da implementação:** NÃO foi possível destravar os 14 portos com fonte oficial
sem (a) registro em 3+ portais ou (b) scraping de SPA. A via viável imediata é:
- shipinfo `ports/search` + derivar âncoras de `bootstrap/vessels` quando disponível, OU
- scraping do shipdata (anchorage counts) — verificar ToS/anti-bot, OU
- AISHUB key grátis + bboxes de fundeadouro (caminho C da doutrina §9).

Registrado para decisão do operador. Nenhum dado falso foi injetado — os 14 portos
continuam `static_reference_seed` honestos.

## Verificação aprofundada das vias AIS (2026-09-19, fim de tarde)

**AISHub — DESCARTADO:** registro exige OPERAR UMA ESTAÇÃO AIS física
(receptor NMEA contribuindo à rede). Não é "conta grátis". Inviável para o
operador sem equipamento.

**VesselAPI / VesselFinder / MarineTraffic — exigem API key** (free tier com
limite), sem acesso imediato.

**shipinfo API — a única funcional anonimamente:**
- `ports/search` → OK (conf 0.92)
- `ports/{id}/congestion` → **Hamburgo tem 175 rows REAIS de congestion**
  (30D). Los Angeles/Singapore/NY/Dubai/Jebel Ali → vazio (cobertura seletiva).
- **Limite anônimo: 6 requests/dia, daily_limit 120** → insuficiente para
  produção, mas prova que a fonte entrega dados reais.

**Estado:** para destravar os 14 portos globalmente com AIS, a via realista é
uma conta com tier maior (shipinfo registrado, ou outro provedor AIS com key).
O Hamburgo via shipinfo é a prova de conceito que funciona hoje (175 rows).
Sem isso, os 14 seguem static_reference_seed honestos.

## Correção pós-auditoria (2026-09-19, noite)

O coletor ShipInfo adicionado ao Aether-X estava incompleto/quebrado: faltava
`import json` no módulo e o pipeline de métricas só aplicava dados ao GRID BR.
Na prática, ele podia consumir o rate limit anônimo sem atualizar nenhum porto
global. Ele foi **desabilitado por padrão** na branch
`fix/ingestion-integrity-audit` (`SHIPINFO_ENABLED=1` para uso manual), com
port map cacheado e batch limitado.

Os conectores GP5 auditados também **não trazem AIS real**:
`ais_connector.py` usa Yahoo Search + Ollama e `vessel_tracking_connector.py`
usa DuckDuckGo Search. Portanto, a decisão acima permanece: sem key/tier pago
ou registro oficial, os 14 portos globais continuam `static_reference_seed`.
