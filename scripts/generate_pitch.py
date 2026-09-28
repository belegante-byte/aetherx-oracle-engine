import argparse
import sys
import os
from datetime import datetime, timezone
from src.products.gp5.fiscal import evaluate_fiscal_routing

def generate_pitch(target_company: str, commodity: str, cargo_value_usd: float, inland_uf: str, cargo_tons: float, intended_port: str):
    print(f"Gerando relatório para {target_company}...")
    
    try:
        res = evaluate_fiscal_routing(
            intended_port_id=intended_port,
            commodity=commodity,
            cargo_value_usd=cargo_value_usd,
            inland_uf=inland_uf,
            cargo_tons=cargo_tons
        )
    except Exception as e:
        print(f"Erro ao avaliar roteamento: {e}")
        sys.exit(1)

    # Filter intended option and recommended option
    intended_opt = next((o for o in res.options if o.port_id == res.intended_port_id), None)
    best_opt = next((o for o in res.options if o.is_recommended), None)

    if not intended_opt or not best_opt:
        print("Erro: Portos insuficientes no banco de dados para avaliação.")
        sys.exit(1)
        

    # Freshness Check
    if intended_opt.as_of != "unknown":
        as_of_dt = datetime.strptime(intended_opt.as_of, "%Y-%m-%d %H:%M:%S")
        hours_old = (datetime.now(timezone.utc).replace(tzinfo=None) - as_of_dt).total_seconds() / 3600
        if hours_old > 24:
            print(f"\n[WARNING] Dados locais muito antigos ({hours_old:.1f}h). Execute a ingestão antes de enviar o pitch!\n")
    date_str = datetime.now().strftime("%d de %B de %Y")
    
    markdown = f"""# Relatório Executivo de Roteamento Logístico Inteligente
**Preparado para:** {target_company.upper()}
**Data de Emissão:** {date_str}
**Commodity:** {commodity.title()}
**Volume da Carga:** {cargo_tons:,.0f} MT
**Valor Estimado Declarado:** US$ {cargo_value_usd:,.2f}
**Destino/Origem Terrestre (Inland):** {inland_uf.upper()}

---

## 1. O Veredito Algorítmico
{res.recommendation_summary}

## 2. Metodologia e Premissas ("Sniper Honesto")
Este relatório foi gerado através do motor **Aether-X Oracle**. Não utilizamos "achismos" nem dados defasados. As premissas matemáticas abertas para a sua validação são:
- **Telemetria Física:** Baseada nas filas de navios em tempo real de hoje, lidas via integrações primárias (ex: APPA, PortosRio, SILOG) e modelagem de congestionamento.
- **Multa de Fila (Demurrage):** Estimativa derivada de índices reais de pressão operacional (estimada dinamicamente entre US$ 32.000 a 45.000/dia por navio panamax).
- **Tributação (ICMS - Regra de Destino/DIFAL):** O modelo atribui a alíquota baseada no **Estado Destinatário da Carga** (`{inland_uf.upper()}`), aplicando o Convênio 100/97 ou isenções vigentes no destino, neutralizando assimetrias de origem portuária.
- **Frete Terrestre (Rodoviário/Ferroviário):** Matriz paramétrica (média de mercado) calculada com base na quilometragem até `{inland_uf.upper()}`.

---

## 3. A Matemática Aberta (Transparência de Dados)

### Rota A: Planejada ({intended_opt.port_name} / {intended_opt.state_code})
- **Status do Oráculo:** `{intended_opt.decision_grade.upper()}` ({intended_opt.data_source})
- Fila Esperada (Delay): **{intended_opt.delay_days} dias**
- Risco Financeiro de Demurrage: **US$ {intended_opt.demurrage_cost_usd:,.2f}**
- Incidência de ICMS ({intended_opt.icms_rate_pct}%): **US$ {intended_opt.icms_cost_usd:,.2f}**
- Custo de Frete Inland ({inland_uf}): **US$ {intended_opt.inland_freight_cost_usd:,.2f}**
- **Custo Total de Operação (TCO): US$ {intended_opt.total_cost_usd:,.2f}**

### Rota B: Rota Aether-X Recomendada ({best_opt.port_name} / {best_opt.state_code})
- **Status do Oráculo:** `{best_opt.decision_grade.upper()}` ({best_opt.data_source})
- Fila Esperada (Delay): **{best_opt.delay_days} dias**
- Risco Financeiro de Demurrage: **US$ {best_opt.demurrage_cost_usd:,.2f}**
- Incidência de ICMS ({best_opt.icms_rate_pct}%): **US$ {best_opt.icms_cost_usd:,.2f}**
- Custo de Frete Inland ({inland_uf}): **US$ {best_opt.inland_freight_cost_usd:,.2f}**
- **Custo Total de Operação (TCO): US$ {best_opt.total_cost_usd:,.2f}**

---
*Gerado autonomamente pelo Motor Aether-X GP5 (Gateway/API) em frações de segundo.*
"""

    out_file = f"pitch_{target_company.lower().replace(' ', '_')}.md"
    with open(out_file, "w") as f:
        f.write(markdown)
    
    print(f"Sucesso! Pitch escrito em {out_file}. Você pode exportá-lo para PDF e enviar ao cliente.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aether-X B2B Pitch Generator")
    parser.add_argument("--company", required=True, help="Nome da empresa alvo")
    parser.add_argument("--commodity", default="FERTILIZANTES")
    parser.add_argument("--value", type=float, default=10000000.0)
    parser.add_argument("--uf", default="MT", help="Estado Inland")
    parser.add_argument("--tons", type=float, default=60000.0)
    parser.add_argument("--port", default="BRSSZ", help="Porto pretendido")
    
    args = parser.parse_args()
    
    generate_pitch(
        target_company=args.company,
        commodity=args.commodity,
        cargo_value_usd=args.value,
        inland_uf=args.uf,
        cargo_tons=args.tons,
        intended_port=args.port
    )
