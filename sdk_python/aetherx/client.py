"""Aether-X Port Congestion Oracle - Python SDK client."""

import asyncio
from typing import Dict, List, Optional

import requests
from pydantic import BaseModel, Field

DEFAULT_RAPIDAPI_HOST = "aether-x-port-congestion-oracle.p.rapidapi.com"
RISK_ENDPOINT = "/v1/port-risk"
TREND_ENDPOINT = "/v1/port-trend"
PORTS_RISK_ENDPOINT = "/v1/ports-risk"


class PortRisk(BaseModel):
    """Predictive congestion signal for a single port."""

    port_id: str = Field(..., description="UN/LOCODE do porto (ex: BRSSZ)")
    port_name: str = Field(..., description="Nome do porto")
    country: str = Field(..., description="País do porto")
    congestion_score: float = Field(..., description="Score de congestão (0.0 a 1.0)")
    eta_delay_days: float = Field(..., description="Atraso estimado de ETA em dias")
    waiting_vessels: int = Field(..., description="Navios aguardando/ancorados")
    freight_volatility_index: float = Field(..., description="Índice de volatilidade de frete")
    estimated_daily_demurrage_usd: int = Field(..., description="Demurrage diária estimada (USD)")
    updated_at: str = Field(..., description="Timestamp da última atualização")


class PortTrendProjection(BaseModel):
    """Projeção de congestão para um horizonte (24h / 48h / 72h)."""

    congestion_score: float = Field(..., description="Score projetado (0.0 a 1.0)")
    eta_delay_days: float = Field(..., description="Atraso de ETA projetado em dias")
    estimated_daily_demurrage_usd: int = Field(..., description="Demurrage projetada (USD/dia)")


class PortTrend(BaseModel):
    """Projeção de congestão do porto nos horizontes 24/48/72 horas."""

    port_id: str = Field(..., description="UN/LOCODE do porto")
    port_name: str = Field(..., description="Nome do porto")
    country: str = Field(..., description="País do porto")
    trend: str = Field(..., description="Rótulo da tendência (acelerando / estável / descongestionando)")
    congestion_score: float = Field(..., description="Score atual (0.0 a 1.0)")
    projection: Dict[str, PortTrendProjection] = Field(..., description="Projeções por horizonte")
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
            PortRisk com acesso direto via atributo (inclui
            ``estimated_daily_demurrage_usd``).

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

    def get_ports_risk(self, port_ids: List[str]) -> List[PortRisk]:
        """Consulta vários portos em UMA chamada (endpoint batch).

        Constrói a lista de UN/LOCODEs separada por vírgula em ``port_ids``
        para até 20 portos por request.

        Raises:
            requests.HTTPError: se a API retornar um status de erro.
        """
        ids = [p.strip().upper() for p in port_ids if p and p.strip()]
        if not ids:
            return []

        url = f"{self.base_url}{PORTS_RISK_ENDPOINT}"
        headers = self._headers()
        params = {"port_ids": ",".join(ids)}
        response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", payload if isinstance(payload, list) else [])
        return [PortRisk.model_validate(item) for item in results]

    def get_port_trend(self, port_id: str) -> PortTrend:
        """Retorna a projeção de congestão 24h / 48h / 72h para um porto.

        Args:
            port_id: Código UN/LOCODE do porto (ex: "BRSSZ", "NLRTM").

        Returns:
            PortTrend com o rótulo da tendência e as projeções por horizonte.

        Raises:
            ValueError: se port_id for vazio.
            requests.HTTPError: se a API retornar um status de erro.
        """
        if not port_id:
            raise ValueError("port_id é obrigatório (ex: 'BRSSZ').")
        url = f"{self.base_url}{TREND_ENDPOINT}"
        headers = self._headers()
        params = {"port_id": port_id}
        response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        response.raise_for_status()
        return PortTrend.model_validate(response.json())

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

    async def get_port_trend_async(self, port_id: str) -> PortTrend:
        """Versão assíncrona de :meth:`get_port_trend` (requer o extra ``async``)."""
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise ImportError(
                "httpx é necessário para métodos assíncronos. "
                "Instale com: pip install aetherx-oracle[async]"
            ) from exc

        if not port_id:
            raise ValueError("port_id é obrigatório (ex: 'BRSSZ').")
        url = f"{self.base_url}{TREND_ENDPOINT}"
        headers = self._headers()
        params = {"port_id": port_id}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return PortTrend.model_validate(response.json())

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

    def _headers(self) -> Dict[str, str]:
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host,
        }

    def _build_request(self, port_id: str):
        if not port_id:
            raise ValueError("port_id é obrigatório (ex: 'BRSSZ').")

        url = f"{self.base_url}{RISK_ENDPOINT}"
        headers = self._headers()
        params = {"port_id": port_id}
        return url, headers, params
