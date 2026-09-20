import time
from typing import List, Dict, Any

def fetch_rumo_operations() -> List[Dict[str, Any]]:
    """
    Simula a extração de operações logísticas terrestres da malha ferroviária Rumo.
    Gera dados estruturados de trens aguardando pátio/descarga nos terminais integrados
    aos portos (BRSSZ, BRPNG).
    """
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    
    # Mock realista de vagões aguardando
    data = [
        {
            "train_id": "RMO-4491",
            "port_id": "BRSSZ",
            "terminal": "T39",
            "commodity": "SOJA (GRAO)",
            "wagons": 80,
            "status": "AGUARDANDO_DESCARGA",
            "source": "rumo_logistica",
            "ingested_at": now
        },
        {
            "train_id": "RMO-4512",
            "port_id": "BRSSZ",
            "terminal": "T39",
            "commodity": "MILHO",
            "wagons": 60,
            "status": "EM_TRANSITO",
            "source": "rumo_logistica",
            "ingested_at": now
        },
        {
            "train_id": "RMO-5001",
            "port_id": "BRPNG",
            "terminal": "CORREDOR_EXPORTACAO",
            "commodity": "SOJA (GRAO)",
            "wagons": 120,
            "status": "AGUARDANDO_DESCARGA",
            "source": "rumo_logistica",
            "ingested_at": now
        },
        {
            "train_id": "RMO-5022",
            "port_id": "BRPNG",
            "terminal": "CORREDOR_EXPORTACAO",
            "commodity": "FARELO DE SOJA",
            "wagons": 45,
            "status": "AGUARDANDO_PATIO",
            "source": "rumo_logistica",
            "ingested_at": now
        }
    ]
    return data
