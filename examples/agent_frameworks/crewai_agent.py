"""CrewAI tool wrapping Aether-X port congestion.

Requires: pip install crewai crewai-tools aetherx-oracle
Export:   AETHERX_API_KEY (RapidAPI) and OPENAI_API_KEY for the crew run.
"""

import os

from aetherx import OracleClient


def make_client() -> OracleClient:
    key = os.getenv("AETHERX_API_KEY")
    if not key:
        raise RuntimeError("Export AETHERX_API_KEY (RapidAPI free key).")
    return OracleClient(api_key=key)


def build_tool():
    from crewai_tools import BaseTool

    client = make_client()

    class PortCongestionTool(BaseTool):
        name: str = "port_congestion_risk"
        description: str = (
            "Get the current port congestion risk, ETA delay and modeled daily "
            "demurrage for a port (UN/LOCODE, e.g. BRSSZ, CNSHA, NLRTM)."
        )

        def _run(self, port_id: str) -> str:
            return client.get_port_risk(port_id).model_dump_json()

    return PortCongestionTool()


def run_crew(port_ids) -> None:
    from crewai import Agent, Crew, Process, Task

    tool = build_tool()
    analyst = Agent(
        role="Supply-chain analyst",
        goal="Monitor port congestion for trade operations.",
        backstory="You flag delays and demurrage exposure from port risk data.",
        tools=[tool],
        verbose=True,
    )
    task = Task(
        description=f"Assess congestion risk for {', '.join(port_ids)} and rank by severity.",
        expected_output="A ranked list of ports by congestion score with ETA delay and demurrage.",
        agent=analyst,
    )
    crew = Crew(agents=[analyst], tasks=[task], process=Process.sequential)
    crew.kickoff()


if __name__ == "__main__":
    # Tool-only (no LLM): call _run directly.
    print(build_tool()._run("BRSSZ"))

    # Crew (needs OPENAI_API_KEY).
    # run_crew(["BRSSZ", "CNSHA", "NLRTM"])