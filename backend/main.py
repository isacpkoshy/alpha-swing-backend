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


@app.get("/api/v1/screener/live-quotes")
async def get_live_nse_bse_quotes(
    symbols: Optional[str] = Query(
        default=None,
        description="Optional comma-separated NSE/BSE symbols; defaults to full 40-stock universe",
    ),
) -> Dict[str, Any]:
    """
    Fetches real-time / latest EOD NSE (.NS) and BSE (.BO) quotes via yfinance in parallel
    so the frontend Screener table always reflects exact market LTP, % change, 14D ATR, and Buy Trigger (`US-B12`).
    """
    from concurrent.futures import ThreadPoolExecutor
    import yfinance as yf

    default_symbols = [
        "CUMMINSIND", "HAL", "BSE", "TRENT", "POLYCAB", "M&M", "CDSL", "DIXON",
        "SUNPHARMA", "ABB", "ICICIBANK", "BHARTIARTL", "LT", "SBIN", "RELIANCE",
        "TATAMOTORS", "BAJFINANCE", "NTPC", "POWERGRID", "TITAN", "TCS", "INFY",
        "PERSISTENT", "BEL", "MCX", "SIEMENS", "KAYNES", "KPITTECH", "MAZDOCK",
        "COCHINSHIP", "ZOMATO", "LUPIN", "IREDA", "JYOTICNC", "NETWEB",
        "WAAREEENER", "ANANTRAJ", "TARIL", "PGEL", "TITAGARH",
    ]
    target_list = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols
        else default_symbols
    )
    aliases = {"ZOMATO": "ETERNAL.NS", "TATAMOTORS": "TMPV.NS"}

    def _fetch_one(sym: str):
        try:
            ticker_str = aliases.get(sym, f"{sym}.NS")
            df = yf.Ticker(ticker_str).history(period="3mo", interval="1d")
            if df is None or df.empty or len(df) < 10:
                df = yf.Ticker(f"{sym}.BO").history(period="3mo", interval="1d")
            if df is None or df.empty or len(df) < 5:
                return sym, None
            close = round(float(df["Close"].iloc[-1]), 2)
            prev = float(df["Close"].iloc[-2]) if len(df) >= 2 else close
            chg = round(((close - prev) / prev) * 100.0, 2)
            atr = round(float((df["High"] - df["Low"]).tail(14).mean()), 2)
            atr_pct = round((atr / close) * 100.0, 2)
            high_10 = round(float(df["High"].tail(10).max()), 2)
            trigger = high_10 if high_10 > close else round(close * 1.005, 2)
            return sym, {
                "price": close,
                "change": chg,
                "atr": atr,
                "atrPct": atr_pct,
                "trigger": trigger,
            }
        except Exception:
            return sym, None

    t0 = time.perf_counter()
    quotes: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        for sym, data in pool.map(_fetch_one, target_list):
            if data:
                quotes[sym] = data

    return {
        "status": "live",
        "count": len(quotes),
        "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 1),
        "quotes": quotes,
    }


@app.post("/api/v1/screener/sync-live")
async def sync_live_nse_universe(
    exchange: str = Query(default="ALL"),
    provider_id: str = Query(default="free_nse"),
):
    """Concurrently syncs live NSE & BSE prices across all universe tickers and returns live quote map."""
    t0 = time.perf_counter()
    live_payload = await get_live_nse_bse_quotes()
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    return {
        "status": "synced",
        "elapsed_ms": elapsed_ms,
        "live_synced": live_payload["count"],
        "quotes": live_payload["quotes"],
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


# ============================================================================
# ZERO-COST TELEGRAM & CLOUD BREAKOUT ALERT ENDPOINTS (US-B6 & US-B9)
# ============================================================================
from backend.engines.alert_engine import TelegramAlertEngine, PriceAlertRule

alert_engine = TelegramAlertEngine()


@app.get("/api/v1/alerts")
async def list_price_alerts() -> Dict[str, Any]:
    alerts = alert_engine.list_alerts()
    return {"count": len(alerts), "alerts": [a.model_dump() for a in alerts]}


@app.post("/api/v1/alerts")
async def create_price_alert(rule: PriceAlertRule) -> Dict[str, Any]:
    alerts = alert_engine.add_alert(rule)
    return {"count": len(alerts), "alerts": [a.model_dump() for a in alerts]}


@app.delete("/api/v1/alerts/{alert_id}")
async def remove_price_alert(alert_id: str) -> Dict[str, Any]:
    alerts = alert_engine.delete_alert(alert_id)
    return {"count": len(alerts), "alerts": [a.model_dump() for a in alerts]}


class EvaluateAlertsRequest(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None


@app.post("/api/v1/alerts/evaluate")
async def evaluate_alerts_now(
    req: Optional[EvaluateAlertsRequest] = None,
    provider_id: str = Query(default="free_nse"),
) -> Dict[str, Any]:
    provider = DataProviderRegistry.get_provider(provider_id)
    return await alert_engine.evaluate_active_alerts(
        provider,
        bot_token=req.telegram_bot_token if req else None,
        chat_id=req.telegram_chat_id if req else None,
    )


class GenerateAIAlertsBatchRequest(BaseModel):
    exchange: str = "ALL"  # "ALL" (NSE + BSE), "NSE", or "BSE"
    min_ai_score: int = 75
    symbols: Optional[List[str]] = None
    persist_to_watchbook: bool = True
    dispatch_telegram: bool = False
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None


@app.post("/api/v1/alerts/generate-ai-batch")
async def generate_ai_alerts_for_nse_and_bse(
    req: Optional[GenerateAIAlertsBatchRequest] = None,
    provider_id: str = Query(default="free_nse"),
) -> Dict[str, Any]:
    """
    Pan-Exchange (NSE + BSE) AI Alert Generator (`US-B11`):
    Scans NSE (.NS) and BSE (.BO) stocks, runs the AI Second-Opinion Brain, and generates
    actionable AI Entry Pivot, Stop-Loss (1.5x ATR), and 2R Target alerts with concall/BSE-filing catalysts.
    """
    params = req or GenerateAIAlertsBatchRequest()
    provider = DataProviderRegistry.get_provider(provider_id)
    screener = QuantScreenerEngine(provider)

    exchange_mode = (params.exchange or "ALL").upper().strip()
    cards: List[TradeSetupCard] = []

    if params.symbols:
        for raw_sym in params.symbols:
            clean = raw_sym.upper().strip()
            ex = "BSE" if clean.endswith(".BO") else ("NSE" if clean.endswith(".NS") else (exchange_mode if exchange_mode in ("NSE", "BSE") else "NSE"))
            sym = clean.replace(".BO", "").replace(".NS", "")
            inst = Instrument(
                symbol=sym,
                exchange_id=ex,
                name=f"{sym} ({ex})",
                asset_class=AssetClass.EQUITY,
                sector=f"{ex} Equities",
                industry="AI Alert Scanned Scrip",
            )
            try:
                c = await screener.build_setup_card_for_instrument(inst, ex, atr_multiplier=1.5)
                if c:
                    cards.append(c)
            except Exception:
                continue
    else:
        cards = await screener.scan_universe(exchange_id=exchange_mode, atr_multiplier=1.5)

    generated_alerts: List[Dict[str, Any]] = []
    for card in cards:
        ex = getattr(card, "exchange_id", None) or ("BSE" if card.symbol in ("MAZDOCK", "IREDA") else "NSE")
        fundamentals = await provider.fetch_fundamentals(card.symbol, ex)
        filings = await provider.fetch_concall_and_filings_context(card.symbol, ex)
        memo = await ai_brain.generate_second_opinion(card, fundamentals, filings)
        if memo.confidence_score < params.min_ai_score:
            continue

        is_bullish = memo.stance.upper() in ("BULLISH", "STRONG_BUY", "ACCUMULATE") or memo.confidence_score >= 82
        condition = "ABOVE_OR_EQUAL" if is_bullish else "BELOW_OR_EQUAL"
        alert_type = "AI_PIVOT_BREAKOUT" if is_bullish else "AI_STOP_LOSS_GUARDRAIL"
        trigger_px = card.trade_plan.entry_price if is_bullish else card.trade_plan.stop_loss_price

        rule = PriceAlertRule(
            alert_id=f"AI-{ex}-{card.symbol}",
            symbol=card.symbol,
            exchange=ex,
            condition=condition,
            alert_type=alert_type,
            target_price=trigger_px,
            stop_loss_price=card.trade_plan.stop_loss_price,
            notes=f"[🤖 {memo.stance} • {memo.confidence_score}/100] {memo.executive_summary[:140]}",
        )
        if params.persist_to_watchbook:
            alert_engine.add_alert(rule)

        generated_alerts.append(
            {
                "alert_id": rule.alert_id,
                "symbol": card.symbol,
                "exchange": ex,
                "company_name": card.company_name,
                "ltp": card.current_price,
                "entry_pivot": card.trade_plan.entry_price,
                "stop_loss": card.trade_plan.stop_loss_price,
                "target_2r": card.trade_plan.target_1_price,
                "ai_verdict": memo.stance,
                "ai_score": memo.confidence_score,
                "ai_catalyst": memo.bullish_catalysts[0] if memo.bullish_catalysts else memo.executive_summary,
                "ai_risk": memo.risk_factors[0] if memo.risk_factors else "1.5x ATR Stop-Loss Invalidation",
                "alert_type": alert_type,
            }
        )

    telegram_result = None
    if params.dispatch_telegram and generated_alerts:
        lines = [f"🤖 *AlphaSwing AI Alert Digest ({exchange_mode} — {len(generated_alerts)} Setups)*"]
        for item in generated_alerts[:12]:
            lines.append(
                f"• *{item['exchange']}:{item['symbol']}* (`🤖 {item['ai_verdict']} {item['ai_score']}`) — "
                f"Pivot `₹{item['entry_pivot']:,.1f}` | Stop `₹{item['stop_loss']:,.1f}` | 2R `₹{item['target_2r']:,.1f}`"
            )
        telegram_result = alert_engine.send_telegram_notification(
            "\n".join(lines),
            bot_token=params.telegram_bot_token,
            chat_id=params.telegram_chat_id,
        )

    return {
        "exchange_scope": exchange_mode,
        "generated_count": len(generated_alerts),
        "generated_alerts": generated_alerts,
        "telegram_dispatch": telegram_result,
    }


# ============================================================================
# HISTORICAL 3-YEAR WALK-FORWARD BACKTESTER ENDPOINTS (US-B7 & US-B10)
# ============================================================================
from backend.engines.backtester import WalkForwardBacktester, SymbolBacktestReport

backtester_engine = WalkForwardBacktester()


@app.get("/api/v1/screener/backtest/{symbol}", response_model=SymbolBacktestReport)
async def get_symbol_backtest(
    symbol: str,
    exchange: str = Query(default="NSE"),
    atr_multiplier: float = Query(default=1.5),
) -> SymbolBacktestReport:
    return backtester_engine.run_symbol_backtest(
        symbol=symbol, exchange=exchange, atr_multiplier=atr_multiplier
    )


@app.get("/api/v1/screener/backtest-universe")
async def get_universe_backtest_summary(
    atr_multiplier: float = Query(default=1.5),
) -> Dict[str, Any]:
    return backtester_engine.run_universe_summary(atr_multiplier=atr_multiplier)



