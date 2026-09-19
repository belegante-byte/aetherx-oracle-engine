# Mapa do Drive GP5 (BKP_GPS_PC)

> Levantado em 2026-09-19 via `embeddedfolderview` (pasta pública).
> Objetivo: conectar a base do projeto (GP5) ao Aether-X e documentar onde
> estão os datasets/código que alimentam o sistema.

## Drive
- Raiz: `https://drive.google.com/drive/folders/1VP4MRowdJ4wET-_HLv9js3XF4zZVscf3`
- Pasta **GP5**: `https://drive.google.com/drive/folders/1lPQV5XR6T3vF9woDIb60ecXOE5BHUE6K`

## Estrutura da pasta GP5

| Pasta | Conteúdo identificado |
| --- | --- |
| **00_GOVERNANCE** | `GP5-000_CARTA_DE_NAVEGACAO.md` + scripts |
| **01_BACKEND** | `main.py` |
| **02_FRONTEND** | (não inspecionado) |
| **03_DATABASE** | (não inspecionado) |
| **04_CONNECTORS** | (não inspecionado) |
| **05_DATA_LAYER** | (1 subpasta) |
| **05_DATASETS** | `antaq/`, `appa_paranagua/`, `outros_portos/`, `relatorio_coleta.md` |
| **06_INTELLIGENCE** | `agente_contatos.py`, `discovery_orchestrator.py`, `hypothesis_matrix.py` |
| **08_EXPERIMENTS** | `F1-0001_Pacific_Wind` |
| **09_DOCS** | `backlog_fontes_portuarias.md`, `diagnostico_gp5.md`, `relatorio_ecossistema.md`, `relatorio_operacional.md` |
| **10_DEVTOOLS** | `gp5-hostinger` (tar/tar.gz), `health_check.py`, `refactor_api_urls.py` |
| **10_TEMP** | (não inspecionado) |
| **11_RAW_DATA** | `equasis_pagina_real.html` |

## 05_DATASETS (o que importa para o Aether-X)

```
05_DATASETS/
├── antaq/                  (dados ANTAQ — mesmo domínio do validate_antaq.py)
├── appa_paranagua/
│   └── appa_lineup_2026-06-26_1728.html   (snapshot APPA 26/06)
├── outros_portos/
│   ├── portosrio/
│   │   ├── rio_de_janeiro_2026-06-26.html
│   │   ├── itaguai.pdf
│   │   ├── niteroi.pdf
│   │   ├── rio.pdf
│   │   └── portosrio_2026-06-26.html
│   └── santos/
│       └── santos_atracacoes_2026-06-26.html
└── relatorio_coleta.md
```

## Conexão com o Aether-X

- O Aether-X **já consome** os mesmos domínios de dados (ANTAQ via HuggingFace,
  APPA/Santos/PortosRio via portais ao vivo).
- O drive guarda **snapshots de 2026-06-26** (congelados) desses line-ups —
  úteis como histórico/referência, não como fonte viva.
- `06_INTELLIGENCE` tem código (agente_contatos, discovery_orchestrator,
  hypothesis_matrix) que pode ser fonte de lógica de distribuição/hipóteses.
- `09_DOCS` tem diagnósticos/backlogs (backlog_fontes_portuarias.md é
  diretamente relevante — lista fontes de dados portuários).

## Limitações do acesso

- `embeddedfolderview` expõe NOMES de pastas/arquivos mas **não os file IDs**
  para download individual (requer JS/login ou API com auth).
- Para baixar um arquivo específico, é preciso o link direto `file/d/<ID>`
  (fornecido pelo operador) ou exportar via `https://drive.google.com/uc?export=download&id=<ID>`.