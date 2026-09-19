# aetherx-oracle

SDK Python oficial para a **Aether-X Port Congestion Oracle API** — sinais preditivos de congestão portuária, atraso de ETA e volatilidade de frete para portos globais.

## Instalação

```bash
pip install aetherx-oracle
```

## Uso rápido

```python
from aetherx import OracleClient

client = OracleClient(api_key="SUA_RAPIDAPI_KEY")

risk = client.get_port_risk("BRSSZ")

print(risk.port_name)                 # Santos
print(risk.country)                   # Brasil
print(risk.congestion_score)          # 0.78
print(risk.eta_delay_days)            # 1.6
print(risk.waiting_vessels)           # 12
print(risk.freight_volatility_index)  # 0.42
print(risk.estimated_daily_demurrage_usd)  # 63200 (USD/dia)
print(risk.updated_at)                # 2026-09-17 15:46:53
```

## Tendência 24/48/72h

```python
trend = client.get_port_trend("NLRTM")
print(trend.trend)                 # estavel / acelerando / descongestionando
print(trend.projection["h48"].congestion_score)
print(trend.projection["h72"].estimated_daily_demurrage_usd)
```

## Consulta em lote (uma única chamada)

```python
ports = client.get_ports_risk(["BRSSZ", "CNSHA", "NLRTM", "USLAX"])
for p in ports:
    print(p.port_id, p.congestion_score, p.estimated_daily_demurrage_usd)
```

## Campos retornados (`PortRisk`)

| Campo | Tipo | Descrição |
|---|---|---|
| `port_id` | `str` | UN/LOCODE do porto (ex: `BRSSZ`) |
| `port_name` | `str` | Nome do porto |
| `country` | `str` | País do porto |
| `congestion_score` | `float` | Score de congestão (0.0 a 1.0) |
| `eta_delay_days` | `float` | Atraso estimado de ETA em dias |
| `waiting_vessels` | `int` | Navios aguardando/ancorados |
| `freight_volatility_index` | `float` | Índice de volatilidade de frete |
| `estimated_daily_demurrage_usd` | `int` | Demurrage diária estimada (USD) |
| `updated_at` | `str` | Timestamp da última atualização |

## Configuração avançada

```python
client = OracleClient(
    api_key="SUA_RAPIDAPI_KEY",
    host="aether-x-port-congestion-oracle.p.rapidapi.com",  # default
    timeout=30.0,                                            # segundos
)
```

## Portos suportados

Portos com dados de exemplo: `BRSSZ`, `BRRIO`, `CNSHA`, `CNNGB`, `CNTAO`, `SGSIN`, `NLRTM`, `USLAX`, `USNYC`, `DEHAM`, `MPTNG`, `AEDXB`, `KRPUS`, `GBLGP`, `ZACPT`, `MXZLO`.

Portos não cadastrados retornam uma estimativa global (`country="Global"`).

## Uso assíncrono (async)

Para consultar múltiplos portos em paralelo (ideal para bots e fundos quantitativos). Requer o extra `async`:

```bash
pip install "aetherx-oracle[async]"
```

```python
import asyncio
from aetherx import OracleClient

async def main():
    client = OracleClient(api_key="SUA_RAPIDAPI_KEY")

    # Um porto
    risk = await client.get_port_risk_async("BRSSZ")
    print(risk.congestion_score)

    # Vários portos em paralelo
    risks = await client.get_ports_risk_async(["BRSSZ", "CNSHA", "NLRTM"])
    for r in risks:
        print(r.port_id, r.congestion_score)

    # Tendência async
    trend = await client.get_port_trend_async("BRSSZ")
    print(trend.trend)

asyncio.run(main())
```

## Termos de uso

Os sinais são fornecidos "AS IS", sem garantia e **não constituem aconselhamento de investimento**. Consulte os [Termos de Serviço](https://aetherx.aether-grid.io/terms).

## Licença

O código deste SDK é distribuído sob a licença **MIT** (veja [LICENSE](LICENSE)). O uso da API hospedada está sujeito aos Termos de Serviço.
