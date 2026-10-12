"""
Pluggable Market Data Provider Interface (Ports & Adapters Pattern).
Any free or paid data feed (yfinance, nselib, Zerodha Kite, Dhan, TrueData, Polygon)
implements this contract so the Quant Engine and AI Brain remain 100% vendor-agnostic.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Type
from backend.domain.models import (
    Instrument,
    OHLCVBar,
    FundamentalSnapshot,
    Timeframe,
)


class MarketDataProvider(ABC):
    """Abstract Port for Market Data, Delivery Volume, and Corporate Filings."""

    provider_id: str = "base"
    supported_exchanges: List[str] = ["NSE", "BSE"]

    @abstractmethod
    async def list_active_instruments(self, exchange_id: str = "NSE") -> List[Instrument]:
        """Return active tradable instruments for the given exchange."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        exchange_id: str = "NSE",
        timeframe: Timeframe = Timeframe.D1,
        lookback_bars: int = 250,
    ) -> List[OHLCVBar]:
        """Fetch historical + latest OHLCV bars with NSE delivery % and technical indicators."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_fundamentals(
        self, symbol: str, exchange_id: str = "NSE"
    ) -> FundamentalSnapshot:
        """Fetch latest quarterly fundamental snapshot and institutional holding data."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_concall_and_filings_context(
        self, symbol: str, exchange_id: str = "NSE"
    ) -> List[Dict[str, str]]:
        """Fetch recent quarterly earnings concall transcripts, BSE/NSE announcements, and news."""
        raise NotImplementedError


class DataProviderRegistry:
    """Registry allowing dynamic hot-swapping between Free and Paid data providers."""

    _providers: Dict[str, Type[MarketDataProvider]] = {}

    @classmethod
    def register(cls, provider_cls: Type[MarketDataProvider]) -> Type[MarketDataProvider]:
        cls._providers[provider_cls.provider_id] = provider_cls
        return provider_cls

    @classmethod
    def get_provider(cls, provider_id: str = "free_nse") -> MarketDataProvider:
        if provider_id not in cls._providers:
            raise ValueError(
                f"Unknown provider '{provider_id}'. Registered: {list(cls._providers.keys())}"
            )
        return cls._providers[provider_id]()

    @classmethod
    def available_providers(cls) -> List[Dict[str, object]]:
        return [
            {
                "provider_id": pid,
                "class_name": pcls.__name__,
                "supported_exchanges": pcls.supported_exchanges,
            }
            for pid, pcls in cls._providers.items()
        ]
