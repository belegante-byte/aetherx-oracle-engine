# Outbound — Pesquisa de Contatos (Prospects → Pessoas)

Objetivo: transformar cada uma das 50 empresas do `50_prospects.csv` em **1 contato humano** (pessoa + cargo + LinkedIn + e-mail público se achar + motivo específico). Preencher no CRM: `Contact Name | LinkedIn | Contact Email | Notes`.

## Playbook por empresa (~15 min cada)
1. **Localizar a pessoa certa** — entrar em LinkedIn Search e filtrar por:
   - Empresa → cargo conforme `Target Role` da planilha (ex.: VP Product / Data Partnerships, Head of Freight Risk, Head of Ocean Visibility, Head of Digital, DevRel/Integrations).
   - Onde existir, preferir quem tem "ocean", "freight", "supply chain", "risk", "data" no cargo.
2. **Extrair o LinkedIn** do perfil (URL pública).
3. **E-mail público** — só quando existir claramente público (padrões comuns por segmento):
   - Startups/plataformas (project44, Portcast, SeaRates...): `{nome}@{dominio}` costuma funcionar.
   - Corporações grandes (Cargill, ADM, Kuehne+Nagel): via formulário ou eventos; priorizar LinkedIn.
4. **Hook personalizado** (coluna `Notes`) — 1 frase que liga o Aether-X ao problema real daquela pessoa. Fontes:
   - Coluna `Approach Angle` da planilha.
   - Pesquisa recente no site/linkedIn deles (ex.: se a empresa lançou "AI agents for ocean visibility", citar isso).
   - Território (ex.: trading com exportação BR → citar Santos `BRSSZ`).
5. **Consolidar** no CRM com status `Not contacted`.

## Exemplos preenchidos (referência)
- **project44** → Research: anunciou "AI agent" para ocean exception resolution. Hook: *"project44 is moving from visibility to AI agents for exception resolution — Aether-X adds the predictive port-risk layer those agents call."* Cargo alvo: VP Product (Ocean) ou Head of Data Partnerships.
- **Bunge (Brasil)** → Research: opera terminais + shipping com fluxo agrícola BR. Hook: *"Bunge move grains out of Santos/Rio Grande — congestion there moves freight; Aether-X gives the signal 24/48/72h ahead."* Cargo alvo: Logistics Analytics / Freight Trading (SP).
- **Smithery / Glama** → já listam o Aether-X (landing). Hook: *"already on your platform; requesting featured placement + assets."* Cargo alvo: Ecosystem/Partnerships.

## Ferramentas (opcionais para acelerar)
- RocketReach / Apollo / Hunter.io (e-mails) — só se o funil justificar o custo.
- Extensão "LinkedIn Sales Navigator" se houver orçamento; senão LinkedIn básico + Google.

## Checkout do lote 1 (10 primeiros)
1. Preencher os 10 primeiros contatos no CRM.
2. Enviar as 4 mensagens (uma por segmento, 2–3 contatos por segmento).
3. Guardar data de envio (`First Contact Date` + `Channel`).
4. 7 dias depois: medir respostas e first API call (ver `docs/funnel.md`) antes do lote 2.