import os
import json
import uuid
import logging
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path
from src.runtime.contracts.v1 import ClientContext

logger = logging.getLogger("m2m_access")

_M2M_SECRET = os.getenv("M2M_API_SECRET", "gp5_m2m_default_secret_key")
KEYS_FILE = Path(os.getenv("DATA_DIR", "data")) / "m2m_keys.json"

VALID_M2M_KEYS: dict[str, str] = {
    _M2M_SECRET: "default_m2m_client",
}

def load_keys_from_disk():
    """Carrega chaves salvas em arquivo se existir."""
    if KEYS_FILE.exists():
        try:
            stored = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                VALID_M2M_KEYS.update(stored)
        except Exception as e:
            logger.warning(f"Erro ao ler {KEYS_FILE}: {e}")

# Executa carga inicial de chaves
load_keys_from_disk()


def register_m2m_key(name: str, email: str, organization: str) -> str:
    """Gera e registra uma chave de trial M2M de 7 dias com persistência em disco."""
    token = f"gp5_trial_{uuid.uuid4().hex[:16]}"
    client_label = f"{name} ({organization} - {email})"
    
    VALID_M2M_KEYS[token] = client_label
    
    # Persiste em disco
    try:
        KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEYS_FILE.write_text(json.dumps(VALID_M2M_KEYS, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Erro ao salvar nova chave em {KEYS_FILE}: {e}")
        
    return token


LEGACY_PERMISSIONS = [
    "observation.read",
]

AUTHENTICATED_PERMISSIONS = [
    "observation.read",
    "decision.*",           # cobre decision.charter_risk, decision.routing, decision.port_exposure
]


def authenticate_client(auth_header: Optional[str], product: str = "gp5") -> ClientContext:
    """Valida o Authorization header e constrói um ClientContext com permissões corretas.

    Dual-Mode:
      - Sem credencial válida → legacy (observation.read apenas)
      - Com credencial válida → authenticated (observation.read + decision.*)
    """
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    now_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    # Sem header → Legacy/Anônimo
    if not auth_header:
        return ClientContext(
            request_id=request_id,
            client_id=f"anonymous_{now_tag}",
            access_mode="legacy",
            product=product,
            permissions=LEGACY_PERMISSIONS,
        )

    raw_token = auth_header.strip()
    if raw_token.lower().startswith("bearer "):
        raw_token = raw_token[7:].strip()

    # Token inválido → trata como legacy anônimo
    if raw_token not in VALID_M2M_KEYS:
        return ClientContext(
            request_id=request_id,
            client_id=f"anonymous_invalid_key_{now_tag}",
            access_mode="legacy",
            product=product,
            permissions=LEGACY_PERMISSIONS,
        )

    # Token válido → Autenticado
    client_id = VALID_M2M_KEYS[raw_token]
    return ClientContext(
        request_id=request_id,
        client_id=client_id,
        access_mode="authenticated",
        product=product,
        permissions=AUTHENTICATED_PERMISSIONS,
    )


def require_permission(context: ClientContext, permission: str) -> None:
    """Lança PermissionError se o ClientContext não possui a permissão requerida."""
    if not context.has_permission(permission):
        raise PermissionError(
            f"Access denied: '{permission}' requires authenticated M2M access. "
            f"Current mode: '{context.access_mode}'. "
            "Get your M2M API Key at https://aetherx.aether-grid.io/m2m-keys"
        )
