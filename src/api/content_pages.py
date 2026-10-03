"""Landing content pages: Aether Grid MCP demo page, SEO intent pages and sitemap.

All pages reuse the same dark theme as the landing page and render the
oracle signals (calculate_port_risk / calculate_port_trend). Every page
states the data provenance explicitly: Brazilian ports (BRPNG/BRSSZ/BRRIO/BRNIT/BRITG) are fed
by live line-ups; the rest serve a static reference seed.
"""

import html
import json
from pathlib import Path

from src.engine.risk_model import calculate_port_risk, calculate_port_trend
from src.products.gp5.fiscal import evaluate_fiscal_routing

PRODUCTION_URL = "https://aetherx.aether-grid.io"
RAPIDAPI_URL = "https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle"
REGISTRY_URL = "io.github.belegante-byte/aetherx-mcp"
PYPI_SDK = "https://pypi.org/project/aetherx-oracle/"
PYPI_MCP = "https://pypi.org/project/aetherx-mcp/"

REMOTE_CFG = '{"mcpServers": {"aetherx-oracle": {"type": "url", "url": "%s/mcp"}}}' % PRODUCTION_URL
STDIO_CFG = '{"mcpServers": {"aetherx-oracle": {"command": "uvx", "args": ["aetherx-mcp"]}}}'

# Portos & chokepoints monitorados, espelhando src/engine/init_prod_db.py. O slug alimenta
# o SEO programático (/port-congestion-<slug>) e o sitemap.
PORT_METAS = [
    {"port_id": "BRSSZ", "slug": "santos", "port_name": "Santos", "country": "Brasil"},
    {"port_id": "BRPNG", "slug": "paranagua", "port_name": "Paranaguá", "country": "Brasil"},
    {"port_id": "BRRIO", "slug": "rio-de-janeiro", "port_name": "Rio de Janeiro", "country": "Brasil"},
    {"port_id": "BRNIT", "slug": "niteroi", "port_name": "Niterói", "country": "Brasil"},
    {"port_id": "BRITG", "slug": "itaguai", "port_name": "Itaguaí", "country": "Brasil"},
    {"port_id": "BRRGD", "slug": "rio-grande", "port_name": "Rio Grande", "country": "Brasil"},
    {"port_id": "BRVDC", "slug": "barcarena-vila-do-conde", "port_name": "Barcarena / Vila do Conde", "country": "Brasil"},
    {"port_id": "BRMAO", "slug": "itaqui-sao-luis", "port_name": "Itaqui / São Luís", "country": "Brasil"},
    {"port_id": "ARROS", "slug": "rosario-san-lorenzo", "port_name": "Rosario / San Lorenzo", "country": "Argentina"},
    {"port_id": "ARBUE", "slug": "buenos-aires", "port_name": "Buenos Aires", "country": "Argentina"},
    {"port_id": "CNSHA", "slug": "shanghai", "port_name": "Shanghai", "country": "China"},
    {"port_id": "CNNGB", "slug": "ningbo-zhoushan", "port_name": "Ningbo-Zhoushan", "country": "China"},
    {"port_id": "CNTAO", "slug": "qingdao", "port_name": "Qingdao", "country": "China"},
    {"port_id": "CNTXG", "slug": "tianjin", "port_name": "Tianjin", "country": "China"},
    {"port_id": "CNSZX", "slug": "shenzhen-yantian", "port_name": "Shenzhen / Yantian", "country": "China"},
    {"port_id": "SGSIN", "slug": "singapore", "port_name": "Singapore", "country": "Cingapura"},
    {"port_id": "KRPUS", "slug": "busan", "port_name": "Busan", "country": "Coreia do Sul"},
    {"port_id": "JPTYO", "slug": "tokyo-yokohama", "port_name": "Tokyo / Yokohama", "country": "Japão"},
    {"port_id": "USMSY", "slug": "new-orleans-mississippi", "port_name": "New Orleans / Mississippi", "country": "EUA"},
    {"port_id": "USHOU", "slug": "houston", "port_name": "Houston", "country": "EUA"},
    {"port_id": "USLAX", "slug": "los-angeles", "port_name": "Los Angeles", "country": "EUA"},
    {"port_id": "USNYC", "slug": "new-york", "port_name": "New York", "country": "EUA"},
    {"port_id": "USSEA", "slug": "seattle-tacoma", "port_name": "Seattle / Tacoma", "country": "EUA"},
    {"port_id": "CAVAN", "slug": "vancouver", "port_name": "Vancouver", "country": "Canadá"},
    {"port_id": "NLAMS", "slug": "amsterdam", "port_name": "Amsterdam", "country": "Holanda"},
    {"port_id": "NLRTM", "slug": "rotterdam", "port_name": "Rotterdam", "country": "Holanda"},
    {"port_id": "DEHAM", "slug": "hamburg", "port_name": "Hamburg", "country": "Alemanha"},
    {"port_id": "BEANT", "slug": "antwerp", "port_name": "Antwerp", "country": "Bélgica"},
    {"port_id": "GBLGP", "slug": "london-gateway", "port_name": "London Gateway", "country": "Reino Unido"},
    {"port_id": "MPTNG", "slug": "tanger-med", "port_name": "Tanger Med", "country": "Marrocos"},
    {"port_id": "AEDXB", "slug": "dubai-jebel-ali", "port_name": "Dubai / Jebel Ali", "country": "EAU"},
    {"port_id": "SARAN", "slug": "ras-tanura", "port_name": "Ras Tanura", "country": "Arábia Saudita"},
    {"port_id": "PABLB", "slug": "panama-canal-balboa", "port_name": "Canal do Panamá / Balboa", "country": "Panamá"},
    {"port_id": "EGSUZ", "slug": "suez-canal-port-said", "port_name": "Canal de Suez / Port Said", "country": "Egito"},
    {"port_id": "ZACPT", "slug": "cape-town", "port_name": "Cape Town", "country": "África do Sul"},
    {"port_id": "ITGOA", "slug": "genoa", "port_name": "Genoa", "country": "Itália"},
    {"port_id": "HORMUZ", "slug": "strait-of-hormuz", "port_name": "Strait of Hormuz", "country": "Omã / Irã (Chokepoint)"},
    {"port_id": "MXZLO", "slug": "manzanillo", "port_name": "Manzanillo", "country": "México"},
]

_SLUG_MAP = {m["slug"]: m for m in PORT_METAS}
# Cobertura declarada nos textos públicos. Derivada do dataset para nunca
# voltar a divergir do que o produto realmente serve.
COVERAGE_COUNT = len(PORT_METAS)

CSS = """\
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#0a0e14;color:#e6edf3;line-height:1.7;min-height:100vh}
a{color:#58a6ff;text-decoration:none}
a:hover{text-decoration:underline}
.container{max-width:760px;margin:0 auto;padding:3rem 1.5rem}
.breadcrumb{font-size:0.75rem;color:#8b949e;margin-bottom:1.6rem}
.breadcrumb a{color:#8b949e}
h1{font-size:1.85rem;font-weight:700;margin-bottom:0.6rem;line-height:1.3}
h2{font-size:1.25rem;font-weight:700;margin:2.2rem 0 0.7rem}
h3{font-size:1rem;font-weight:700;margin:1.4rem 0 0.4rem}
p{margin-bottom:1rem;color:#c9d1d9}
.lede{font-size:1.05rem;color:#e6edf3}
.muted{color:#8b949e;font-size:0.9rem}
.pill{display:inline-block;font-size:0.72rem;padding:3px 12px;border-radius:20px;font-weight:600;margin:0 6px 6px 0}
.pill-green{background:#00d9921a;color:#00d992;border:1px solid #00d99244}
.pill-blue{background:#58a6ff1a;color:#58a6ff;border:1px solid #58a6ff44}
.pill-amber{background:#d299221a;color:#d29922;border:1px solid #d2992244}
.snippet-card{background:#161b22;border:1px solid #21262d;border-radius:8px;margin:0.6rem 0 1.2rem;overflow:hidden}
.card-header{display:flex;justify-content:space-between;align-items:center;gap:0.6rem;padding:0.5rem 0.9rem;border-bottom:1px solid #21262d;font-size:0.8rem;font-weight:600;color:#8b949e;background:#0d1117}
pre{margin:0;padding:0.9rem;font-size:0.82rem;line-height:1.55;overflow-x:auto;color:#e6edf3}
code{font-family:'SF Mono',SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace}
ul,ol{padding-left:1.4rem;margin-bottom:1.2rem;color:#c9d1d9}
li{margin-bottom:0.35rem}
table{border-collapse:collapse;width:100%;margin:0.8rem 0 1.4rem;font-size:0.85rem}
th,td{border:1px solid #21262d;padding:0.5rem 0.7rem;text-align:left}
th{background:#161b22;color:#e6edf3}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0.4rem;margin:0.8rem 0}
.metric{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:0.7rem}
.metric span{display:block;font-size:0.62rem;color:#8b949e;text-transform:uppercase;letter-spacing:.05em}
.metric b{font-size:0.95rem;font-variant-numeric:tabular-nums}
.cta{display:inline-block;background:#238636;color:#fff;font-weight:600;font-size:0.9rem;padding:0.65rem 1.3rem;border-radius:6px;margin:1.2rem 0}
.cta:hover{background:#2ea043;text-decoration:none}
.footer{margin-top:3rem;padding-top:1.5rem;border-top:1px solid #21262d;color:#8b949e;font-size:0.75rem}
@media(max-width:640px){.metrics{grid-template-columns:1fr 1fr}}
"""


def _json_pre(payload) -> str:
    code = json.dumps(payload, ensure_ascii=False, indent=2)
    return f'<div class="snippet-card"><div class="card-header"><span>Example response</span></div><pre><code>{html.escape(code)}</code></pre></div>'


def _page(title: str, meta_description: str, h1: str, lede: str, body: str, canonical_suffix: str, og_title: str | None = None) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{meta_description}">
<meta property="og:title" content="{og_title or title}">
<meta property="og:description" content="{meta_description}">
<meta property="og:type" content="website">
<meta property="og:url" content="{PRODUCTION_URL}{canonical_suffix}">
<link rel="canonical" href="{PRODUCTION_URL}{canonical_suffix}">
<style>{CSS}</style>
</head>
<body>
<div class="container">
<div class="breadcrumb"><a href="/">Aether Grid Port Congestion Oracle</a> /</div>
<h1>{h1}</h1>
<p class="lede muted">{lede}</p>
{body}
<div class="footer">Aether Grid Port Congestion Oracle &middot; Free trial 30 dias <a href="{PRODUCTION_URL}/m2m-keys">/m2m-keys</a> &middot; <a href="{RAPIDAPI_URL}">RapidAPI</a> &middot; <a href="{PYPI_SDK}">PyPI SDK</a> &middot; <a href="{PYPI_MCP}">MCP server</a> &middot; MCP Registry: {REGISTRY_URL}</div>
</div>
</body>
</html>"""


def _quickstart_block() -> str:
    return f"""{_json_pre(calculate_port_risk("BRSSZ"))}
<h2>Try it in under 3 minutes</h2>
<p>Install the typed Python SDK and call a port by its UN/LOCODE:</p>
<div class="snippet-card"><div class="card-header"><span>Python</span></div><pre><code>pip install --upgrade aetherx-oracle

from aetherx import OracleClient

client = OracleClient(api_key="YOUR_RAPIDAPI_KEY")
risk = client.get_port_risk("BRSSZ")
print(risk.congestion_score)
print(risk.estimated_daily_demurrage_usd)</code></pre></div>
<p>Get a free 30-day trial key at <a href="{PRODUCTION_URL}/m2m-keys">/m2m-keys</a>; paid access via <a href="{PRODUCTION_URL}/m2m-keys">RapidAPI subscription</a> or direct contact at <a href="mailto:contato@aether-grid.io">contato@aether-grid.io</a>.</p>
<a class="cta" href="{PRODUCTION_URL}/fiscal-demo">See the fiscal demo</a>
<h2>MCP server for AI agents</h2>
<p>The same signal is exposed over the Model Context Protocol, so agents call <code>get_port_risk</code>, <code>get_ports_risk</code> and <code>get_port_trend</code> directly:</p>
<div class="snippet-card"><div class="card-header"><span>Claude Desktop / Cursor / any MCP client</span></div><pre><code>{STDIO_CFG}</code></pre></div>
<p>Or use the hosted remote endpoint (no install): <code>{PRODUCTION_URL}/mcp</code>. Published in the <a href="https://registry.modelcontextprotocol.io">Official MCP Registry</a> as <code>{REGISTRY_URL}</code>.</p>"""


def mcp_page_html() -> str:
    body = f"""<div class="snippet-card"><div class="card-header"><span>Data integrity</span></div><pre><code>Brazilian ports (BRPNG/BRSSZ/BRRIO/BRNIT/BRITG) serve LIVE line-ups from
APPA Paranaguá, Porto de Santos, Lachmann schedules and SILOG PortosRio.
Other ports serve data_source="static_reference_seed".
Every response includes data_source and as_of.</code></pre></div>
<p class="lede">Query port congestion signals, ETA delays, vessel queues and modeled demurrage exposure through an <strong>MCP-compatible AI agent</strong>.</p>
<span class="pill pill-blue">Remote MCP Online</span>
<span class="pill pill-blue">Official MCP Registry</span>
<span class="pill pill-blue">PyPI: aetherx-mcp</span>

<h2>Available tools</h2>
<table>
<tr><th>Tool</th><th>What it does</th></tr>
<tr><td><code>get_port_risk</code></td><td>Congestion score, ETA delay, waiting vessels, freight volatility and daily demurrage for one port.</td></tr>
<tr><td><code>get_ports_risk</code></td><td>The same signal for up to 20 ports in a single call (portfolio scans).</td></tr>
<tr><td><code>get_port_trend</code></td><td>24h / 48h / 72h congestion projection with trend label.</td></tr>
</table>

<h2>Ask your agent directly</h2>
<ul>
<li>"What's the congestion risk at Santos?"</li>
<li>"Compare Santos, Shanghai and Rotterdam."</li>
<li>"Which of these ports currently has the highest modeled demurrage exposure?"</li>
<li>"Show me the 72-hour congestion trend for Santos."</li>
<li>"Scan my portfolio of 10 ports and rank them by congestion risk."</li>
</ul>

<h2>Install</h2>
<h3>Remote (no install)</h3>
<div class="snippet-card"><div class="card-header"><span>MCP client config</span></div><pre><code>{REMOTE_CFG}</code></pre></div>
<h3>Local (stdio)</h3>
<div class="snippet-card"><div class="card-header"><span>MCP client config</span></div><pre><code>{STDIO_CFG}</code></pre></div>

<h2>Where it lives</h2>
<ul>
<li><a href="{REGISTRY_URL}">Official MCP Registry</a> — <code>{REGISTRY_URL}</code> (active)</li>
<li><a href="{PYPI_MCP}">PyPI — aetherx-mcp</a></li>
<li><a href="https://glama.ai/mcp/connectors/io.github.belegante-byte/aetherx-mcp">Glama</a> · <a href="https://smithery.ai/servers/belegante/aetherx-mcp">Smithery</a></li>
<li><a href="{PRODUCTION_URL}/docs">Swagger UI</a> · <a href="{PRODUCTION_URL}" class="__rEST__">REST API</a></li>
</ul>

<h2>Reference signal (Santos)</h2>{live_card("BRSSZ")}
<a class="cta" href="{PRODUCTION_URL}/m2m-keys">Get a free trial key (REST)</a>
"""
    return _page(
        "Aether Grid MCP — Port Congestion Server for AI Agents",
        "MCP server for live Brazilian port line-ups and reference global port congestion signals. Tools: get_port_risk, get_ports_risk, get_port_trend. Remote endpoint and PyPI install.",
        "Aether Grid MCP: Port Congestion for AI Agents",
        "Connect any MCP-compatible agent to congestion signals for Brazilian ports (live line-ups) and reference signals for global ports.",
        body,
        "/mcp-page",
    )


def port_congestion_api_page() -> str:
    body = f"""<p>Congestion is a fast-moving signal, and Brazilian ports now feed real operational data. <strong>Santos (BRSSZ)</strong> and <strong>Paranaguá (BRPNG)</strong> pull live line-ups from APPA Paranaguá, the Porto de Santos operations panel and Lachmann schedules; the remaining ports serve a <strong>reference seed</strong>. Every response carries <code>data_source</code> (<code>live:appa+santos+lachmann</code> or <code>static_reference_seed</code>) and <code>as_of</code> so you know exactly what you are looking at.</p>
<h2>What a port congestion score tells you</h2>
<ul>
<li><strong>Congestion score (0.0–1.0)</strong> — normalized risk of operational congestion at the port.</li>
<li><strong>ETA delay (days)</strong> — expected delay applied to incoming vessels.</li>
<li><strong>Waiting vessels</strong> — ships anchored or queued.</li>
<li><strong>Freight volatility index</strong> — pressure indicator for freight pricing.</li>
<li><strong>Daily demurrage exposure (USD)</strong> — modeled cost for a vessel queued at the port.</li>
</ul>
<h2>One API call</h2>
<p>A single REST request returns the full signal for a port:</p>
<div class="snippet-card"><div class="card-header"><span>HTTP</span></div><pre><code>GET /v1/port-risk?port_id=BRSSZ</code></pre></div>
{_quickstart_block()}
"""
    return _page(
        "Port Congestion API — Port Risk, ETA Delay & Demurrage",
        f"Port congestion API, vessel queue intelligence, port delay risk / ETA delay and demurrage exposure for {COVERAGE_COUNT} registered ports & global chokepoints (5 Brazilian ports with live authority line-ups, the rest reference seed). Choose between ports, route cargo and assess demurrage risk.",
        "Port Congestion API",
        "Port congestion signal, vessel queue, ETA delay and demurrage exposure — live line-ups for Brazilian ports, reference seed elsewhere.",
        body,
        "/port-congestion-api",
    )


def santos_port_congestion_api_page() -> str:
    live = calculate_port_risk("BRSSZ")
    risk = {k: live[k] for k in ("congestion_score", "eta_delay_days", "waiting_vessels", "freight_volatility_index", "estimated_daily_demurrage_usd")}
    body = f"""<p>Santos (BRSSZ) is Latin America's busiest container port and a critical chokepoint for Brazilian agri-mineral exports and imports. Monitoring its congestion is essential for importers, exporters, freight forwarders and commodity desks.</p>
<h2>Santos live signal</h2>
<div class="metrics">
<div class="metric"><span>Congestion score</span><b>{risk['congestion_score']:.2f}</b></div>
<div class="metric"><span>ETA delay</span><b>{risk['eta_delay_days']:.1f} days</b></div>
<div class="metric"><span>Waiting vessels</span><b>{risk['waiting_vessels']}</b></div>
<div class="metric"><span>Demurrage/day</span><b>${risk['estimated_daily_demurrage_usd']:,}</b></div>
</div>
<p class="muted">Live values from the Porto de Santos operations panel, data_source {live.get('data_source')} (as_of {live.get('as_of', live.get('updated_at', 'n/a'))}).</p>
{_json_pre({"port_id": "BRSSZ", "port_name": "Santos", "country": "Brasil", **risk})}
<h2>Track Santos programmatically</h2>
<div class="snippet-card"><div class="card-header"><span>Python SDK</span></div><pre><code>pip install --upgrade aetherx-oracle

from aetherx import OracleClient

client = OracleClient(api_key="YOUR_RAPIDAPI_KEY")
risk = client.get_port_risk("BRSSZ")
print(risk.congestion_score, risk.eta_delay_days)</code></pre></div>
<p>Add the 24/48/72h trend with <code>client.get_port_trend("BRSSZ")</code>, or monitor several Brazilian ports at once with <code>client.get_ports_risk(["BRSSZ", "BRRIO"])</code>. AI agents can consume the same data via the <a href="/mcp-page">Aether Grid MCP server</a>.</p>
<a class="cta" href="{PRODUCTION_URL}/m2m-keys">Get a free trial key for Santos data</a>
"""
    return _page(
        "Santos Port Congestion API — Reference Risk & ETA",
        "Santos (BRSSZ) port congestion reference data: congestion score, ETA delay, waiting vessels and daily demurrage via REST, Python SDK or MCP (static seed, not live).",
        "Santos Port Congestion API",
        "Reference congestion risk, ETA delay and demurrage for Santos (BRSSZ), the busiest container port in Latin America.",
        body,
        "/santos-port-congestion-api",
    )


def port_congestion_python_page() -> str:
    body = f"""<p>You don't need heavy infrastructure to monitor port congestion. With a typed Python SDK you can pull congestion scores, ETA delays and demurrage exposure for {COVERAGE_COUNT} registered ports & global chokepoints (5 Brazilian ports with live authority line-ups, the rest reference seed) in a few lines.</p>
<h2>How to monitor port congestion with Python</h2>
<div class="snippet-card"><div class="card-header"><span>1. Install</span></div><pre><code>pip install --upgrade aetherx-oracle</code></pre></div>
<div class="snippet-card"><div class="card-header"><span>2. Call a port</span></div><pre><code>from aetherx import OracleClient

client = OracleClient(api_key="YOUR_RAPIDAPI_KEY")

risk = client.get_port_risk("BRSSZ")   # Santos
print(risk.port_name)
print(risk.congestion_score)
print(risk.eta_delay_days)
print(risk.estimated_daily_demurrage_usd)</code></pre></div>
<div class="snippet-card"><div class="card-header"><span>3. Scan a portfolio in one call</span></div><pre><code>results = client.get_ports_risk(["BRSSZ", "CNSHA", "NLRTM", "USLAX", "SGSIN"])
for r in sorted(results, key=lambda x: x.congestion_score, reverse=True):
    print(f"{{r.port_id:<6}} {{r.congestion_score:.2f}}  {{r.estimated_daily_demurrage_usd:,}}/day")</code></pre></div>
<div class="snippet-card"><div class="card-header"><span>4. Add the 24/48/72h trend</span></div><pre><code>trend = client.get_port_trend("NLRTM")
print(trend.trend)
print(trend.projection["h48"].congestion_score)</code></pre></div>
<h2>Async example</h2>
<p>For quants and supply-chain monitors that poll many ports, use the async extra to parallelize:</p>
<div class="snippet-card"><div class="card-header"><span>pip install aetherx-oracle[async]</span></div><pre><code>import asyncio
from aetherx import OracleClient

async def main():
    client = OracleClient(api_key="YOUR_RAPIDAPI_KEY")
    risks = await client.get_ports_risk_async(["BRSSZ", "CNSHA", "NLRTM"])
    for r in risks:
        print(r.port_id, r.congestion_score)

asyncio.run(main())</code></pre></div>
{_json_pre(calculate_port_risk("NLRTM"))}
<p>The same signal is available through the <a href="/mcp-page">MCP server for AI agents</a> and the plain REST API (<code>{PRODUCTION_URL}/v1/port-risk?port_id=BRSSZ</code>).</p>
<a class="cta" href="{PRODUCTION_URL}/m2m-keys">Get a free trial key (REST)</a>
"""
    return _page(
        "Port Congestion API with Python — Quick Start SDK",
        "Monitor port congestion with Python: install the aetherx-oracle SDK, call Santos, scan a portfolio of ports and add 24/48/72h ETA delay trends.",
        "Port Congestion Monitoring with Python",
        f"A 3-minute, typed-Python quick start for congestion scores, ETA delays and demurrage exposure across {COVERAGE_COUNT} registered ports & global chokepoints (5 Brazilian ports with live authority line-ups, the rest reference seed).",
        body,
        "/port-congestion-python",
    )


def live_card(port_id: str) -> str:
    risk = calculate_port_risk(port_id)
    metrics = (
        f'<div class="metric"><span>Score</span><b>{risk["congestion_score"]:.2f}</b></div>'
        f'<div class="metric"><span>ETA delay</span><b>{risk["eta_delay_days"]:.1f}d</b></div>'
        f'<div class="metric"><span>Waiting</span><b>{risk["waiting_vessels"]}</b></div>'
        f'<div class="metric"><span>Demurrage</span><b>${risk["estimated_daily_demurrage_usd"]:,}</b></div>'
    )
    return f'<div class="metrics">{metrics}</div>'


def port_detail_page(port_id: str, slug: str) -> str:
    """Página SEO única por porto, com dados de referência do seed (risco + tendência)."""
    risk = calculate_port_risk(port_id)
    trend = calculate_port_trend(port_id)
    port_name = risk["port_name"]
    country = risk["country"]
    proj = trend["projection"]
    ds_label = risk.get("data_source_label") or ("live line-ups" if risk.get("data_source", "").startswith("live:") else "static reference seed")
    body = f"""<p>Congestion signal for <strong>{html.escape(port_name)} ({port_id}), {html.escape(country)}</strong> — {ds_label}, data_source={risk.get('data_source')} updated at {risk.get('as_of', risk.get('updated_at', 'n/a'))}.</p>
{live_card(port_id)}
<h2>What this data means</h2>
<ul>
<li><strong>Congestion score ({risk['congestion_score']:.2f})</strong> — normalized 0.0–1.0 risk of operational congestion.</li>
<li><strong>ETA delay ({risk['eta_delay_days']:.1f} days)</strong> — expected delay applied to incoming vessels.</li>
<li><strong>Waiting vessels ({risk['waiting_vessels']})</strong> — ships anchored or queued at the port.</li>
<li><strong>Freight volatility ({risk['freight_volatility_index']:.2f})</strong> — pressure indicator for freight pricing.</li>
<li><strong>Daily demurrage (${risk['estimated_daily_demurrage_usd']:,})</strong> — estimated cost for a vessel queued at the port.</li>
</ul>
<h2>24 / 48 / 72h projection</h2>
<div class="metrics">
<div class="metric"><span>24h</span><b>{proj['h24']['congestion_score']:.2f}</b></div>
<div class="metric"><span>48h</span><b>{proj['h48']['congestion_score']:.2f}</b></div>
<div class="metric"><span>72h</span><b>{proj['h72']['congestion_score']:.2f}</b></div>
<div class="metric"><span>Trend</span><b>{trend['trend']}</b></div>
</div>
{_json_pre(risk)}
<h2>Track {html.escape(port_name)} programmatically</h2>
<div class="snippet-card"><div class="card-header"><span>Python SDK</span></div><pre><code>pip install --upgrade aetherx-oracle

from aetherx import OracleClient

client = OracleClient(api_key="YOUR_RAPIDAPI_KEY")
risk = client.get_port_risk("{port_id}")
print(risk.congestion_score, risk.eta_delay_days)</code></pre></div>
<p>Add the 24/48/72h trend with <code>client.get_port_trend("{port_id}")</code>, or monitor several ports at once with <code>client.get_ports_risk(["{port_id}", "CNSHA"])</code>. AI agents can consume the same data via the <a href="/mcp-page">Aether Grid MCP server</a>.</p>
<a class="cta" href="{PRODUCTION_URL}/m2m-keys">Get a free trial key (REST)</a>
"""
    return _page(
        f"{port_name} Port Congestion — Reference Risk, ETA & Demurrage",
        f"{port_name} ({port_id}) port congestion reference data: congestion score {risk['congestion_score']:.2f}, ETA delay {risk['eta_delay_days']:.1f} days, {risk['waiting_vessels']} waiting vessels and daily demurrage ${risk['estimated_daily_demurrage_usd']:,} via REST, Python SDK or MCP (static seed).",
        f"{port_name} Port Congestion",
        f"Reference congestion, ETA delay, waiting vessels and demurrage for {port_name} ({port_id}), {country}.",
        body,
        f"/port-congestion-{slug}",
    )


def robots_txt_content() -> str:
    return (
        "User-agent: *\n"
        "Allow: /\n\n"
        f"Sitemap: {PRODUCTION_URL}/sitemap.xml\n"
    )


def m2m_keys_page_html() -> str:
    body = f"""
    <div class="header">
      <div class="badge">M2M PRODUCT RUNTIME · ENTERPRISE ACCESS</div>
      <h1>GP5 Maritime — Chaves de Acesso M2M & Decision Tools</h1>
      <p class="subtitle">
        Obtenha uma credencial autenticada de 30 dias para habilitar o conjunto completo de ferramentas de suporte à decisão (Demurrage Risk, Cargo Routing e ChangePackets) no seu servidor MCP, agentes LLM ou algoritmos de trading.
      </p>
    </div>

    <div class="grid grid-2" style="margin-bottom:2rem;">
      <div class="card">
        <h3><span class="status-dot"></span> Modo Legado / Gratuito (Observation)</h3>
        <p style="color:#94a3b8; margin: 0.5rem 0 1rem;">Acesso público de observação sem credencial.</p>
        <ul style="color:#cbd5e1; font-size:0.9rem; line-height:1.6; padding-left:1.2rem;">
          <li>Fila multimodal combinada de navios + vagões Rumo</li>
          <li>Ferramentas: <code>get_port_state</code>, <code>get_physical_events</code></li>
          <li>Limites padrão com rastreio de telemetria</li>
          <li>Decision Tools retornam 403 Forbidden</li>
        </ul>
      </div>

      <div class="card" style="border-color:#38bdf8; background: rgba(56, 189, 248, 0.05);">
        <h3 style="color:#38bdf8;"><span class="status-dot green"></span> Modo Autenticado M2M (Decision Layer)</h3>
        <p style="color:#94a3b8; margin: 0.5rem 0 1rem;">Credencial M2M completa para Tradings e Operadores.</p>
        <ul style="color:#cbd5e1; font-size:0.9rem; line-height:1.6; padding-left:1.2rem;">
          <li>Tudo do Modo Observação + Suporte à Decisão em USD</li>
          <li>Ferramentas: <code>evaluate_charter_risk</code>, <code>evaluate_routing_alternatives</code></li>
          <li>Cálculo de sobrestadia (Demurrage) sob premissas parametrizáveis</li>
          <li>Uso estendido e prioridade de execução</li>
        </ul>
      </div>
    </div>

    
    <div class="card" style="max-width:650px; margin: 0 auto 3rem; padding: 2rem; border-color:#38bdf8; background: rgba(56, 189, 248, 0.05);">
      <h2 style="font-size:1.4rem; margin-bottom:0.5rem; color:#38bdf8;">Acesso Pago via RapidAPI</h2>
      <p style="color:#94a3b8; font-size:0.9rem; margin-bottom:1rem;">Pagamento, assinatura e uso medido são operados pelo marketplace <strong>RapidAPI</strong> — merchant of record da API. Assine lá e suas chamadas REST às Decision Tools são autenticadas pelo proxy (<code>X-RapidAPI-Proxy-Secret</code>) e cobradas pelo seu plano.</p>
      <ul style="color:#cbd5e1; font-size:0.9rem; line-height:1.7; padding-left:1.1rem; margin-bottom:1.5rem;">
        <li>Planos em escada (free / metered / PRO) geridos pela RapidAPI</li>
        <li>Sem chaves manuais: o proxy do marketplace autentica suas requisições</li>
        <li>REST <code>/v1/port-risk</code>, <code>/v1/gp5/*</code> contadas por plano</li>
      </ul>
      <a href="https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle" target="_blank" rel="noopener" style="display:inline-block; padding:0.85rem 2rem; background:#38bdf8; color:#082f49; text-decoration:none; font-weight:bold; font-size:1rem; border-radius:6px;">
        Assinar na RapidAPI →
      </a>
      <p style="color:#64748b; font-size:0.85rem; margin-top:1rem;">Migração futura: assinatura direta via Stripe (em verificação da conta). Quando ativada, o checkout nos emite chave <code>gp5_enterprise_*</code> aceita na REST e no MCP.</p>
    </div>

    <div class="card" style="max-width:650px; margin: 0 auto 3rem; padding: 2rem;">
      <h2 style="font-size:1.4rem; margin-bottom:1rem; color:#f8fafc;">Solicitar Chave M2M (30 Dias Grátis)</h2>
      <p style="color:#94a3b8; font-size:0.9rem; margin-bottom:1.5rem;">Preencha os dados abaixo para gerar instantaneamente a sua credencial M2M para teste empresarial.</p>
      
      <form id="keyForm" onsubmit="generateKey(event)">
        <div style="margin-bottom:1rem;">
          <label style="display:block; color:#cbd5e1; font-size:0.85rem; margin-bottom:0.3rem;">Seu Nome / Responsável Técnico *</label>
          <input type="text" id="name" required placeholder="Ex: Rodrigo Silva" style="width:100%; padding:0.75rem; background:#0f172a; border:1px solid #334155; color:#fff; border-radius:6px;">
        </div>
        <div style="margin-bottom:1rem;">
          <label style="display:block; color:#cbd5e1; font-size:0.85rem; margin-bottom:0.3rem;">E-mail Corporativo *</label>
          <input type="email" id="email" required placeholder="rodrigo@trading.com.br" style="width:100%; padding:0.75rem; background:#0f172a; border:1px solid #334155; color:#fff; border-radius:6px;">
        </div>
        <div style="margin-bottom:1.5rem;">
          <label style="display:block; color:#cbd5e1; font-size:0.85rem; margin-bottom:0.3rem;">Empresa / Mesa de Operação *</label>
          <input type="text" id="organization" required placeholder="Ex: Caramuru Commodities / Trading Desk" style="width:100%; padding:0.75rem; background:#0f172a; border:1px solid #334155; color:#fff; border-radius:6px;">
        </div>

        <button type="submit" style="width:100%; padding:0.85rem; background:#0284c7; color:#fff; border:none; font-weight:600; font-size:1rem; border-radius:6px; cursor:pointer;">
          Gerar Minha Chave M2M Agora →
        </button>
      </form>

      <div id="keyResult" style="display:none; margin-top:1.5rem; padding:1.2rem; background:#022c22; border:1px solid #059669; border-radius:6px;">
        <h4 style="color:#34d399; margin:0 0 0.5rem;">Sua Chave M2M foi Gerada!</h4>
        <p style="color:#cbd5e1; font-size:0.85rem; margin-bottom:0.8rem;">Adicione esta chave ao seu cabeçalho HTTP <code>Authorization: Bearer &lt;SUA_CHAVE&gt;</code> para utilizar as Decision Tools.</p>
        <pre><code id="generatedKey" style="color:#6ee7b7; font-size:1.1rem; font-weight:bold;"></code></pre>
      </div>
    </div>

    <script>
    async function generateKey(e) {{
      e.preventDefault();
      const name = document.getElementById('name').value;
      const email = document.getElementById('email').value;
      const org = document.getElementById('organization').value;

      try {{
        const resp = await fetch('/v1/m2m/request-key', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{name: name, email: email, organization: org}})
        }});
        const data = await resp.json();
        if (data.api_key) {{
          document.getElementById('generatedKey').innerText = data.api_key;
          document.getElementById('keyResult').style.display = 'block';
        }}
      }} catch (err) {{
        alert('Erro ao gerar chave: ' + err);
      }}
    }}
    </script>
    """
    return _page(
        "GP5 M2M — Chaves de Acesso & Decision Tools",
        "Obtenha credencial M2M autenticada para o GP5 Maritime Product Runtime.",
        "GP5 M2M — Chaves de Acesso & Decision Tools",
        "Obtenha uma credencial de 30 dias para habilitar Decision Tools (Demurrage, Routing, Corridors) no seu agente MCP ou trading desk.",
        body,
        "/m2m-keys"
    )


def demo_page_html() -> str:
    body = f"""
    <div style="background: linear-gradient(135deg, #0d1117 0%, #161b22 100%); border: 1px solid #30363d; border-radius: 12px; padding: 1.8rem; margin-bottom: 2rem;">
      <span class="pill pill-green">Simulador Interativo M2M</span>
      <span class="pill pill-blue">Zero-Install Trial</span>
      <h2 style="margin-top:0.6rem; color:#f0f6fc; font-size:1.4rem;">GP5 Maritime Decision Simulator</h2>
      <p style="color:#8b949e; font-size:0.95rem; margin-bottom:1.5rem;">
        Teste as ferramentas de decisão em tempo real (Demurrage Exposure, Total Cycle Days e Risco de Sobrestadia) diretamente no seu navegador.
      </p>

      <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 1.2rem; margin-bottom: 1.5rem;">
        <div>
          <label style="display:block; color:#8b949e; font-size:0.8rem; font-weight:600; margin-bottom:0.4rem;">Porto de Origem</label>
          <select id="simOrigin" onchange="runSim()" style="width:100%; padding:0.6rem; background:#0d1117; border:1px solid #30363d; color:#e6edf3; border-radius:6px;">
            <option value="BRSSZ" selected>Santos (BRSSZ) — Brasil</option>
            <option value="BRPNG">Paranaguá (BRPNG) — Brasil</option>
            <option value="BRMAO">Itaqui (BRMAO) — Brasil</option>
            <option value="ARROS">Rosario (ARROS) — Argentina</option>
            <option value="USMSY">Chicago / New Orleans (USMSY) — EUA</option>
          </select>
        </div>

        <div>
          <label style="display:block; color:#8b949e; font-size:0.8rem; font-weight:600; margin-bottom:0.4rem;">Porto de Destino</label>
          <select id="simDest" onchange="runSim()" style="width:100%; padding:0.6rem; background:#0d1117; border:1px solid #30363d; color:#e6edf3; border-radius:6px;">
            <option value="CNTAO" selected>Qingdao (CNTAO) — China</option>
            <option value="CNSHA">Shanghai (CNSHA) — China</option>
            <option value="NLRTM">Rotterdam (NLRTM) — Holanda</option>
            <option value="DEHAM">Hamburg (DEHAM) — Alemanha</option>
          </select>
        </div>

        <div>
          <label style="display:block; color:#8b949e; font-size:0.8rem; font-weight:600; margin-bottom:0.4rem;">Tipo / Capacidade do Navio (DWT)</label>
          <select id="simDwt" onchange="runSim()" style="width:100%; padding:0.6rem; background:#0d1117; border:1px solid #30363d; color:#e6edf3; border-radius:6px;">
            <option value="35000">Handysize (35,000 t)</option>
            <option value="55000">Supramax (55,000 t)</option>
            <option value="60000" selected>Panamax Standard (60,000 t)</option>
            <option value="82000">Kamsarmax (82,000 t)</option>
            <option value="180000">Capesize (180,000 t)</option>
          </select>
        </div>

        <div>
          <label style="display:block; color:#8b949e; font-size:0.8rem; font-weight:600; margin-bottom:0.4rem;">Cálculo de Prancha / Laytime Permitido</label>
          <select id="simLaytime" onchange="runSim()" style="width:100%; padding:0.6rem; background:#0d1117; border:1px solid #30363d; color:#e6edf3; border-radius:6px;">
            <option value="2.0" selected>2 dias (Prancha Rápida)</option>
            <option value="3.0">3 dias (Prancha Padrão)</option>
            <option value="5.0">5 dias (Prancha Conservadora)</option>
          </select>
        </div>

        <div>
          <label style="display:block; color:#8b949e; font-size:0.8rem; font-weight:600; margin-bottom:0.4rem;">Taxa de Sobrestadia (Demurrage Rate USD/Dia)</label>
          <input type="number" id="simRate" value="32000" step="1000" onchange="runSim()" style="width:100%; padding:0.6rem; background:#0d1117; border:1px solid #30363d; color:#e6edf3; border-radius:6px;">
        </div>

        <div>
          <label style="display:block; color:#8b949e; font-size:0.8rem; font-weight:600; margin-bottom:0.4rem;">Commodity</label>
          <input type="text" id="simCommodity" value="SOJA" onchange="runSim()" style="width:100%; padding:0.6rem; background:#0d1117; border:1px solid #30363d; color:#e6edf3; border-radius:6px;">
        </div>
      </div>

      <div style="background:#090d12; border:1px solid #21262d; border-radius:8px; padding:1.2rem; margin-bottom:1.5rem;">
        <h4 style="color:#58a6ff; font-size:0.9rem; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:0.8rem;">Resultado da Avaliação do Corredor & Sobrestadia</h4>
        <div class="metrics">
          <div class="metric"><span>Espera na Origem</span><b id="resOriginWait">-- dias</b></div>
          <div class="metric"><span>Dias de Navegação</span><b id="resTransit">-- dias</b></div>
          <div class="metric"><span>Ciclo Total Corredor</span><b id="resTotalCycle">-- dias</b></div>
          <div class="metric"><span>Exposição Demurrage</span><b id="resDemurrageUsd" style="color:#f85149;">$0</b></div>
        </div>
        <div class="metrics" style="margin-top:0.6rem;">
          <div class="metric"><span>Custo CFR Demurrage/ton</span><b id="resCostPerTon">$0.00 / t</b></div>
          <div class="metric"><span>Port Congestion Index (PCI)</span><b id="resPciScore" style="color:#e6edf3;">-- / 100</b></div>
          <div class="metric"><span>SC Early Warning (SCDEW)</span><b id="resScdewScore" style="color:#e6edf3;">-- / 100</b></div>
          <div class="metric"><span>Nível de Risco</span><b id="resRiskBadge" style="color:#3fb950;">BAIXO</b></div>
        </div>
        <div class="metrics" style="margin-top:0.6rem;">
          <div class="metric"><span>Status da Carga</span><b>UNMEASURED_DWT_CAPACITY_ONLY</b></div>
          <div class="metric"><span>Proveniência Telemetria</span><b>live:appa+santos+lachmann</b></div>
        </div>
      </div>

      <div style="display:flex; gap:10px; flex-wrap:wrap;">
        <a class="cta" href="/m2m-keys" style="margin:0;">Obter Chave M2M para seu Agente LLM →</a>
        <a href="/aetherx-mcp.json" download="aetherx-mcp.json" style="display:inline-block; background:#21262d; border:1px solid #30363d; color:#c9d1d9; font-weight:600; font-size:0.9rem; padding:0.65rem 1.3rem; border-radius:6px;">Baixar MCP Config (1-Click)</a>
      </div>
    </div>

    <h2>Código de Exemplo no seu Agente LLM / Python</h2>
    <div class="snippet-card"><div class="card-header"><span>Python M2M Request (evaluate_corridor_risk & get_pci_index)</span></div><pre><code>import requests

headers = {{"Authorization": "Bearer YOUR_M2M_API_KEY"}}
payload = {{
    "origin_port": "BRPNG",
    "destination_port": "CNTAO",
    "commodity": "SOJA",
    "vessel_capacity_tons": 60000
}}

# Endpoint REST de Corredor Global GP5
res = requests.post("https://aetherx.aether-grid.io/v1/gp5/evaluate-corridor", json=payload, headers=headers)
print("Corridor Risk:", res.json())

# Endpoint REST de Port Congestion Index (PCI)
pci_res = requests.get("https://aetherx.aether-grid.io/v1/gp5/pci?port_id=BRPNG", headers=headers)
print("PCI Score:", pci_res.json())</code></pre></div>

    <script>
    const TRANSIT_MATRIX = {{
      "BRPNG_CNTAO": 32, "BRPNG_CNSHA": 31, "BRPNG_NLRTM": 16, "BRPNG_DEHAM": 17,
      "BRSSZ_CNTAO": 31, "BRSSZ_CNSHA": 30, "BRSSZ_NLRTM": 15, "BRSSZ_DEHAM": 16,
      "BRMAO_CNTAO": 34, "BRMAO_CNSHA": 33, "BRMAO_NLRTM": 14, "BRMAO_DEHAM": 15,
      "ARROS_CNTAO": 35, "ARROS_CNSHA": 34, "ARROS_NLRTM": 19, "ARROS_DEHAM": 20,
      "USMSY_CNTAO": 29, "USMSY_CNSHA": 28, "USMSY_NLRTM": 12, "USMSY_DEHAM": 13
    }};

    const PORT_WAITS = {{
      "BRSSZ": 4.2, "BRPNG": 3.8, "BRMAO": 2.5, "ARROS": 5.1, "USMSY": 2.0
    }};

    function runSim() {{
      const origin = document.getElementById('simOrigin').value;
      const dest = document.getElementById('simDest').value;
      const dwt = parseFloat(document.getElementById('simDwt').value) || 60000;
      const laytime = parseFloat(document.getElementById('simLaytime').value) || 2.0;
      const rate = parseFloat(document.getElementById('simRate').value) || 32000;

      const originWait = PORT_WAITS[origin] || 3.0;
      const key = origin + '_' + dest;
      const transit = TRANSIT_MATRIX[key] || 30;
      const destWait = 3.0;
      const totalCycle = (originWait + transit + destWait).toFixed(1);

      const excessDays = Math.max(0, originWait - laytime);
      const demurrageUsd = Math.round(excessDays * rate);
      const costPerTon = (demurrageUsd / dwt).toFixed(2);

      const pciScore = Math.min(100, Math.round((originWait / 5.0) * 80 + 15));
      const scdewScore = Math.min(100, Math.round(pciScore * 0.7 + (transit > 25 ? 20 : 10)));

      document.getElementById('resOriginWait').innerText = originWait.toFixed(1) + ' dias';
      document.getElementById('resTransit').innerText = transit + ' dias';
      document.getElementById('resTotalCycle').innerText = totalCycle + ' dias';
      document.getElementById('resDemurrageUsd').innerText = '$' + demurrageUsd.toLocaleString();
      document.getElementById('resCostPerTon').innerText = '$' + costPerTon + ' / t';
      document.getElementById('resPciScore').innerText = pciScore + ' / 100';
      document.getElementById('resScdewScore').innerText = scdewScore + ' / 100';

      const badge = document.getElementById('resRiskBadge');
      if (demurrageUsd > 60000) {{
        badge.innerText = 'ALTO / CRÍTICO';
        badge.style.color = '#f85149';
      }} else if (demurrageUsd > 20000) {{
        badge.innerText = 'MODERADO';
        badge.style.color = '#d29922';
      }} else {{
        badge.innerText = 'BAIXO';
        badge.style.color = '#3fb950';
      }}
    }}
    runSim();
    </script>
    """
    return _page(
        "GP5 Maritime — Simulador Interativo de Risco & Sobrestadia",
        "Simulador interativo de risco de afretamento, tempo de ciclo de viagem e custos de sobrestadia (Demurrage) para o comércio global.",
        "GP5 Maritime — Decision Simulator",
        "Avalie corredores de comércio, tempo de espera na origem/destino e risco financeiro de afretamento em tempo real.",
        body,
        "/demo"
    )


PAGES = [
    ("/mcp-page", mcp_page_html, "Aether Grid MCP — Port Congestion Server for AI Agents"),
    ("/m2m-keys", m2m_keys_page_html, "GP5 M2M — Chaves de Acesso & Decision Tools"),
    ("/demo", demo_page_html, "GP5 Maritime — Simulador Interativo de Risco & Sobrestadia"),
    ("/port-congestion-api", port_congestion_api_page, "Port Congestion API — Port Risk, ETA Delay & Demurrage"),
    ("/santos-port-congestion-api", santos_port_congestion_api_page, "Santos Port Congestion API — Reference Risk & ETA"),
    ("/port-congestion-python", port_congestion_python_page, "Port Congestion API with Python — Quick Start SDK"),
]


def _content_lastmod() -> str:
    """Data da última mudança de conteúdo (mtime do VERSION, que muda a cada
    deploy). Evita lastmod falso — data fixa ou date.today() penalizam SEO."""
    from datetime import datetime, timezone
    try:
        version_path = Path(__file__).resolve().parent.parent.parent / "VERSION"
        ts = version_path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except OSError:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def sitemap_xml() -> str:
    lastmod = _content_lastmod()
    base_urls = ["/", "/mcp-page", "/m2m-keys", "/demo", "/port-congestion-api", "/santos-port-congestion-api", "/port-congestion-python"]
    port_urls = [f"/port-congestion-{m['slug']}" for m in PORT_METAS]
    urls = base_urls + port_urls + SEO_URLS
    items = "\n".join(f"  <url><loc>{PRODUCTION_URL}{u}</loc><lastmod>{lastmod}</lastmod></url>" for u in urls)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{items}
</urlset>
"""


def fiscal_demo_page(intended_port: str = "BRSSZ", commodity: str = "FERTILIZANTES", cargo_value: float = 10000000.0, inland_uf: str = "MT", cargo_tons: float = 60000.0) -> str:
    try:
        res = evaluate_fiscal_routing(intended_port, commodity, cargo_value, inland_uf, cargo_tons)
        options = res.options
        summary = res.recommendation_summary
    except Exception as e:
        options = []
        summary = f"Erro ao processar: {str(e)}"

    rows = ""
    for opt in options:
        color = "#10b981" if opt.is_recommended else "#ef4444" if opt.port_id == intended_port else "#6b7280"
        badge = "RECOMENDADO" if opt.is_recommended else "ROTA PRETENDIDA" if opt.port_id == intended_port else "ALTERNATIVA"
        
        rows += f"""
        <tr style="border-bottom: 1px solid #374151;">
            <td style="padding: 1rem; color: {color}; font-weight: bold;">{opt.port_name} ({opt.state_code})</td>
            <td style="padding: 1rem;">{opt.delay_days} dias</td>
            <td style="padding: 1rem;">US$ {opt.demurrage_cost_usd:,.2f}</td>
            <td style="padding: 1rem;">{opt.icms_rate_pct}%</td>
            <td style="padding: 1rem;">US$ {opt.icms_cost_usd:,.2f}</td>
            <td style="padding: 1rem;">US$ {opt.inland_freight_cost_usd:,.2f}</td>
            <td style="padding: 1rem; font-weight: bold; color: {color};">US$ {opt.total_cost_usd:,.2f}</td>
            <td style="padding: 1rem; font-size: 0.8rem;"><span style="background: {color}; color: #000; padding: 2px 6px; border-radius: 4px;">{badge}</span></td>
        </tr>
        """

    body = f"""

    <div style="max-width: 1200px; margin: 0 auto; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <h2 style="color: #60a5fa; text-align: center; font-size: 2.2rem; margin-bottom: 10px;">Aether Grid GP5: Simulador de Arbitragem Logística</h2>
        <p style="color: #9ca3af; font-size: 1.1rem; line-height: 1.6; text-align: center; max-width: 800px; margin: 0 auto 30px auto;">
            Simule ao vivo o custo real de roteamento. Cruzamos o <strong>Congestionamento Portuário (Demurrage)</strong>, 
            a <strong>Guerra Fiscal (ICMS)</strong> e o <strong>Frete Rodoviário</strong> para encontrar a rota mais lucrativa.
        </p>
        
        <div style="background: #1f2937; padding: 25px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
            <form action="/fiscal-demo" method="GET" style="display: flex; flex-wrap: wrap; gap: 15px; align-items: flex-end;">
                <div style="display: flex; flex-direction: column; flex: 1; min-width: 150px;">
                    <label style="color: #9ca3af; font-size: 0.9rem; margin-bottom: 5px; font-weight: bold;">Produto</label>
                    <input type="text" name="commodity" value="{commodity}" style="padding: 12px; background: #111827; border: 1px solid #4b5563; color: white; border-radius: 6px; font-size: 1rem;">
                </div>
                <div style="display: flex; flex-direction: column; flex: 1; min-width: 150px;">
                    <label style="color: #9ca3af; font-size: 0.9rem; margin-bottom: 5px; font-weight: bold;">Porto Desejado</label>
                    <input type="text" name="intended_port" value="{intended_port}" style="padding: 12px; background: #111827; border: 1px solid #4b5563; color: white; border-radius: 6px; font-size: 1rem;">
                </div>
                <div style="display: flex; flex-direction: column; flex: 1; min-width: 150px;">
                    <label style="color: #9ca3af; font-size: 0.9rem; margin-bottom: 5px; font-weight: bold;">Estado (Origem/Destino)</label>
                    <input type="text" name="inland_uf" value="{inland_uf}" style="padding: 12px; background: #111827; border: 1px solid #4b5563; color: white; border-radius: 6px; font-size: 1rem;">
                </div>
                <div style="display: flex; flex-direction: column; flex: 1; min-width: 150px;">
                    <label style="color: #9ca3af; font-size: 0.9rem; margin-bottom: 5px; font-weight: bold;">Volume (Tons)</label>
                    <input type="number" name="cargo_tons" value="{cargo_tons}" style="padding: 12px; background: #111827; border: 1px solid #4b5563; color: white; border-radius: 6px; font-size: 1rem;">
                </div>
                <div style="display: flex; flex-direction: column; flex: 1; min-width: 150px;">
                    <label style="color: #9ca3af; font-size: 0.9rem; margin-bottom: 5px; font-weight: bold;">Valor (US$)</label>
                    <input type="number" name="cargo_value" value="{cargo_value}" style="padding: 12px; background: #111827; border: 1px solid #4b5563; color: white; border-radius: 6px; font-size: 1rem;">
                </div>
                <div style="flex: 1; min-width: 150px;">
                    <button type="submit" style="width: 100%; padding: 12px 20px; background: #3b82f6; color: white; border: none; border-radius: 6px; font-weight: bold; font-size: 1rem; cursor: pointer;">⚡ Simular Rota</button>
                </div>
            </form>
        </div>

        <div style="background: #111827; padding: 25px; border-radius: 12px; border: 1px solid #3b82f6; margin-bottom: 30px; border-left: 5px solid #3b82f6;">
            <h3 style="color: #60a5fa; margin-top: 0; font-size: 1.3rem;">Veredito da Aether Grid (IA)</h3>
            <p style="color: #e5e7eb; font-size: 1.2rem; font-weight: 500; line-height: 1.5; margin-bottom: 0;">{summary}</p>
        </div>

        <p style="color: #6b7280; font-size: 0.8rem; margin-bottom: 30px;">Fretes rodoviários de grãos em R$/t convertidos em USD (câmbio US$ 1,00 = R$ 5,22, 28/09/2026) — fonte: CONAB Boletim Logístico 07/2026 e Sifreca/ESALQ-USP. Corredores sem tarifa publicada são estimativas calibradas e marcadas.</p>

        <div style="overflow-x: auto; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);">
            <table style="width: 100%; text-align: left; border-collapse: collapse; background: #1f2937; border-radius: 12px; overflow: hidden; min-width: 800px;">
                <thead>
                    <tr style="background: #111827; border-bottom: 2px solid #374151; color: #9ca3af; text-transform: uppercase; font-size: 0.85rem;">
                        <th style="padding: 1.2rem;">Porto</th>
                        <th style="padding: 1.2rem;">Fila (Dias)</th>
                        <th style="padding: 1.2rem;">Demurrage</th>
                        <th style="padding: 1.2rem;">ICMS</th>
                        <th style="padding: 1.2rem;">Frete Inland</th>
                        <th style="padding: 1.2rem; color: white;">Custo Total (TCO)</th>
                        <th style="padding: 1.2rem;">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        
        <div style="margin-top: 60px; text-align: center; border-top: 1px solid #374151; padding-top: 40px; padding-bottom: 40px;">
            <h3 style="color: white; font-size: 1.8rem; margin-bottom: 15px;">Quer plugar essa inteligência no ERP da sua empresa?</h3>
            <p style="color: #9ca3af; font-size: 1.1rem; margin-bottom: 30px;">O Motor GP5 toma essas decisões sozinho (M2M) para todos os navios que você opera.</p>
            <div style="display: flex; justify-content: center; gap: 15px; flex-wrap: wrap;">
                <a href="https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle" target="_blank" rel="noopener" style="display: inline-block; padding: 15px 35px; background: #10b981; color: #000; text-decoration: none; font-weight: bold; border-radius: 8px; font-size: 1.1rem;">Adquirir Acesso Pago (RapidAPI) →</a>
            </div>
        </div>
    </div>
    """
    return _page(
        title="Fiscal Arbitrage | Aether Grid",
        meta_description="O motor de roteamento B2B logístico-tributário definitivo.",
        h1="Aether Grid Oracle: Fiscal Routing",
        lede="Descubra para onde enviar seu navio para pagar menos impostos e zero demurrage.",
        body=body,
        canonical_suffix="/fiscal-demo"
    )



import itertools

SEO_COMMODITIES = ["soja", "milho", "fertilizantes"]
SEO_UFS = ["mt", "go", "ms", "pr", "sp"]
# Map slugs back to IDs
PORT_SLUG_ID = {
    "santos": "BRSSZ",
    "paranagua": "BRPNG",
    "itaqui": "BRMAO",
    "rio-de-janeiro": "BRRIO",
    "rio-grande": "BRRGD"
}
PORT_SLUGS = list(PORT_SLUG_ID.keys())

# Generate predictable URLs for the sitemap
SEO_URLS = []
for comm in SEO_COMMODITIES:
    for uf in SEO_UFS:
        # Generate some logical pairs (not all against all to avoid spam, just realistic ones)
        pairs = [("santos", "paranagua"), ("paranagua", "santos"), ("itaqui", "santos"), ("rio-grande", "paranagua"), ("rio-de-janeiro", "santos")]
        for p1, p2 in pairs:
            SEO_URLS.append(f"/arbitragem-logistica/{comm}-{p1}-vs-{p2}-{uf}")

def arbitrage_seo_page(slug: str) -> str:
    # Slug format: {commodity}-{port1}-vs-{port2}-{uf}
    parts = slug.split("-vs-")
    if len(parts) != 2:
        return "Not found"
    
    left = parts[0].split("-")
    comm = left[0]
    p1 = "-".join(left[1:])
    
    right = parts[1].split("-")
    uf = right[-1]
    p2 = "-".join(right[:-1])
    
    id1 = PORT_SLUG_ID.get(p1, "BRSSZ")
    id2 = PORT_SLUG_ID.get(p2, "BRPNG")
    
    try:
        from src.products.gp5.fiscal import evaluate_fiscal_routing
        res = evaluate_fiscal_routing(intended_port_id=id1, commodity=comm.upper(), cargo_value_usd=10000000.0, inland_uf=uf.upper(), cargo_tons=60000.0)
        # Find the specific ports
        opt1 = next((o for o in res.options if o.port_id == id1), None)
        opt2 = next((o for o in res.options if o.port_id == id2), None)
        if not opt1 or not opt2:
            raise ValueError("Ports not found in simulation")
    except Exception as e:
        return f"Error: {str(e)}"
    
    title = f"Arbitragem Logística de {comm.title()}: {opt1.port_name} vs {opt2.port_name} ({uf.upper()})"
    desc = f"Descubra qual a rota mais barata para importar ou exportar {comm.title()} no estado {uf.upper()}. Comparação de Frete Terrestre, Demurrage (Fila do Porto) e ICMS."
    
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | Aether Grid Oracle</title>
<meta name="description" content="{desc}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{PRODUCTION_URL}/arbitragem-logistica/{slug}" />
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0a0e14; color: #e6edf3; padding: 2rem; line-height: 1.6; }}
.container {{ max-width: 800px; margin: 0 auto; }}
h1 {{ color: #58a6ff; font-size: 2rem; border-bottom: 1px solid #30363d; padding-bottom: 0.5rem; }}
h2 {{ color: #8b949e; margin-top: 2rem; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.5rem; margin: 1rem 0; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }}
.highlight {{ color: #3fb950; font-weight: bold; font-size: 1.2rem; display: block; margin: 1rem 0; }}
.data-row {{ display: flex; justify-content: space-between; border-bottom: 1px dashed #30363d; padding: 0.5rem 0; }}
.vs {{ text-align: center; font-style: italic; color: #6e7681; margin: 1rem 0; font-size: 1.2rem; }}
.cta {{ text-align: center; margin-top: 3rem; padding: 2rem; background: #0d1117; border-radius: 8px; border: 1px solid #58a6ff; }}
.cta a {{ color: #0a0e14; background: #58a6ff; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: bold; }}
.disclaimer {{ font-size: 0.8rem; color: #6e7681; margin-top: 2rem; border-top: 1px solid #30363d; padding-top: 1rem; }}
</style>
</head>
<body>
<div class="container">
    <h1>{title}</h1>
    <p>{desc} Dados atualizados em tempo real via telemetria portuária e tabelas estaduais (DIFAL).</p>
    
    <span class="highlight">Veredito da Inteligência Artificial: {res.recommendation_summary}</span>

    <div class="card">
        <h2>Opção A: Rota via {opt1.port_name}</h2>
        <div class="data-row"><span>Status da Fila (Delay)</span><span>{opt1.delay_days} dias ({opt1.data_source})</span></div>
        <div class="data-row"><span>Custo de Demurrage</span><span>US$ {opt1.demurrage_cost_usd:,.2f}</span></div>
        <div class="data-row"><span>Frete Terrestre até {uf.upper()}</span><span>US$ {opt1.inland_freight_cost_usd:,.2f}</span></div>
        <div class="data-row"><span>ICMS (Regra de Destino)</span><span>US$ {opt1.icms_cost_usd:,.2f} ({opt1.icms_rate_pct}%)</span></div>
        <div class="data-row" style="font-weight:bold; color:#58a6ff;"><span>Custo Total Estimado (TCO)</span><span>US$ {opt1.total_cost_usd:,.2f}</span></div>
    </div>
    
    <div class="vs">versus</div>

    <div class="card">
        <h2>Opção B: Rota via {opt2.port_name}</h2>
        <div class="data-row"><span>Status da Fila (Delay)</span><span>{opt2.delay_days} dias ({opt2.data_source})</span></div>
        <div class="data-row"><span>Custo de Demurrage</span><span>US$ {opt2.demurrage_cost_usd:,.2f}</span></div>
        <div class="data-row"><span>Frete Terrestre até {uf.upper()}</span><span>US$ {opt2.inland_freight_cost_usd:,.2f}</span></div>
        <div class="data-row"><span>ICMS (Regra de Destino)</span><span>US$ {opt2.icms_cost_usd:,.2f} ({opt2.icms_rate_pct}%)</span></div>
        <div class="data-row" style="font-weight:bold; color:#58a6ff;"><span>Custo Total Estimado (TCO)</span><span>US$ {opt2.total_cost_usd:,.2f}</span></div>
    </div>

    <h2>Metodologia (Aether Grid Oracle)</h2>
    <p>O cálculo de TCO (Custo Total de Operação) acima foi gerado autonomamente cruzando matrizes de frete rodoviário e ferroviário, isenções de Convênio ICMS 100/97 aplicadas ao estado de destino, e telemetria de congestionamento de navios ao vivo (live line-ups).</p>
    
    <div class="cta">
        <h3>Quer plugar essa inteligência na sua operação corporativa?</h3>
        <p>Acesse o simulador oficial ou integre seus agentes autônomos via MCP e API REST.</p>
        <br><a href="/fiscal-demo">Testar Simulador Interativo</a>
    </div>

    <div class="disclaimer">
        As informações representam um cenário simulado de 60.000 MT baseado em condições observadas em tempo real. Valores apresentados como referência de mercado. Motor GP5 Aether Grid.
    </div>
</div>
</body>
</html>"""
