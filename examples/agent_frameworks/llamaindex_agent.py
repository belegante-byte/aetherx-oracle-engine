"""LlamaIndex agent using Aether-X port congestion as a FunctionTool.

Requires: pip install llama-index aetherx-oracle
Export:   AETHERX_API_KEY (RapidAPI) and OPENAI_API_KEY for the agent run.
"""

import os

from aetherx import OracleClient


def make_client() -> OracleClient:
    key = os.getenv("AETHERX_API_KEY")
    if not key:
        raise RuntimeError("Export AETHERX_API_KEY (RapidAPI free key).")
    return OracleClient(api_key=key)


def build_tools():
    from llama_index.core.tools import FunctionTool

    client = make_client()

    def get_risk(port_id: str) -> str:
        """Get current port congestion risk, ETA delay and daily demurrage
        for a port (UN/LOCODE, e.g. BRSSZ, CNSHA, NLRTM)."""
        return client.get_port_risk(port_id).model_dump_json()

    def get_trend(port_id: str) -> str:
        """Get the 24h/48h/72h congestion projection and trend label for a port."""
        return client.get_port_trend(port_id).model_dump_json()

    return [
        FunctionTool.from_defaults(
            fn=get_risk,
            name="port_congestion_risk",
            description="Current port congestion risk, ETA delay and demurrage for a UN/LOCODE.",
        ),
        FunctionTool.from_defaults(
            fn=get_trend,
            name="port_congestion_trend",
            description="24h/48h/72h congestion projection and trend label for a UN/LOCODE.",
        ),
    ]


def run_agent(question: str) -> str:
    from llama_index.core.agent import ReActAgent
    from llama_index.llms.openai import OpenAI

    agent = ReActAgent.from_tools(
        build_tools(), llm=OpenAI(model="gpt-4o-mini"), verbose=True
    )
    return str(agent.chat(question))


if __name__ == "__main__":
    # Tool-only (no LLM): invoke a FunctionTool directly.
    print(build_tools()[0].call("BRSSZ"))

    # Agent (needs OPENAI_API_KEY).
    # print(run_agent("Which of Santos, Shanghai and Rotterdam has the highest congestion right now?"))