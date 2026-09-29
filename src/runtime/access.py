import os
import json
import uuid
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path
from src.runtime.contracts.v1 import ClientContext

logger = logging.getLogger("m2m_access")

# INTEGRIDADE/SEGURANÇA (auditoria 2026-09-21):
# - Não há mais segredo fallback hardcoded. O valor "gp5_m2m_default_secret_key"
#   foi exposto publicamente (commitado em data/m2m_keys.json) e é filtrado no
#   load. O segredo mestre DEVE vir de M2M_API_SECRET no ambiente.
# - Chaves de trial expiram após TRIAL_VALIDITY_DAYS (30 por padrão — funil
#   grátis permanente via observação anônima; trial longo p/ testes sérios); o
#   timestamp de emissão fica em m2m_keys_meta.json (não versionado no git).
_M2M_SECRET = os.getenv("M2M_API_SECRET")
TRIAL_VALIDITY_DAYS = int(os.getenv("M2M_TRIAL_VALIDITY_DAYS", "30"))
_COMPROMISED_DEFAULT_SECRET = "gp5_m2m_default_secret_key"
KEYS_FILE = Path(os.getenv("DATA_DIR", "data")) / "m2m_keys.json"
META_FILE = Path(os.getenv("DATA_DIR", "data")) / "m2m_keys_meta.json"

VALID_M2M_KEYS: dict[str, str] = {}
if _M2M_SECRET:
    VALID_M2M_KEYS[_M2M_SECRET] = "default_m2m_client"

# token -> ISO timestamp de emissão (nunca versionado — ver .gitignore)
_KEY_META: dict[str, str] = {}

# Chaves pagas (tokens) e planos associados (ex.: GP5_ENTERPRISE).
# Chaves pagas NUNCA expiram; são persistidas no mesmo cofre JSON que a auth lê.
_KEY_PLANS: dict[str, str] = {}

# Idempotência de pagamento: external_id (ex.: Stripe session/event id) -> token já concedido.
_PAYMENT_GRANTS: dict[str, str] = {}

_META_PLANS_KEY = "__plans__"
_META_GRANTS_KEY = "__payment_grants__"


def _load_meta():
    if META_FILE.exists():
        try:
            stored = json.loads(META_FILE.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                for token, iso in stored.items():
                    if token in (_META_PLANS_KEY, _META_GRANTS_KEY):
                        continue
                    _KEY_META[token] = iso
                plans_raw = stored.get(_META_PLANS_KEY)
                if plans_raw:
                    try:
                        _KEY_PLANS.update(json.loads(plans_raw))
                    except Exception:
                        logger.warning("Meta plans corrompido; ignorado.")
                grants_raw = stored.get(_META_GRANTS_KEY)
                if grants_raw:
                    try:
                        _PAYMENT_GRANTS.update(json.loads(grants_raw))
                    except Exception:
                        logger.warning("Meta payment grants corrompido; ignorado.")
        except Exception as e:
            logger.warning(f"Erro ao ler {META_FILE}: {e}")


def _persist_keys():
    try:
        KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Nunca persiste o segredo mestre do ambiente em disco.
        to_disk = {
            k: v for k, v in VALID_M2M_KEYS.items()
            if not (_M2M_SECRET and k == _M2M_SECRET)
        }
        KEYS_FILE.write_text(json.dumps(to_disk, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Erro ao salvar chaves em {KEYS_FILE}: {e}")


def _persist_meta():
    try:
        META_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(_KEY_META)
        payload[_META_PLANS_KEY] = json.dumps(_KEY_PLANS)
        payload[_META_GRANTS_KEY] = json.dumps(_PAYMENT_GRANTS)
        META_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Erro ao salvar metadados em {META_FILE}: {e}")


def load_keys_from_disk():
    """Carrega chaves salvas em arquivo se existir.

    Filtra o antigo segredo default (comprometido publicamente no histórico git).
    """
    if KEYS_FILE.exists():
        try:
            stored = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                stored.pop(_COMPROMISED_DEFAULT_SECRET, None)
                VALID_M2M_KEYS.update(stored)
        except Exception as e:
            logger.warning(f"Erro ao ler {KEYS_FILE}: {e}")
    _load_meta()


def _token_expired(token: str) -> bool:
    """Chave mestre nunca expira; chaves de trial expiram após 7 dias.

    Chaves legado sem timestamp são consideradas válidas (continuidade de
    operação), mas emitem warning para que sejam rotacionadas — as trial keys
    antigas foram expostas no histórico git.
    """
    if _M2M_SECRET and token == _M2M_SECRET:
        return False
    # Chaves pagas (GP5 Enterprise) validam por assinatura ativa, não por idade.
    if token in _KEY_PLANS:
        return False
    issued = _KEY_META.get(token)
    if not issued:
        logger.warning(
            f"[M2M] Chave {token[:16]}... sem timestamp de emissão (legado). "
            "Considere rotacionar (o arquivo foi exposto no histórico git)."
        )
        return False
    try:
        issued_dt = datetime.fromisoformat(issued)
        if issued_dt.tzinfo is None:
            issued_dt = issued_dt.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - issued_dt
        return age > timedelta(days=TRIAL_VALIDITY_DAYS)
    except Exception:
        return True


load_keys_from_disk()


def register_m2m_key(name: str, email: str, organization: str) -> str:
    """Gera e registra uma chave de trial M2M de TRIAL_VALIDITY_DAYS dias (padrão 30)."""
    token = f"gp5_trial_{uuid.uuid4().hex[:16]}"
    client_label = f"{name} ({organization} - {email})"

    VALID_M2M_KEYS[token] = client_label
    _KEY_META[token] = datetime.now(timezone.utc).isoformat()

    _persist_keys()
    _persist_meta()

    return token


def is_paid_key(token: str) -> bool:
    """True se o token é uma chave PAGA (assinatura ativa), não trial.

    Chaves pagas são registradas via `register_paid_m2m_key` (Stripe). Chaves
    de trial NÃO passam aqui: trial dá acesso MCP, mas não abre a REST de
    produto (Governança, ver AGENTS.md).
    """
    if not token:
        return False
    return token in _KEY_PLANS or token in _PAYMENT_GRANTS.values()


def register_paid_m2m_key(name: str, email: str, organization: str, external_id: str) -> str:
    """Registra uma chave paga (GP5 Enterprise) com idempotência.

    external_id é o identificador da transação na plataforma de pagamento
    (ex.: Stripe session/event id). Se o mesmo external_id já concedeu uma
    chave, devolve a MESMA chave em vez de duplicar.
    """
    existing = _PAYMENT_GRANTS.get(external_id)
    if existing:
        return existing

    token = f"gp5_enterprise_{uuid.uuid4().hex[:16]}"
    client_label = f"{name} ({organization} - {email})"

    VALID_M2M_KEYS[token] = client_label
    _KEY_META[token] = datetime.now(timezone.utc).isoformat()
    _KEY_PLANS[token] = "GP5_ENTERPRISE"
    _PAYMENT_GRANTS[external_id] = token

    _persist_keys()
    _persist_meta()

    return token


def get_paid_key_for_email(email: str) -> Optional[str]:
    """Devolve a chave paga já emitida para um e-mail, se existir."""
    for token, label in VALID_M2M_KEYS.items():
        if token in _KEY_PLANS and label.endswith(f"- {email})"):
            return token
    return None


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

    # Token inválido ou expirado → trata como legacy anônimo
    if raw_token not in VALID_M2M_KEYS or _token_expired(raw_token):
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
