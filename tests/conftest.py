"""Fixtures compartilhadas da suíte.

O transporte MCP montado em main.app cria um StreamableHTTPSessionManager cujo
lifespan (session_manager.run()) só pode ser executado UMA vez por instância.
Por isso todos os testes que exercitam /mcp compartilham um único portal
(TestClient aberto uma vez, sessão inteira) via fixture `mcp_client`.
"""
import pytest
from starlette.testclient import TestClient


@pytest.fixture(scope="session")
def mcp_client():
    from src.api.main import app

    with TestClient(app) as c:
        yield c