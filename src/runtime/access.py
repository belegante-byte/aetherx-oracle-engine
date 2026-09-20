import os
import uuid
from typing import Optional
from datetime import datetime, timezone
from src.runtime.contracts.v1 import ClientContext

# ─── Credenciais M2M Bootstrap ────────────────────────────────────────────────
# Variável de ambiente M2M_API_SECRET define a primeira chave de bootstrap.
# Em produção, substituir por lookup em tabela/secrets manager.
_M2M_SECRET = os.getenv("M2M_API_SECRET", "gp5_m2m_default_secret_key")

VALID_M2M_KEYS: dict[str, str] = {
    _M2M_SECRET: "default_m2m_client",
}

# ─── Definição de permissões por modo de acesso ────────────────────────────────
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

    Não implementa billing. Emite apenas o contexto de identidade e permissões.
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

    # Token inválido → trata como legacy anônimo (não como cliente autenticado)
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
    """Lança PermissionError se o ClientContext não possui a permissão requerida.
    A ser chamado pelas ferramentas de Decision Layer antes de executar lógica.
    """
    if not context.has_permission(permission):
        raise PermissionError(
            f"Access denied: '{permission}' requires authenticated M2M access. "
            f"Current mode: '{context.access_mode}'. "
            "Provide a valid 'Authorization: Bearer <API_KEY>' header."
        )
