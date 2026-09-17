import os
import sys


# Garantir importação do projeto
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


from src.ingestion.santos_scraper import fetch_santos_lineup


if __name__ == "__main__":
    print("[AETHER-X PROD INIT] Inicializando e semeando o banco DuckDB para produção...")
    fetch_santos_lineup()
    print("[AETHER-X PROD INIT] Banco semeado com sucesso!")