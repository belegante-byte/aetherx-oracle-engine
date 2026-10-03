import os
import json
import uuid
import logging
import threading
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

# token -> nível contratado do plano ("trial" | "pro" | "enterprise").
# Autoridade do gate de acesso da REST paga (engenharia de produto 2026-09-29).
_KEY_LEVELS: dict[str, str] = {}

_META_PLANS_KEY = "__plans__"
_META_GRANTS_KEY = "__payment_grants__"
_META_LEVELS_KEY = "__key_levels__"

# ── Modelo de acessos por plano (engenharia de produto, 2026-09-29). ─────────
# Referência única do que cada cliente contratou e do que a REST paga entrega.
# trial  -> só MCP (funil free; NUNCA abre REST de produto).
# pro    -> 5 portos BR com fila de autoridade + cobertura global de referência,
#           1 slot (integração concorrente) e quota diária de chamadas.
# enterprise -> tudo do Pro + fiscal/routing e análise ANTAQ (verified-queue),
#           até SLOT_LIMITS[enterprise] integrações concorrentes.
# Quotas de chamada e slots são limites por instância (best-effort, ver AGENTS.md).
PLAN_TRIAL = "trial"
PLAN_PRO = "pro"
PLAN_ENTERPRISE = "enterprise"
LEVEL_ORDER = {"": 0, PLAN_TRIAL: 1, PLAN_PRO: 2, PLAN_ENTERPRISE: 3}

# Endpoint REST paga -> nível mínimo do plano que pode consultá-lo.
MIN_LEVEL_BY_PATH: dict[str, str] = {
    # Pro (dados: sinais BR + estatística oficial ANTAQ + demurrage e referência global)
    "/v1/port-risk": PLAN_PRO,
    "/v1/port-trend": PLAN_PRO,
    "/v1/ports-risk": PLAN_PRO,
    "/v1/port-history": PLAN_PRO,
    "/v1/gp5/physical-events": PLAN_PRO,
    "/v1/gp5/charter-risk": PLAN_PRO,
    "/v1/gp5/corridor-risk": PLAN_PRO,
    "/v1/gp5/pci": PLAN_PRO,
    "/v1/gp5/cdr": PLAN_PRO,
    "/v1/gp5/vqpm": PLAN_PRO,
    "/v1/gp5/irdi": PLAN_PRO,
    "/v1/gp5/scdew": PLAN_PRO,
    # Enterprise (decisão: arbitragem de corredor + evidência validada ANTAQ)
    "/v1/gp5/routing-eval": PLAN_ENTERPRISE,
    "/v1/gp5/fiscal-routing": PLAN_ENTERPRISE,
    "/v1/verified-queue": PLAN_ENTERPRISE,
}

# Slots = integrações/consumidores simultâneos autorizados (NÃO quantidade de
# chamadas) — limite de concorrência por chave, por instância.
SLOT_LIMITS: dict[str, int] = {PLAN_PRO: 1, PLAN_ENTERPRISE: 5}

# Quota diária de chamadas por plano (independente dos slots).
# Sobrescreva via env se necessário (ex.: GP5_DAILY_CALL_QUOTA_PRO=1000).
DAILY_CALL_QUOTA: dict[str, int] = {
    PLAN_PRO: int(os.getenv("GP5_DAILY_CALL_QUOTA_PRO", "5000")),
    PLAN_ENTERPRISE: int(os.getenv("GP5_DAILY_CALL_QUOTA_ENTERPRISE", "50000")),
}

PLAN_LABEL: dict[str, str] = {
    PLAN_TRIAL: "Trial MCP (30d)",
    PLAN_PRO: "GP5 Pro",
    PLAN_ENTERPRISE: "GP5 Enterprise",
}

# Controle de concorrência (slots) e quota diária — por instância, em memória.
_SLOT_LOCK = threading.Lock()
_SLOT_USED: dict[str, int] = {}
_CALL_QUOTA_LOCK = threading.Lock()
_CALL_USED: dict[str, dict[str, int]] = {}  # token -> {"YYYY-MM-DD": count}


def _load_meta():
    if META_FILE.exists():
        try:
            stored = json.loads(META_FILE.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                for token, iso in stored.items():
                    if token in (_META_PLANS_KEY, _META_GRANTS_KEY, _META_LEVELS_KEY):
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
                levels_raw = stored.get(_META_LEVELS_KEY)
                if levels_raw:
                    try:
                        _KEY_LEVELS.update(json.loads(levels_raw))
                    except Exception:
                        logger.warning("Meta key levels corrompido; ignorado.")
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
        payload[_META_LEVELS_KEY] = json.dumps(_KEY_LEVELS)
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
    """Chave mestre nunca expira; chaves de trial expiram após TRIAL_VALIDITY_DAYS dias (30 por padrão).

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
    _KEY_LEVELS[token] = PLAN_TRIAL

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


def get_key_level(token: str) -> str:
    """Nível contratado ("trial" | "pro" | "enterprise") da chave.

    Chaves pagas legadas (sem nível gravado) assumem enterprise — todas as
    chaves pagas emitidas até aqui eram GP5 Enterprise. Chave desconhecida/
    expirada devolve "" (sem plano).
    """
    if not token:
        return ""
    if token in _KEY_LEVELS:
        return _KEY_LEVELS[token]
    if is_paid_key(token):
        return PLAN_ENTERPRISE
    if token in VALID_M2M_KEYS and not _token_expired(token):
        return PLAN_TRIAL
    return ""


def register_paid_m2m_key(
    name: str, email: str, organization: str, external_id: str,
    level: str = PLAN_ENTERPRISE,
) -> str:
    """Registra uma chave paga com idempotência e nível de plano.

    external_id é o identificador da transação na plataforma de pagamento
    (ex.: Stripe session/event id). Se o mesmo external_id já concedeu uma
    chave, devolve a MESMA chave em vez de duplicar.

    `level` controla o que a REST paga entrega (pro | enterprise) e o limite de
    slots/quota de chamadas — pré-requisito da engenharia de produto aprovada.
    """
    existing = _PAYMENT_GRANTS.get(external_id)
    if existing:
        return existing
    # Normaliza "GP5_ENTERPRISE"/"enterprise"/"pro" para o nível canônico.
    level = str(level or "").strip().lower()
    if level.startswith("gp5_"):
        level = level[4:]
    if level not in (PLAN_PRO, PLAN_ENTERPRISE):
        raise ValueError(f"level inválido: {level!r} (esperado 'pro' ou 'enterprise')")

    token = f"gp5_{level}_{uuid.uuid4().hex[:16]}"
    client_label = f"{name} ({organization} - {email})"

    VALID_M2M_KEYS[token] = client_label
    _KEY_META[token] = datetime.now(timezone.utc).isoformat()
    _KEY_PLANS[token] = "GP5_ENTERPRISE" if level == PLAN_ENTERPRISE else "GP5_PRO"
    _KEY_LEVELS[token] = level
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
        plan=get_key_level(raw_token),
    )


def require_permission(context: ClientContext, permission: str) -> None:
    """Lança PermissionError se o ClientContext não possui a permissão requerida."""
    if not context.has_permission(permission):
        raise PermissionError(
            f"Access denied: '{permission}' requires authenticated M2M access. "
            f"Current mode: '{context.access_mode}'. "
            "Get your M2M API Key at https://aetherx.aether-grid.io/m2m-keys"
        )


# ── Gates da REST paga (engenharia de produto 2026-09-29). ────────────────────
# Aplicados pelo M2MGatewayMiddleware APÓS o RapidAPIGuard validar que a chave
# é paga (ou o proxy-secret do RapidAPI). Nível de plano autoriza o endpoint;
# slots limitam integrações concorrentes; a quota é independente das chamadas.

def authorization_gate(token: str, path: str) -> dict:
    """Avalia nível do plano vs endpoint da REST paga.

    Retorna:
      {"allowed": True,  "plan": level, "endpoint": path}
      {"allowed": False, "code": "PLAN_REQUIRED", "required_plan": level,
       "plan": current, "endpoint": path, "feature": path}
    """
    required = MIN_LEVEL_BY_PATH.get(path.rsplit("?", 1)[0].rstrip("/"))
    level = get_key_level(token)
    if required and LEVEL_ORDER.get(level, 0) < LEVEL_ORDER.get(required, 0):
        return {
            "allowed": False,
            "code": "PLAN_REQUIRED",
            "required_plan": required,
            "required_level": LEVEL_ORDER.get(required),
            "plan": level,
            "endpoint": path,
            "feature": path,
        }
    return {"allowed": True, "plan": level, "endpoint": path, "required_plan": required}


def upgrade_hint(required_plan: str) -> str:
    """Mensagem comercial de upgrade (integridade: sem prometer o que não há)."""
    if required_plan == PLAN_ENTERPRISE:
        return (
            "Este endpoint exige o plano GP5 Enterprise (evidência ANTAQ validada, "
            "arbitragem de corredor e fiscal-routing). Upgrade em "
            "https://aetherx.aether-grid.io/m2m-keys ou via RapidAPI."
        )
    return (
        "Este endpoint exige o plano GP5 Pro (sinais dos 5 portos BR com estatística "
        "oficial ANTAQ e exposição de demurrage). Upgrade em "
        "https://aetherx.aether-grid.io/m2m-keys ou via RapidAPI."
    )


def acquire_slot(token: str) -> bool:
    """Tenta reservar um slot de integração concorrente para a chave.

    Slots são consumidores simultâneos autorizados (pro: 1, enterprise: 5) —
    NÃO quantidade de chamadas. Limite por instância de deploy.
    """
    limit = SLOT_LIMITS.get(get_key_level(token), 0)
    if limit <= 0:
        return False
    with _SLOT_LOCK:
        used = _SLOT_USED.get(token, 0)
        if used >= limit:
            return False
        _SLOT_USED[token] = used + 1
        return True


def release_slot(token: str) -> None:
    """Libera o slot de integração reservado por acquire_slot."""
    with _SLOT_LOCK:
        used = _SLOT_USED.get(token, 0)
        if used > 1:
            _SLOT_USED[token] = used - 1
        else:
            _SLOT_USED.pop(token, None)


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def consume_call_quota(token: str) -> dict:
    """Consome 1 chamada da quota diária do plano (independente dos slots).

    In-memory por instância (documentado como best-effort no AGENTS.md/CHANGELOG).
    Retorna {"allowed": bool, "used": int, "limit": int}.
    """
    level = get_key_level(token)
    limit = DAILY_CALL_QUOTA.get(level, 0)
    day = _today_key()
    with _CALL_QUOTA_LOCK:
        by_day = _CALL_USED.setdefault(token, {})
        used = by_day.get(day, 0)
        if limit > 0 and used >= limit:
            return {"allowed": False, "used": used, "limit": limit, "plan": level}
        by_day[day] = used + 1
        return {"allowed": True, "used": used + 1, "limit": limit, "plan": level}
