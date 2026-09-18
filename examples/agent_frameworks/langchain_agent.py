"""LangChain agent using Aether-X port congestion as a tool.

Requires: pip install langchain langchain-openai aetherx-oracle
Export:   AETHERX_API_KEY (RapidAPI) and OPENAI_API_KEY for the agent run.
"""

import os

from aetherx import OracleClient


def make_client() -> OracleClient:
    key = os.getenv("AETHERX_API_KEY")
    if not key:
        raise RuntimeError("Export AETHERX_API_KEY (RapidAPI free key).")
    return OracleClient(api_key=key)


def build_tool():
    """LangChain tool — only needs AETHERX_API_KEY, no LLM.

    Import (langchain_core) is deferred on purpose so the file can be read
    without the framework installed.
    """
    from langchain_core.tools import tool

    client = make_client()

    @tool
    def port_congestion_risk(port_id: str) -> str:
        """Get the current port congestion risk, ETA delay and daily
        demurrage exposure for a port (UN/LOCODE, e.g. BRSSZ, CNSHA, NLRTM)."""
        risk = client.get_port_risk(port_id)
        return risk.model_dump_json()

    @tool
    def port_congestion_trend(port_id: str) -> str:
        """Get the 24h/48h/72h congestion projection and trend label for a port."""
        trend = client.get_port_trend(port_id)
        return trend.model_dump_json()

    return [port_congestion_risk, port_congestion_trend]


def run_agent(question: str) -> str:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage
    from langgraph.prebuilt import create_react_agent

    model = ChatOpenAI(model="gpt-4o-mini")
    agent = create_react_agent(model, build_tool())
    result = agent.invoke({"messages": [HumanMessage(content=question)]})
    return result["messages"][-1].content


if __name__ == "__main__":
    # Tool-only (no LLM): print the signal directly.
    for tool in build_tool():
        print(f"-> {tool.name}")
        print(tool.invoke("BRSSZ"))

    # Agent (needs OPENAI_API_KEY).
    # print(run_agent("Compare congestion risk at Santos and Rotterdam."))