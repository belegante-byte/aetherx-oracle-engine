"""Ontologia de intenção do Aether-X.

Famílias de intenção que conectam a descoberta ao problema que o Oracle
resolve (não apenas ao nome do produto). Reutilizada pelas superfícies de
texto (llms.txt, README, registry, páginas) e pela Control Tower para
classificar o motivo de um tool_call.

Não altera a semântica das métricas do funil — é uma camada de contexto
para descoberta e atribuição.
"""

INTENT_FAMILIES: dict[str, list[str]] = {
    "congestion": [
        "port congestion",
        "port congestion signal",
        "port congestion risk",
        "port operational pressure",
        "port congestion intelligence",
    ],
    "queue": [
        "vessel queue",
        "vessel queue intelligence",
        "ships waiting",
        "port waiting vessels",
        "vessels at anchor",
    ],
    "delay": [
        "port delay risk",
        "vessel delay",
        "ETA delay",
        "shipping delay",
        "port delay signal",
    ],
    "economic": [
        "demurrage exposure",
        "demurrage risk",
        "port delay cost",
        "shipping disruption",
        "demurrage intelligence",
    ],
    "decision": [
        "choose between ports",
        "compare ports",
        "route cargo",
        "assess port risk",
        "estimate delay exposure",
        "assess demurrage risk",
        "port selection",
        "vessel scheduling",
        "supply-chain disruption",
    ],
}

INTENT_LABELS: dict[str, str] = {
    "congestion": "port congestion signal",
    "queue": "vessel queue intelligence",
    "delay": "port delay risk / ETA delay",
    "economic": "demurrage exposure / port delay cost",
    "decision": "compare ports / route cargo / assess port risk",
}

# Lista achatada para uso em metadados (keywords, description, llms.txt).
ALL_INTENT_TERMS: list[str] = sorted({
    term
    for terms in INTENT_FAMILIES.values()
    for term in terms
})

# Frase de "when to call" por família, para tool description e instruções.
INTENT_CALL_GUIDE: dict[str, str] = {
    "congestion": "when a decision depends on current port congestion or operational pressure",
    "queue": "when the vessel queue / ships waiting at a port matters for scheduling",
    "delay": "when ETA delay risk or shipping delay affects the decision",
    "economic": "when demurrage exposure or port delay cost is the deciding factor",
    "decision": "when choosing between ports or routing cargo",
}


def intent_for_query(query: str) -> str | None:
    """Classifica uma query/texto em uma família de intenção (ou None)."""
    q = (query or "").lower()
    for family, terms in INTENT_FAMILIES.items():
        if any(term.lower() in q for term in terms):
            return family
    # decision: "compare" + porto(s) genérico (ex.: "compare Santos and Paranaguá")
    if "compare" in q or "choos" in q or "routing" in q or "select" in q:
        return "decision"
    return None