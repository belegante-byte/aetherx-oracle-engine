"""PydanticAI agent exposing Aether-X port congestion as a tool.

Requires: pip install pydantic-ai aetherx-oracle
Export:   AETHERX_API_KEY (RapidAPI) and OPENAI_API_KEY for the agent run.
"""

import os

from aetherx import OracleClient


def make_client() -> OracleClient:
    key = os.getenv("AETHERX_API_KEY")
    if not key:
        raise RuntimeError("Export AETHERX_API_KEY (RapidAPI free key).")
    return OracleClient(api_key=key)


def build_agent():
    from pydantic_ai import Agent

    from aetherx import PortRisk

    client = make_client()

    agent = Agent(
        "openai:gpt-4o-mini",
        system_prompt=(
            "You are a supply-chain agent. Use the port_congestion_risk tool to "
            "report congestion, ETA delay and demurrage exposure for ports."
        ),
    )

    @agent.tool
    def port_congestion_risk(port_id: str) -> PortRisk:
        """Get the current port congestion risk, ETA delay and modeled daily
        demurrage for a port (UN/LOCODE, e.g. BRSSZ, CNSHA, NLRTM)."""
        return client.get_port_risk(port_id)

    return agent


def run_agent(question: str) -> None:
    agent = build_agent()
    result = agent.run_sync(question)
    print(result.output)
    if result.all_messages():
        for msg in result.all_messages():
            print(msg)


if __name__ == "__main__":
    # Needs OPENAI_API_KEY for the agent run (AETHERX_API_KEY for the tool).
    print(run_agent("What is the congestion risk at Santos and Rotterdam right now?"))