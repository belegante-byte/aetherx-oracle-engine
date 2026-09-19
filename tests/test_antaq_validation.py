"""Testes da camada de validação ANTAQ (mapeamento complexo -> port_id)."""

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from scripts.validate_antaq import map_port  # noqa: E402


def test_map_santos():
    assert map_port("Santos", "Porto de Santos") == "BRSSZ"


def test_map_paranagua():
    assert map_port("Paranaguá - Antonina", "Terminal da Portos do Paraná") == "BRPNG"


def test_map_itaguai():
    assert map_port("Itaguaí", "Porto de Itaguaí") == "BRITG"


def test_map_rio_niteroi_split():
    assert map_port("Rio de Janeiro -  Niterói", "Rio de Janeiro") == "BRRIO"


def test_map_niteroi_terminal():
    assert map_port("Rio de Janeiro -  Niterói", "Niterói") == "BRNIT"
    assert map_port("Rio de Janeiro -  Niterói", "Estaleiro Renave") == "BRNIT"


def test_map_mojibake_santos():
    assert map_port("Santos", "Porto de Santos") == "BRSSZ"