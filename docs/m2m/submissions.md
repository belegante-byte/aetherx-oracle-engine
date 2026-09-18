# Submissões M2M — checklist prático (parte do usuário)

Cruzamento de `surfaces.csv` (status `not_started`/`submitted`) com o passo a passo de submissão.
> Regra: cada submissão leva ~2-5 min. Faça em lotes de 5 e marque o status no CSV (`first_calls` depois de 7d).

## Lote 1 — Diretórios MCP (maior prioridade, 5 min)

1. **mcp.so** → abrir https://mcp.so e clicar "Submit server". Preencher com o package `aetherx-mcp` (GitHub: `belegante-byte`). O registrador da MCP usa o `mcp.discover.json`/metadata do package; apontar a "Homepage" para https://pypi.org/project/aetherx-mcp/ e o "Endpoint" para `https://aether-x-oracle-production.up.railway.app/mcp`.
2. **mcpservers.org** → https://mcpservers.org (form) — mesmos dados acima.
3. **Cursor MCP directory** → https://cursor.directory/mcp → "Add" → preencher `aetherx-oracle`.
4. **Continue.dev Hub** → https://hub.continue.dev → registrar servidor com metadata mcp-name `io.github.belegante-byte/aetherx-mcp`.
5. **OpenTools** → https://opentools.com → submit server (mesmo metadata).

## Lote 2 — PulseMCP + agregados

1. **PulseMCP** → submissões pausadas, mas ingere do MCP Registry. Confirmar se `io.github.belegante-byte/aetherx-mcp` já aparece na busca; senão, quando reabrirem, submeter em https://www.pulsemcp.com/submit.
2. **Cline Marketplace** → https://cline.bot/mcp-marketplace → publicar (requer o repo público + `cline.md`/manifests). Preparar metadata do package.

## Lote 3 — Awesome lists (via GitHub, PRs)

> Os PRs de listas GitHub podem ser feitos pelo `gh` (conta `belegante-byte`) — ver `../../scripts` ou pedir ao agente.

- `punkpeye/awesome-remote-mcp-servers`: **PR #403 já aberto** — acompanhar merge.
- `punkpeye/awesome-mcp-servers`: PR a criar (formato de tabela no README).
- `public-apis/public-apis`: PR a criar (atenção: a lista exige `Auth: No`/`apiKey` + HTTPS + CORS; o proxy RapidAPI pode ser classificável — submeter e aceitar possível rejeição).

## Lote 4 — Contas de dados (custo zero, mas número de conta)

1. **Kaggle** → https://www.kaggle.com/datasets → criar dataset a partir de `hf_space/ports.json`/CSV (CC BY 4.0).
2. **Zenodo** → https://zenodo.org → arquivar o snapshot com DOI (citações/backlink).
3. **AWS Data Exchange / Snowflake Marketplace / Google Cloud Datasets** → exigem conta/assinatura; avaliar apenas se houver demanda.
4. **Porto de Santos open data** → contato institucional (backlink/page) — baixa prioridade, humano opcional.

## Lote 5 — Observação/medida (faz isso sempre que publicar)

Cada submissão → volta ao `surfaces.csv`, marca `status=live`, e depois de 7 dias preenche `first_calls`.
Fonte das chamadas: `/internal/metrics` + logs `AETHERX_METRIC` (channels `mcp`, `discovery`, `seo`).