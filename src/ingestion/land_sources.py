import os
import time
from typing import List, Dict, Any

# Sinaliza que esta fonte é sintética (mock) — sem integração real com a Rumo.
# A flag bloqueia a ingestão silenciosa em produção.
IS_MOCK = True


def fetch_rumo_operations(allow_mock: bool = False) -> List[Dict[str, Any]]:
    """
    MOCK — dados sintéticos da malha ferroviária Rumo Logística.

    Esta função NÃO se conecta a nenhuma API ou sistema da Rumo.
    Gera registros estruturados fixos para BRSSZ e BRPNG apenas para
    desenvolvimento local e testes.

    Em produção, o pipeline de ingestão (run_ingestion_live.py) deve
    passar allow_mock=False (padrão) para impedir que dados sintéticos
    entrem no banco de dados real.

    Args:
        allow_mock: Se False (padrão), levanta RuntimeError quando
                    AETHERX_ENV=production. Se True, permite o mock
                    explicitamente (somente para testes locais/dev).

    Raises:
        RuntimeError: Se chamado em ambiente de produção sem allow_mock=True.
    """
    env = os.getenv("AETHERX_ENV", "development").lower()
    if env == "production" and not allow_mock:
        raise RuntimeError(
            "[land_sources] fetch_rumo_operations() é um MOCK e não pode ser "
            "executado em AETHERX_ENV=production sem allow_mock=True. "
            "Integre uma fonte real da Rumo ou remova a chamada do pipeline."
        )

    now = time.strftime('%Y-%m-%d %H:%M:%S')

    # Dados sintéticos — não representam operações reais
    data = [
        {
            "train_id": "RMO-4491",
            "port_id": "BRSSZ",
            "terminal": "T39",
            "commodity": "SOJA (GRAO)",
            "wagons": 80,
            "status": "AGUARDANDO_DESCARGA",
            "source": "rumo_logistica_mock",
            "ingested_at": now,
        },
        {
            "train_id": "RMO-4512",
            "port_id": "BRSSZ",
            "terminal": "T39",
            "commodity": "MILHO",
            "wagons": 60,
            "status": "EM_TRANSITO",
            "source": "rumo_logistica_mock",
            "ingested_at": now,
        },
        {
            "train_id": "RMO-5001",
            "port_id": "BRPNG",
            "terminal": "CORREDOR_EXPORTACAO",
            "commodity": "SOJA (GRAO)",
            "wagons": 120,
            "status": "AGUARDANDO_DESCARGA",
            "source": "rumo_logistica_mock",
            "ingested_at": now,
        },
        {
            "train_id": "RMO-5022",
            "port_id": "BRPNG",
            "terminal": "CORREDOR_EXPORTACAO",
            "commodity": "FARELO DE SOJA",
            "wagons": 45,
            "status": "AGUARDANDO_PATIO",
            "source": "rumo_logistica_mock",
            "ingested_at": now,
        },
    ]
    return data
