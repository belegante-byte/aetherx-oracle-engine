"""Landing content pages: Aether-X MCP demo page, SEO intent pages and sitemap.

All pages reuse the same dark theme as the landing page and render the
oracle signals (calculate_port_risk / calculate_port_trend). Every page
states the data provenance explicitly: Brazilian ports (BRPNG/BRSSZ/BRRIO/BRNIT/BRITG) are fed
by live line-ups; the rest serve a static reference seed.
"""

import html
import json

from src.engine.risk_model import calculate_port_risk, calculate_port_trend

PRODUCTION_URL = "https://aetherx.aether-grid.io"
RAPIDAPI_URL = "https://rapidapi.com/belegante/api/aether-x-port-congestion-oracle"
REGISTRY_URL = "io.github.belegante-byte/aetherx-mcp"
PYPI_SDK = "https://pypi.org/project/aetherx-oracle/"
PYPI_MCP = "https://pypi.org/project/aetherx-mcp/"

REMOTE_CFG = '{"mcpServers": {"aetherx-oracle": {"type": "url", "url": "%s/mcp"}}}' % PRODUCTION_URL
STDIO_CFG = '{"mcpServers": {"aetherx-oracle": {"command": "uvx", "args": ["aetherx-mcp"]}}}'

# 19 portos monitorados, espelhando src/engine/init_prod_db.py. O slug alimenta
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
    {"port_id": "HORMUZ", "slug": "strait-of-hormuz", "port_name": "Strait of Hormuz", "country": "Omã / Irã (Chokepoint)"},
    {"port_id": "MXZLO", "slug": "manzanillo", "port_name": "Manzanillo", "country": "México"},
]

_SLUG_MAP = {m["slug"]: m for m in PORT_METAS}

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
<div class="breadcrumb"><a href="/">Aether-X Port Congestion Oracle</a> /</div>
<h1>{h1}</h1>
<p class="lede muted">{lede}</p>
{body}
<div class="footer">Aether-X Port Congestion Oracle &middot; Free tier $0.00 &middot; <a href="{RAPIDAPI_URL}">RapidAPI</a> &middot; <a href="{PYPI_SDK}">PyPI SDK</a> &middot; <a href="{PYPI_MCP}">MCP server</a> &middot; MCP Registry: {REGISTRY_URL}</div>
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
<p>Get a free key on the <a href="{RAPIDAPI_URL}">RapidAPI listing</a> (Free Developer Tier, $0.00).</p>
<a class="cta" href="{RAPIDAPI_URL}">Get a free API key</a>
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
<a class="cta" href="{RAPIDAPI_URL}">Get a free API key</a>
"""
    return _page(
        "Aether-X MCP — Port Congestion Server for AI Agents",
        "MCP server for live Brazilian port line-ups and reference global port congestion signals. Tools: get_port_risk, get_ports_risk, get_port_trend. Remote endpoint and PyPI install.",
        "Aether-X MCP: Port Congestion for AI Agents",
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
        "Port congestion API, vessel queue intelligence, port delay risk / ETA delay and demurrage exposure for 19 ports (5 Brazilian LIVE, 14 reference seed). Choose between ports, route cargo and assess demurrage risk.",
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
<p>Add the 24/48/72h trend with <code>client.get_port_trend("BRSSZ")</code>, or monitor several Brazilian ports at once with <code>client.get_ports_risk(["BRSSZ", "BRRIO"])</code>. AI agents can consume the same data via the <a href="/mcp-page">Aether-X MCP server</a>.</p>
<a class="cta" href="{RAPIDAPI_URL}">Get a free API key for Santos data</a>
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
    body = f"""<p>You don't need heavy infrastructure to monitor port congestion. With a typed Python SDK you can pull congestion scores, ETA delays and demurrage exposure for 19 ports (5 Brazilian LIVE, 14 reference seed) in a few lines.</p>
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
<a class="cta" href="{RAPIDAPI_URL}">Get a free API key</a>
"""
    return _page(
        "Port Congestion API with Python — Quick Start SDK",
        "Monitor port congestion with Python: install the aetherx-oracle SDK, call Santos, scan a portfolio of ports and add 24/48/72h ETA delay trends.",
        "Port Congestion Monitoring with Python",
        "A 3-minute, typed-Python quick start for congestion scores, ETA delays and demurrage exposure across 19 ports (5 Brazilian LIVE, 14 reference seed).",
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
<p>Add the 24/48/72h trend with <code>client.get_port_trend("{port_id}")</code>, or monitor several ports at once with <code>client.get_ports_risk(["{port_id}", "CNSHA"])</code>. AI agents can consume the same data via the <a href="/mcp-page">Aether-X MCP server</a>.</p>
<a class="cta" href="{RAPIDAPI_URL}">Get a free API key</a>
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
        Obtenha uma credencial autenticada de 7 dias para habilitar o conjunto completo de ferramentas de suporte à decisão (Demurrage Risk, Cargo Routing e ChangePackets) no seu servidor MCP, agentes LLM ou algoritmos de trading.
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

    <div class="card" style="max-width:650px; margin: 0 auto 3rem; padding: 2rem;">
      <h2 style="font-size:1.4rem; margin-bottom:1rem; color:#f8fafc;">Solicitar Chave M2M (7 Dias Grátis)</h2>
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
        "Obtenha uma credencial de 7 dias para habilitar Decision Tools (Demurrage, Routing, Corridors) no seu agente MCP ou trading desk.",
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
          <div class="metric"><span>Proveniência Telemetria</span><b>live:appa+santos+lachmann+portinsight+straittraffic</b></div>
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
    ("/mcp-page", mcp_page_html, "Aether-X MCP — Port Congestion Server for AI Agents"),
    ("/m2m-keys", m2m_keys_page_html, "GP5 M2M — Chaves de Acesso & Decision Tools"),
    ("/demo", demo_page_html, "GP5 Maritime — Simulador Interativo de Risco & Sobrestadia"),
    ("/port-congestion-api", port_congestion_api_page, "Port Congestion API — Port Risk, ETA Delay & Demurrage"),
    ("/santos-port-congestion-api", santos_port_congestion_api_page, "Santos Port Congestion API — Reference Risk & ETA"),
    ("/port-congestion-python", port_congestion_python_page, "Port Congestion API with Python — Quick Start SDK"),
]


def sitemap_xml() -> str:
    lastmod = "2026-09-20"
    base_urls = ["/", "/mcp-page", "/m2m-keys", "/demo", "/port-congestion-api", "/santos-port-congestion-api", "/port-congestion-python"]
    port_urls = [f"/port-congestion-{m['slug']}" for m in PORT_METAS]
    urls = base_urls + port_urls
    items = "\n".join(f"  <url><loc>{PRODUCTION_URL}{u}</loc><lastmod>{lastmod}</lastmod></url>" for u in urls)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{items}
</urlset>
"""