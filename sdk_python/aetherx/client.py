"""Aether-X Port Congestion Oracle - Python SDK client."""

import asyncio
from typing import List, Optional

import requests
from pydantic import BaseModel, Field

DEFAULT_RAPIDAPI_HOST = "aether-x-port-congestion-oracle.p.rapidapi.com"
RISK_ENDPOINT = "/v1/port-risk"


class PortRisk(BaseModel):
    """Predictive congestion signal for a single port."""

    port_id: str = Field(..., description="UN/LOCODE do porto (ex: BRSSZ)")
    port_name: str = Field(..., description="Nome do porto")
    country: str = Field(..., description="País do porto")
    congestion_score: float = Field(..., description="Score de congestão (0.0 a 1.0)")
    eta_delay_days: float = Field(..., description="Atraso estimado de ETA em dias")
    waiting_vessels: int = Field(..., description="Navios aguardando/ancorados")
    freight_volatility_index: float = Field(..., description="Índice de volatilidade de frete")
    updated_at: str = Field(..., description="Timestamp da última atualização")


class OracleClient:
    """Cliente para a API Aether-X Port Congestion Oracle (via RapidAPI).

    Exemplo:
        >>> from aetherx import OracleClient
        >>> client = OracleClient(api_key="SUA_RAPIDAPI_KEY")
        >>> risk = client.get_port_risk("BRSSZ")
        >>> print(risk.congestion_score, risk.waiting_vessels)
    """

    def __init__(
        self,
        api_key: str,
        host: str = DEFAULT_RAPIDAPI_HOST,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key é obrigatória (sua chave da RapidAPI).")

        self.api_key = api_key
        self.host = host
        self.base_url = (base_url or f"https://{host}").rstrip("/")
        self.timeout = timeout

    def get_port_risk(self, port_id: str) -> PortRisk:
        """Retorna o sinal preditivo de congestão para um porto.

        Args:
            port_id: Código UN/LOCODE do porto (ex: "BRSSZ", "CNSHA").

        Returns:
            PortRisk com acesso direto via atributo.

        Raises:
            ValueError: se port_id for vazio.
            requests.HTTPError: se a API retornar um status de erro.
        """
        url, headers, params = self._build_request(port_id)
        response = requests.get(
            url, headers=headers, params=params, timeout=self.timeout
        )
        response.raise_for_status()
        return PortRisk.model_validate(response.json())

    async def get_port_risk_async(self, port_id: str) -> PortRisk:
        """Versão assíncrona de :meth:`get_port_risk` (requer o extra ``async``).

        Uso:
            >>> import asyncio
            >>> client = OracleClient(api_key="SUA_RAPIDAPI_KEY")
            >>> risk = asyncio.run(client.get_port_risk_async("BRSSZ"))

        Instale com: ``pip install aetherx-oracle[async]``
        """
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise ImportError(
                "httpx é necessário para métodos assíncronos. "
                "Instale com: pip install aetherx-oracle[async]"
            ) from exc

        url, headers, params = self._build_request(port_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return PortRisk.model_validate(response.json())

    async def get_ports_risk_async(self, port_ids: List[str]) -> List[PortRisk]:
        """Consulta vários portos em paralelo via ``asyncio.gather``.

        Ideal para fundos quantitativos e bots que monitoram uma carteira de portos.
        """
        if not port_ids:
            return []
        return list(
            await asyncio.gather(
                *(self.get_port_risk_async(port_id) for port_id in port_ids)
            )
        )

    def _build_request(self, port_id: str):
        if not port_id:
            raise ValueError("port_id é obrigatório (ex: 'BRSSZ').")

        url = f"{self.base_url}{RISK_ENDPOINT}"
        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host,
        }
        params = {"port_id": port_id}
        return url, headers, params
