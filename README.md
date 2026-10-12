# AlphaSwing Backend (`alpha-swing-backend`)

High-performance, **100% zero-cost (`₹0`)** Python FastAPI Backend, Quantitative Swing Screener Engine, Gemini 3.8 AI Research Brain, and SQLite3 WAL Portfolio Risk Engine for Indian Equities (**NSE & BSE**).

> **Frontend Repository**: Pair this backend with [`alpha-swing-frontend`](https://github.com/isacpkoshy/alpha-swing-frontend).

---

## Architecture & Core Engines

- **`backend/main.py`**: FastAPI Gateway with CORS middleware and `X-Response-Time-Ms` sub-millisecond telemetry header.
- **`backend/adapters/storage/sqlite_store.py`**: Thread-safe `SQLite3 WAL` (`256 MB mmap` + `64 MB` page cache + L1 RAM cache) delivering `< 0.5 ms` read/write latency.
- **`backend/adapters/market_data/free_nse_adapter.py`**: Pluggable `free_nse` market data adapter with live Yahoo Finance (`yfinance` `.NS` / `.BO`) indicator computation and an **8-thread parallel NSE universe scanner**.
- **`backend/engines/quant_screener.py`**: Deterministic Swing Setup generator computing Entry Pivot Zone, customizable `1.2x / 1.5x / 2.0x ATR_14` Stop-Loss, Targets `1/2/3`, Risk-to-Reward, and 4-point institutional checklist.
- **`backend/engines/ai_brain.py`**: Google Gemini (`gemini-3.8-flash` via `google-genai` Interactions API) Concall & Exchange Filing Second-Opinion Synthesizer with offline fallback.
- **`backend/engines/portfolio_analyzer.py`**: Portfolio Health Score (`0–100`), Weighted Beta, `>30%` Sector Concentration checks, 50-DMA breach alerts, and Macro Stress Testing.
- **`database/schema.sql`**: Extensible multi-exchange, multi-asset PostgreSQL 16 + TimescaleDB + `pgvector` schema.

---

## Quickstart (Port `8000`)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Start API Server on http://127.0.0.1:8000
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Interactive Swagger UI**: `http://127.0.0.1:8000/docs`
- **Health & WAL Cache Telemetry**: `http://127.0.0.1:8000/api/v1/health`
