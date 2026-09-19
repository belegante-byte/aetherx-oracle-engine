# Auditoria de fontes de fila/line-up públicas BR (Fase 3 PVA, 2026-09-19)

> Distribuição CONGELADA (v0.4.0 / 0.2.4). Documento de análise.
> Objetivo: mapear **quais portos BR expõem fila ao vivo publicamente e com
> qual semântica**, para decidir onde o Oracle pode crescer sem inventar
> observação que a fonte não possui.

## Método
- Busca aberta (websearch) + varredura de repositórios GitHub (`gh api`) +
  **probe HTTP ao vivo** de cada portal (status 200, sem login, sem baixar).
- Critério de aceite para "fila real": o portal declara **estado presente**
  (atracado / ao largo / esperado / programado), não apenas programação futura
  (ETA/ETB/ETD).

## 2. Resultado do probe ao vivo (2026-09-19)

| Portal | Status | Acessível sem login | Semântica observada | Uso atual Oracle |
|---|---|---|---|---|
| APPA Web (Paranaguá/Antonina) | 200 | sim | **fila real** (ATRACADOS/AO LARGO/ESPERADOS/PROGRAMADOS) + IMO | **BRPNG (`live:appa`)** |
| Portos PR "Tempo Real" | 200 | sim | **fila real** resumo (23 ao largo / 141 esperados / 17 atracados) — mesma base APPA | redundante (confirma APPA) |
| SILOG pré-pauta (RIO/NIT/ITG) | 200 | sim | programação futura (INICIO/IMO/NAVIO/TIPO/DE/PARA) | BRRIO/BRNIT/BRITG (`live:portosrio_silog`) |
| APS Ship Tracker / Expected Arrivals | 200 | sim | programação por terminal (ATA/ETA); sem estados de fila | programação (complemento BRSSZ) |
| Portonave line-up (Navegantes/SC) | 200 | sim (SPA) | `/api/LineUp` existe; estados via JS; anti-bot FingerprintJS | não usado |
| TCP "Programação de Navios" | 200 | sim (SPA) | ETA/ETB/ETD/ATB por serviço | não usado |
| EBTP/Embraport (Santos) | 200 | sim | escala por navio (ATA/status) | não usado |
| Itapoá (via ComexIA) | 200 | sim | lineup + deadlines | não usado |

## 3. Semântica por classe de fonte

- **Fila real (declara estado presente)** → pode alimentar `waiting_vessels`:
  APPA, Portos PR Tempo Real. HOJE: único par = BRPNG (source `appa`).
- **Programação futura (ETA/ETB/ETD)** → alimenta programação, NÃO fila:
  SILOG pré-pauta, APS expected arrivals, Portonave, TCP, Itapoá.
- **Escala declarada** → contexto de operação, não congestionamento.

## 4. Resultado da varredura GitHub (fontes gratuitas de navio)

Repositórios REAIS (com dados/uso), não código lixo:
- **`tayljordan/ais`** — dataset JSON de AIS curado (10 000 navios, snapshot
  2024, originado de AISHUB). Útil como seed/referência, não como dado ao vivo.
- **`GuillermoSiaira/marine-traffic`** — coletor AIS **aberto e gratuito**:
  ingest via `aisstream.io` (WebSocket grátis) → port calls/voyages → publica
  parquet por dia no IPFS (CC-BY 4.0+e). Provê `port_calls.parquet` (mmsi,
  ship, port, arrived_at, departed_at, duration_hours). Dado histórico aberto.
- **`thomasleese/ship-scraper`** — scraper de particulares VesselFinder via
  CSV de IMO/MMSI (output: MMSI, IMO, nome, GT, NT). Grátis por páginas públicas.
- **`api-evangelist/shipfinder-ais-data-api`** — possível API AIS agregadora.
- **`vessel-api/VesselApi`** — REST de posição AIS em tempo real; plano
  gratuito 150 req/mês (não dá fila BR densa sozinho).
- **`nicholailim/MaritimeFlow`** — análise "quanto navio fica ancorado / quão
  congestionado o porto fica" a partir de AIS. Inspira a heurística de fila.

Fontes AIS **gratuitas com processamento próprio** (as que mais importam):
- **AISHUB** — API key gratuita; `getpositions?bbox=...` → navios na bbox com
  `navigational status` (ancorado/moored). Ideal p/ derivar **âncoras ao largo
  por porto** usando polígono (boka).
- **aisstream.io** — stream WebSocket global gratuito de posições AIS
  (astral). Requer coletor próprio; cobre aderência contínua.

## 5. Implicação para o Oracle (honest)

- **BRPNG** é o único BR com **fila real pública tripla** (APPA + Tempo Real +
  painel da própria APPA) → continua o único anchor de calibração. ✅
- **Rio / Itaguaí / Niterói (SILOG)** não têm fila pública, MAS:
  **AIS derivado dá âncoras ao largo** desses portos sem login (fundo ao largo
  da barra / frente dos molhes). Isso **não é fila oficial** — é observação
  derivada (`ais_derivado`, confidence própria). Pode fechar o buraco que a
  sessão 1 deixou, mantendo a semântica.
- **Navegantes (Portonave)** responde SPA com `/api/LineUp`; **TCP** e
  **EBTP** são programação, não fila.

## 6. Próximo (propostas, nenhuma implementada)

1. **Fechar Fase 2-a primeiro**: acumular pares BRPNG por dia (decisão
   anterior) antes de comprar cobertura nova.
2. **Prototipar `ais_derivado` para BRRIO/BRITG/BRNIT**: via AISHUB bbox ou
   aisstream, contar navios com navstat=ancorado dentro do polígono do
   fundeadouro → `waiting_vessels` com `fonte="ais_derivado"` e confidence
   baixa, NUNCA fundido com fila oficial.
3. Auditar Portonave `/api/LineUp` (se der sem anti-bot) como possível
   "programação" de Navegantes.
4. Manter navegação pública **sem login** (princípio de observação declarada);
   SILOG interno continua fora do alcance gratuito.

## 7. Referências abertas citadas
- APPA: `https://www.appaweb.appa.pr.gov.br/appaweb/pesquisa.aspx?WCI=relLineUp`
- Tempo Real: `https://www.portosdoparana.pr.gov.br/Pagina/Tempo-Real`
- APS: `https://www.portodesantos.com.br/en/ship-tracker/expected-arrivals`
- Portonave: `https://extranet.portonave.com.br/line-up` (+`/api/LineUp`)
- TCP: `https://portal.tcp.com.br/publico/programacao/navios`
- EBTP: `http://www.embraportonline.com.br/Navios/Escala`
- AISHUB: `https://www.aishub.net/api`
- aisstream: `https://aisstream.io`