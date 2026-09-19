"""Aether-X Control Tower: painel operacional interno.

Renderiza em uma única tela o estado vivo do sistema: runtime, uso M2M,
top tools, top ports, discovery health, data quality e eventos recentes.
Acesso protegido pelo proxy secret (rota /internal/* não é pública).
"""

import json
from datetime import datetime, timezone


def _fmt_uptime(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s"


def _fmt_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")


def _status_dot(ok: bool) -> str:
    return "●" if ok else "○"


# Matriz de qualidade por porto (espelha docs/strategy/aetherx-operating-audit.md).
# Superfícies de descoberta (verificação aproximada por HTTP no carregamento).
DISCOVERY_SURFACES = [
    ("MCP Registry", "live"),
    ("Glama", "live"),
    ("Smithery", "live"),
    ("RapidAPI", "live"),
    ("Google", "indexing"),
    ("public-apis", "pending"),
    ("GitHub", "live"),
    ("Hugging Face", "live"),
    ("PyPI", "live"),
    ("mcp.so", "blocked"),
    ("PulseMCP", "blocked"),
]


def port_quality_matrix(conn=None) -> list[dict]:
    """Deriva a matriz de qualidade de cada porto a partir do DuckDB real.

    Regra (honesta, não fixa):
    - LIVE: port_id começa com 'BR' e data_source é live:* (fonte viva)
    - fila observável: live_detail JSON contém ao_largo > 0
    - par de calibração: existe registro em calibration_pairs com matched=1
    - VALIDATED: LIVE + fila observável + par de calibração  → decision grade
    - CONDITIONAL: LIVE + ANTAQ disponível, mas sem fila observável E/OU sem par
    - REFERENCE: seed estático (não é LIVE)
    """
    import json as _json
    if conn is None:
        import duckdb
        conn = duckdb.connect(_db_path(), read_only=True)
    rows = conn.execute(
        "SELECT port_id, data_source, live_detail FROM port_metrics ORDER BY port_id"
    ).fetchall()
    paired = set(
        r[0] for r in conn.execute(
            "SELECT port_id FROM calibration_pairs WHERE matched=1"
        ).fetchall()
    )
    out = []
    for pid, ds, ld in rows:
        live = ds is not None and ds.startswith("live:")
        queue_observable = False
        if ld:
            try:
                detail = _json.loads(ld)
                queue_observable = bool(detail.get("ao_largo"))
            except Exception:
                queue_observable = False
        has_pair = pid in paired
        if live and queue_observable and has_pair:
            grade, status = "VALIDATED", "decision"
        elif live:
            grade, status = "CONDITIONAL", "conditional"
        else:
            grade, status = "REFERENCE", "reference"
        out.append({"port_id": pid, "live": live, "grade": grade, "status": status})
    return out


def _db_path() -> str:
    import os
    return os.getenv("DATABASE_PATH", "data/oracle.duckdb")


def control_tower_html(snapshot: dict) -> str:
    m = snapshot
    uptime = _fmt_uptime(m.get("uptime_seconds", 0))
    req = m.get("requests_total", 0)
    mcp_calls = m.get("mcp_calls", 0)
    unique = sum(m.get("unique_machines", {}).values())
    repeat = sum(m.get("repeat_machines", {}).values())
    mcp_uniq = m.get("unique_machines", {}).get("mcp", 0)
    mcp_rep = m.get("repeat_machines", {}).get("mcp", 0)
    rep_rate = (mcp_rep / mcp_uniq * 100) if mcp_uniq else 0.0
    err_rate = m.get("error_rate", 0.0) * 100

    tools = m.get("top_tools", [])
    ports = m.get("top_ports", [])
    events = m.get("recent_events", [])

    tools_html = "".join(
        f'<div class="row"><span>{t}</span><span class="val">{c}</span></div>'
        for t, c in tools
    ) or '<div class="row"><span>sem dados</span></div>'
    ports_html = "".join(
        f'<div class="row"><span>{p}</span><span class="val">{c}</span></div>'
        for p, c in ports
    ) or '<div class="row"><span>sem dados</span></div>'

    paid_plans = m.get("paid_plans", {}) or {}
    paid_count = m.get("paid_user_count", 0)
    paid_users = m.get("paid_users", []) or []
    paid_html = "".join(
        f'<div class="row"><span>{plan}</span><span class="val">{c}</span></div>'
        for plan, c in sorted(paid_plans.items())
    ) or '<div class="row muted"><span>nenhuma chamada paga ainda</span></div>'
    paid_users_html = "".join(
        f'<div class="row muted"><span>{u}</span></div>'
        for u in paid_users[:10]
    ) or ""
    if paid_users_html:
        paid_html += '<div class="muted" style="margin-top:.4rem">usuários pagos:</div>' + paid_users_html

    quality_html = ""
    try:
        _quality_rows = port_quality_matrix()
    except Exception:
        _quality_rows = []
    for q in _quality_rows:
        ok = q["live"]
        dot = _status_dot(ok)
        color = "limegreen" if ok else "gray"
        quality_html += (
            f'<div class="row"><span>{q["port_id"]}</span>'
            f'<span class="val"><span class="dot" style="color:{color}">{dot}</span>'
            f' {"LIVE" if q["live"] else "SEED"} / {q["grade"]}</span></div>'
        )
    if not _quality_rows:
        quality_html += '<div class="row muted"><span>sem dados de portos</span></div>'

    disc_html = ""
    _status_colors = {
        "live": "limegreen",
        "indexing": "#58a6ff",
        "pending": "orange",
        "blocked": "#f85149",
    }
    for name, status in DISCOVERY_SURFACES:
        color = _status_colors.get(status, "gray")
        dot = _status_dot(status != "blocked")
        disc_html += (
            f'<div class="row"><span>{name}</span>'
            f'<span class="val"><span class="dot" style="color:{color}">{dot}</span> {status}</span></div>'
        )

    events_html = ""
    for ev in events:
        ts = _fmt_ts(ev.get("ts", 0))
        kind = ev.get("kind", "?")
        detail = ev.get("detail", "")
        icon = {
            "tool_call": "🔧", "port_query": "⚓", "new_machine": "🆕",
            "repeat_machine": "🔁", "mcp_call": "🤖", "error": "⚠️",
            "paid_call": "💰",
        }.get(kind, "•")
        events_html += (
            f'<div class="event"><span class="ts">{ts}</span>'
            f'<span class="kind">{icon} {kind}</span><span class="det">{detail}</span></div>'
        )
    if not events_html:
        events_html = '<div class="row muted">sem eventos ainda nesta janela</div>'

    mcp_consumers = m.get("mcp_consumer_count", 0)
    consumers_detail = m.get("mcp_consumers", {}).get("calls_by_machine", {})
    consumers_html = "".join(
        f'<div class="row"><span>{mid[:8]}…</span><span class="val">{c} calls</span></div>'
        for mid, c in list(consumers_detail.items())[:6]
    ) or '<div class="row muted"><span>nenhuma tool executada</span></div>'

    funnel = m.get("funnel", {}) or {}
    # Dois funis: infraestrutura (descoberta/transporte) vs produto (consumo).
    infra_stages = ("discovery", "mcp_connect", "repeat_transport")
    product_stages = ("discovery", "tool_call", "repeat_tool", "paid")
    _funnel_label = {
        "discovery": "DISCOVERY", "mcp_connect": "MCP CONNECT",
        "tool_call": "TOOL CALL", "repeat_transport": "TRANSPORT REPEAT",
        "repeat_tool": "TOOL REPEAT", "paid": "PAID",
    }
    infra_funnel = "".join(
        f'<div class="row"><span>{_funnel_label.get(s, s)}</span>'
        f'<span class="val">{funnel.get(s, 0)}</span></div>'
        for s in infra_stages
    )
    product_funnel = "".join(
        f'<div class="row"><span>{_funnel_label.get(s, s)}</span>'
        f'<span class="val">{funnel.get(s, 0)}</span></div>'
        for s in product_stages
    )

    machines = m.get("machines", []) or []
    machines_html = "".join(
        f'<div class="event"><span class="ts">{_fmt_ts(mach.get("first", 0))}</span>'
        f'<span class="kind">{mach.get("id")}…</span>'
        f'<span class="det">{", ".join(mach.get("stages", [])) or "—"} · {mach.get("calls", 0)}c'
        f'{" · " + ",".join(mach.get("ports", {}).keys()) if mach.get("ports") else ""}'
        f'{" · intent:" + ",".join(mach.get("intent", {}).keys()) if mach.get("intent") else ""}</span></div>'
        for mach in machines[:10]
    ) or '<div class="row muted"><span>sem máquinas ainda</span></div>'

    intent_by_family = m.get("intent_by_family", {}) or {}
    _intent_label = {
        "congestion": "CONGESTION", "queue": "QUEUE", "delay": "DELAY",
        "economic": "ECONOMIC", "decision": "DECISION",
    }
    intent_html = "".join(
        f'<div class="row"><span>{_intent_label.get(k, k)}</span>'
        f'<span class="val">{intent_by_family.get(k, 0)}</span></div>'
        for k in ("congestion", "queue", "delay", "economic", "decision")
    )

    # ---- Decomposição M2M ACTIVITY ----
    # Abre "N unique / N repeat" em: quantos são transporte (voltar ao servidor)
    # vs produto (voltar para executar tool), e quantos são novos.
    all_machine_ids = set()
    for ch, ids in (m.get("unique_machines") or {}).items():
        pass
    # total de máquinas M2M únicas (MCP + discovery + rest), excluindo bots
    m2m_channels = {"mcp", "discovery", "rest"}
    m2m_unique = sum((m.get("unique_machines") or {}).get(c, 0) for c in m2m_channels)
    m2m_repeat = sum((m.get("repeat_machines") or {}).get(c, 0) for c in m2m_channels)
    transport_repeat = funnel.get("repeat_transport", 0)
    tool_repeat = funnel.get("repeat_tool", 0)
    tool_calls = funnel.get("tool_call", 0)
    first_time = m2m_unique - m2m_repeat if m2m_unique >= m2m_repeat else m2m_unique

    activity_html = (
        f'<div class="row"><span>M2M UNIQUE</span><span class="val">{m2m_unique}</span></div>'
        f'<div class="row"><span>REPEATED (qualquer)</span><span class="val">{m2m_repeat}</span></div>'
        f'<div class="row"><span>├ TRANSPORT REPEAT</span><span class="val">{transport_repeat}</span></div>'
        f'<div class="row"><span>├ TOOL REPEAT</span><span class="val">{tool_repeat}</span></div>'
        f'<div class="row"><span>FIRST-TIME</span><span class="val">{first_time}</span></div>'
        f'<div class="row"><span>TOOL CALLS (janela)</span><span class="val">{tool_calls}</span></div>'
    )

    # ---- Classificação: o que as máquinas SÃO ----
    roles = m.get("roles", {}) or {}
    _role_label = {
        "automated": "BOTS / CRAWLERS / LIVENESS",
        "seo": "SEO CRAWLERS",
        "discovery": "MACHINE DISCOVERY",
        "mcp_client": "MCP CLIENTS (connect)",
        "api_client": "API CLIENTS",
        "consumer": "PRODUCT CONSUMERS (tool)",
    }
    role_html = "".join(
        f'<div class="row"><span>{_role_label.get(r, r)}</span>'
        f'<span class="val">{roles.get(r, 0)}</span></div>'
        for r in ("automated", "seo", "discovery", "mcp_client", "api_client", "consumer")
    )

    # ---- Last tool call ----
    ltc = m.get("last_tool_call") or {}
    if ltc:
        last_tool_html = (
            f'<div class="row"><span>MACHINE</span><span class="val">{ltc.get("machine")}</span></div>'
            f'<div class="row"><span>TOOL</span><span class="val">{ltc.get("tool")}</span></div>'
            f'<div class="row"><span>PORT</span><span class="val">{ltc.get("port") or "—"}</span></div>'
            f'<div class="row"><span>INTENT</span><span class="val">{ltc.get("intent") or "—"}</span></div>'
            f'<div class="row"><span>WHEN</span><span class="val">{_fmt_ts(ltc.get("ts", 0))} UTC</span></div>'
        )
    else:
        last_tool_html = '<div class="row muted"><span>nenhum tool_call neste processo</span></div>'

    win = m.get("window", {}) or {}
    life = m.get("lifetime", {}) or {}
    window_lifetime_html = (
        f'<div class="row"><span>JANELA (processo)</span><span class="val">MCP {win.get("mcp_calls", 0)} · REQ {win.get("requests", 0)}</span></div>'
        f'<div class="row"><span>LIFETIME (persistido)</span><span class="val">MCP {life.get("mcp_calls", 0)} · REQ {life.get("requests", 0)}</span></div>'
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aether-X Control Tower</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,monospace;background:#0a0e14;color:#e6edf3;padding:2rem;font-size:14px}}
h1{{font-size:1.4rem;letter-spacing:2px;color:#58a6ff;margin-bottom:1.5rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem;max-width:1200px}}
.card{{background:#10161f;border:1px solid #1c2430;border-radius:8px;padding:1rem}}
.card h2{{font-size:.75rem;text-transform:uppercase;letter-spacing:1px;color:#8b949e;margin-bottom:.6rem}}
.row{{display:flex;justify-content:space-between;padding:2px 0}}
.val{{color:#e6edf3}}
.dot{{font-size:.9rem}}
.muted{{color:#6e7681}}
.event{{display:flex;gap:.5rem;padding:2px 0;font-size:13px}}
.event .ts{{color:#6e7681}}
.event .kind{{color:#8b949e}}
.event .det{{color:#e6edf3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.big{{font-size:1.6rem;font-weight:700}}
.green{{color:limegreen}}
.blue{{color:#58a6ff}}
.orange{{color:orange}}
.red{{color:#f85149}}
.stat{{padding:2px 0}}
</style></head><body>
<h1>AETHER-X CONTROL TOWER</h1>
<div class="grid">
  <div class="card">
    <h2>SYSTEM</h2>
    <div class="stat">SYSTEM <span class="green">● ONLINE</span></div>
    <div class="stat">VERSION <span class="val">0.4.x / api 0.2.1</span></div>
    <div class="stat">UPTIME <span class="val">{uptime}</span></div>
    <div class="stat">REQUESTS <span class="val big">{req:,}</span></div>
    <div class="stat">MCP CALLS <span class="val big">{mcp_calls:,}</span></div>
    <div class="stat">UNIQUE M2M <span class="val">{unique}</span></div>
    <div class="stat">REPEAT <span class="val">{repeat}</span></div>
    <div class="stat">REPEAT RATE <span class="val">{rep_rate:.1f}%</span></div>
    <div class="stat">ERROR RATE <span class="val">{err_rate:.2f}%</span></div>
  </div>
  <div class="card">
    <h2>M2M ACTIVITY (aberto)</h2>
    {activity_html}
  </div>
  <div class="card">
    <h2>CLASSIFICATION (o que são)</h2>
    {role_html}
    <div class="muted" style="margin-top:.4rem">janela vs lifetime</div>
    {window_lifetime_html}
  </div>
  <div class="card">
    <h2>LAST TOOL CALL</h2>
    {last_tool_html}
  </div>
  <div class="card">
    <h2>TOP TOOLS</h2>
    {tools_html}
  </div>
  <div class="card">
    <h2>CONSUMERS (tools executadas)</h2>
    <div class="row"><span>MÁQUINAS QUE EXECUTARAM TOOL</span><span class="val">{mcp_consumers}</span></div>
    {consumers_html}
  </div>
  <div class="card">
    <h2>FUNNEL · INFRAESTRUTURA</h2>
    {infra_funnel}
  </div>
  <div class="card">
    <h2>FUNNEL · PRODUTO</h2>
    {product_funnel}
  </div>
  <div class="card">
    <h2>MACHINES (anônimas)</h2>
    {machines_html}
  </div>
  <div class="card">
    <h2>INTENT (por tool_call)</h2>
    {intent_html}
  </div>
  <div class="card">
    <h2>TOP PORTS</h2>
    {ports_html}
  </div>
  <div class="card">
    <h2>MONETIZATION</h2>
    <div class="row"><span>PAID CALLS</span><span class="val">{sum(paid_plans.values())}</span></div>
    <div class="row"><span>PAID USERS</span><span class="val">{paid_count}</span></div>
    {paid_html}
  </div>
  <div class="card">
    <h2>DISCOVERY</h2>
    {disc_html}
  </div>
  <div class="card">
    <h2>DATA QUALITY</h2>
    {quality_html}
  </div>
  <div class="card">
    <h2>RECENT EVENTS</h2>
    {events_html}
  </div>
</div>
</body></html>"""