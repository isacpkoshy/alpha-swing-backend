"""
FastAPI Gateway for AlphaSwing India (100% Zero-Cost High-Performance Stack):
- Serves the live Full-Stack Institutional Terminal UI at `/` (`http://localhost:8000`)
- Sub-Millisecond SQLite3 WAL + 256MB mmap + L1 RAM Cache (`backend/adapters/storage/sqlite_store.py`)
- Parallel Multi-Threaded NSE Batch Sync (`/api/v1/screener/sync-live`)
- Actionable Swing & Positional Setup Cards (`/api/v1/screener/setups`)
- Live On-Demand NSE Symbol Scanner (`/api/v1/screener/scan-symbol/{symbol}`)
- AI Brain Concall & Filing Second-Opinion Memo (`/api/v1/ai/second-opinion/{symbol}`)
- Persistent Portfolio CRUD, CSV Broker Import & Macro Stress Testing (`/api/v1/portfolio/*`)
"""

import csv
import io
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.adapters.market_data.base import DataProviderRegistry
import backend.adapters.market_data.free_nse_adapter  # Registers 'free_nse' provider
from backend.adapters.storage.sqlite_store import SQLiteWALStore
from backend.engines.quant_screener import QuantScreenerEngine
from backend.engines.ai_brain import AIAnalystBrain
from backend.engines.portfolio_analyzer import PortfolioDiagnosticsEngine
from backend.domain.models import (
    Instrument,
    AssetClass,
    TradeSetupCard,
    AIThesisMemo,
    PortfolioHoldingInput,
    PortfolioDiagnosticsReport,
)

app = FastAPI(
    title="AlphaSwing India — Zero-Cost High-Performance Swing Terminal API",
    version="1.2.0",
    description="Hexagonal API with SQLite3 WAL Sub-Millisecond Cache, Multi-Threaded yfinance Scanner, Gemini 3.8 AI Brain, and Portfolio Stress Engine.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Response-Time-Ms"],
)

wal_store = SQLiteWALStore()
ai_brain = AIAnalystBrain()
portfolio_engine = PortfolioDiagnosticsEngine()
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.middleware("http")
async def add_execution_time_header(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
    return response


@app.get("/", include_in_schema=False)
async def serve_root():
    """Returns API Gateway metadata (or serves local index.html if co-located)."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "service": "AlphaSwing India — Backend Quant & AI Engine API",
        "version": "1.2.0",
        "docs_url": "/docs",
        "health_url": "/api/v1/health",
        "screener_setups_url": "/api/v1/screener/setups",
        "portfolio_url": "/api/v1/portfolio",
    }


@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "online",
        "backend": "FastAPI + SQLite3 WAL (256MB mmap) + ThreadPool yfinance",
        "cost_tier": "100% Zero-Cost Open Source (₹0)",
        "ai_model": ai_brain.MODEL_NAME,
        "gemini_live_key_configured": bool(ai_brain.api_key),
        "storage_telemetry": wal_store.stats(),
    }


@app.get("/api/v1/performance/stats")
async def get_performance_stats():
    """Returns real-time SQLite WAL + L1 RAM cache performance telemetry."""
    return wal_store.stats()


@app.get("/api/v1/extensibility/providers")
async def list_data_providers():
    """Returns registered MarketDataProvider adapters (Free & Paid plug-ins)."""
    return {
        "active_default": "free_nse",
        "registered_providers": DataProviderRegistry.available_providers(),
    }


@app.get("/api/v1/screener/setups", response_model=List[TradeSetupCard])
async def get_swing_setups(
    exchange: str = Query(default="NSE", description="Exchange ID: NSE, BSE"),
    strategy: Optional[str] = Query(default="ALL", description="Strategy slug filter"),
    min_rr: float = Query(default=1.5, description="Minimum Risk-to-Reward ratio"),
    atr_multiplier: float = Query(default=1.5, description="ATR Stop-Loss Multiplier"),
    min_delivery_pct: float = Query(default=0.0, description="Minimum NSE Delivery %"),
    min_rel_vol: float = Query(default=0.0, description="Minimum 20D Relative Volume"),
    with_ai_memo: bool = Query(default=True, description="Include AI Brain Second Opinion"),
    provider_id: str = Query(default="free_nse", description="Pluggable data provider ID"),
):
    provider = DataProviderRegistry.get_provider(provider_id)
    screener = QuantScreenerEngine(provider)
    cards = await screener.scan_universe(
        exchange_id=exchange,
        strategy_filter=strategy,
        min_rr=min_rr,
        atr_multiplier=atr_multiplier,
        min_delivery_pct=min_delivery_pct,
        min_rel_vol=min_rel_vol,
    )

    if with_ai_memo:
        for card in cards:
            fundamentals = await provider.fetch_fundamentals(card.symbol, exchange)
            filings = await provider.fetch_concall_and_filings_context(card.symbol, exchange)
            card.ai_memo = await ai_brain.generate_second_opinion(card, fundamentals, filings)

    return cards


@app.post("/api/v1/screener/sync-live")
async def sync_live_nse_universe(
    exchange: str = Query(default="NSE"),
    provider_id: str = Query(default="free_nse"),
):
    """Concurrently syncs live NSE prices across all universe tickers using an 8-worker thread pool and caches in SQLite WAL."""
    t0 = time.perf_counter()
    provider = DataProviderRegistry.get_provider(provider_id)
    if hasattr(provider, "sync_live_universe_parallel"):
        result = provider.sync_live_universe_parallel(exchange_id=exchange)
    else:
        result = {"total_symbols": 0, "live_synced": 0}
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    return {
        "status": "synced",
        "elapsed_ms": elapsed_ms,
        **result,
        "cache_stats": wal_store.stats(),
    }


@app.get("/api/v1/screener/scan-symbol/{symbol}", response_model=TradeSetupCard)
async def scan_custom_symbol(
    symbol: str,
    exchange: str = Query(default="NSE", description="NSE or BSE"),
    atr_multiplier: float = Query(default=1.5),
    provider_id: str = Query(default="free_nse"),
):
    """Dynamically fetches live NSE/BSE OHLCV via yfinance, caches in SQLite WAL, and builds an Actionable Setup Card."""
    provider = DataProviderRegistry.get_provider(provider_id)
    screener = QuantScreenerEngine(provider)

    sym = symbol.upper().strip()
    existing = await provider.list_active_instruments(exchange)
    inst = next(
        (i for i in existing if i.symbol == sym),
        Instrument(
            symbol=sym,
            exchange_id=exchange,
            name=f"{sym} ({exchange})",
            asset_class=AssetClass.EQUITY,
            sector="NSE Equities",
            industry="Live Scanned Scrip",
        ),
    )

    try:
        card = await screener.build_setup_card_for_instrument(
            inst, exchange, atr_multiplier=atr_multiplier
        )
    except Exception as exc:
        raise HTTPException(
            status_code=404, detail=f"Could not fetch live NSE data for '{sym}': {exc}"
        )

    if not card:
        raise HTTPException(status_code=404, detail=f"No OHLCV bars found for '{sym}'.")

    fundamentals = await provider.fetch_fundamentals(sym, exchange)
    filings = await provider.fetch_concall_and_filings_context(sym, exchange)
    card.ai_memo = await ai_brain.generate_second_opinion(card, fundamentals, filings)
    return card


@app.get("/api/v1/ai/second-opinion/{symbol}", response_model=AIThesisMemo)
async def get_ai_second_opinion(
    symbol: str,
    exchange: str = "NSE",
    provider_id: str = "free_nse",
):
    provider = DataProviderRegistry.get_provider(provider_id)
    screener = QuantScreenerEngine(provider)
    cards = await screener.scan_universe(exchange_id=exchange)
    target_card = next((c for c in cards if c.symbol.upper() == symbol.upper()), None)
    if not target_card:
        raise HTTPException(status_code=404, detail=f"Setup for {symbol} not found.")

    fundamentals = await provider.fetch_fundamentals(symbol, exchange)
    filings = await provider.fetch_concall_and_filings_context(symbol, exchange)
    return await ai_brain.generate_second_opinion(target_card, fundamentals, filings)


@app.get("/api/v1/portfolio")
async def get_persisted_portfolio() -> Dict[str, Any]:
    """Fetches persisted holdings from SQLite WAL and returns full diagnostics report."""
    holdings = wal_store.get_portfolio_holdings()
    report = portfolio_engine.evaluate_portfolio(
        portfolio_name="Core Swing Portfolio (SQLite WAL)",
        sync_source="ZERODHA_CSV_WAL",
        holdings=holdings,
    )
    return {
        "holdings": [h.model_dump() for h in holdings],
        "report": report.model_dump(),
    }


@app.post("/api/v1/portfolio/holdings")
async def upsert_portfolio_holding(holding: PortfolioHoldingInput) -> Dict[str, Any]:
    """Persists a new or updated holding in SQLite WAL and recalculates diagnostics in <1ms."""
    holdings = wal_store.upsert_portfolio_holding(holding)
    report = portfolio_engine.evaluate_portfolio(
        portfolio_name="Core Swing Portfolio (SQLite WAL)",
        sync_source="ZERODHA_CSV_WAL",
        holdings=holdings,
    )
    return {
        "holdings": [h.model_dump() for h in holdings],
        "report": report.model_dump(),
    }


@app.delete("/api/v1/portfolio/holdings/{symbol}")
async def delete_portfolio_holding(symbol: str) -> Dict[str, Any]:
    """Removes a holding from SQLite WAL and recalculates diagnostics."""
    holdings = wal_store.delete_portfolio_holding(symbol)
    report = portfolio_engine.evaluate_portfolio(
        portfolio_name="Core Swing Portfolio (SQLite WAL)",
        sync_source="ZERODHA_CSV_WAL",
        holdings=holdings,
    )
    return {
        "holdings": [h.model_dump() for h in holdings],
        "report": report.model_dump(),
    }


class CSVImportPayload(BaseModel):
    csv_text: str


@app.post("/api/v1/portfolio/import-csv")
async def import_portfolio_csv(payload: CSVImportPayload) -> Dict[str, Any]:
    """
    Zero-Cost Broker CSV Importer (supports Zerodha Console, Angel One, Groww, or custom CSV).
    Expected columns (case-insensitive, flexible names):
    Instrument/Symbol, Qty./Quantity, Avg. cost/AvgPrice, LTP/CurrentPrice, Sector (optional)
    """
    reader = csv.DictReader(io.StringIO(payload.csv_text.strip()))
    imported_count = 0
    for row in reader:
        norm = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items() if k}
        sym = (
            norm.get("instrument")
            or norm.get("symbol")
            or norm.get("ticker")
            or norm.get("tradingsymbol")
            or ""
        ).upper().replace(".NS", "")
        if not sym:
            continue
        try:
            qty = float(norm.get("qty.") or norm.get("qty") or norm.get("quantity") or 0)
            avg_price = float(
                norm.get("avg. cost")
                or norm.get("avg_buy_price")
                or norm.get("avgprice")
                or norm.get("average price")
                or 0
            )
            ltp = float(
                norm.get("ltp")
                or norm.get("current_price")
                or norm.get("close")
                or avg_price
            )
            sector = norm.get("sector") or "Indian Equities"
            if qty <= 0 or avg_price <= 0:
                continue
            holding = PortfolioHoldingInput(
                symbol=sym,
                quantity=qty,
                avg_buy_price=avg_price,
                current_price=ltp,
                sector=sector,
                beta=1.10,
                above_50_dma=ltp >= (avg_price * 0.97),
                stop_loss_price=round(ltp * 0.94, 2),
            )
            wal_store.upsert_portfolio_holding(holding)
            imported_count += 1
        except ValueError:
            continue

    holdings = wal_store.get_portfolio_holdings()
    report = portfolio_engine.evaluate_portfolio(
        portfolio_name="Core Swing Portfolio (SQLite WAL)",
        sync_source="BROKER_CSV_IMPORT",
        holdings=holdings,
    )
    return {
        "imported_count": imported_count,
        "holdings": [h.model_dump() for h in holdings],
        "report": report.model_dump(),
    }


@app.post("/api/v1/portfolio/analyze", response_model=PortfolioDiagnosticsReport)
async def analyze_portfolio(
    holdings: List[PortfolioHoldingInput],
    portfolio_name: str = "Core Swing Portfolio",
    sync_source: str = "ZERODHA",
):
    return portfolio_engine.evaluate_portfolio(
        portfolio_name=portfolio_name,
        sync_source=sync_source,
        holdings=holdings,
    )
