# AlphaSwing Terminal — User Stories & Traceability Matrix

This document tracks all **Phase 1 (Completed MVP)** and **Phase 2 (Active Backlog)** User Stories across [`alpha-swing-backend`](https://github.com/isacpkoshy/alpha-swing-backend/issues) and [`alpha-swing-frontend`](https://github.com/isacpkoshy/alpha-swing-frontend/issues).

> **Mandatory Git & PR Workflow Rule**:
> 1. **Never push directly to `main`**.
> 2. Create a dedicated feature branch per User Story (`git checkout -b feat/us-b6-telegram-alerts`).
> 3. Commit with Conventional Commits referencing the issue (`feat(alerts): add Telegram webhook dispatcher (Closes #6)`).
> 4. Push the branch (`git push -u origin feat/us-b6-telegram-alerts`) and open a **Pull Request** (`gh pr create`) targeting `main`.

---

## 1. Backend Repository (`alpha-swing-backend`)

- **Open Backlog Issues**: [https://github.com/isacpkoshy/alpha-swing-backend/issues](https://github.com/isacpkoshy/alpha-swing-backend/issues)
- **Completed MVP Issues**: [https://github.com/isacpkoshy/alpha-swing-backend/issues?q=is%3Aissue+is%3Aclosed](https://github.com/isacpkoshy/alpha-swing-backend/issues?q=is%3Aissue+is%3Aclosed)

| Story ID | GitHub Issue | Epic Label | Priority | Milestone | Status | Code Implementation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **US-B1** | [Issue #1](https://github.com/isacpkoshy/alpha-swing-backend/issues/1) — Deterministic Swing Setup & ATR Risk Engine | `epic:quant-screener` | `P0` | Phase 1 MVP | ✅ **DONE** | `backend/engines/quant_screener.py` |
| **US-B2** | [Issue #2](https://github.com/isacpkoshy/alpha-swing-backend/issues/2) — Live NSE/BSE Data Adapter & 8-Thread Parallel Scanner | `epic:market-data` | `P0` | Phase 1 MVP | ✅ **DONE** | `backend/adapters/market_data/free_nse_adapter.py` |
| **US-B3** | [Issue #3](https://github.com/isacpkoshy/alpha-swing-backend/issues/3) — Sub-Millisecond SQLite3 WAL + 256MB mmap Cache | `epic:performance` | `P0` | Phase 1 MVP | ✅ **DONE** | `backend/adapters/storage/sqlite_store.py` |
| **US-B4** | [Issue #4](https://github.com/isacpkoshy/alpha-swing-backend/issues/4) — Gemini 3.8 Flash AI Second-Opinion Synthesizer | `epic:ai-brain` | `P0` | Phase 1 MVP | ✅ **DONE** | `backend/engines/ai_brain.py` |
| **US-B5** | [Issue #5](https://github.com/isacpkoshy/alpha-swing-backend/issues/5) — Portfolio Health, CSV Import & Macro Stress API | `epic:portfolio-risk` | `P0` | Phase 1 MVP | ✅ **DONE** | `backend/engines/portfolio_analyzer.py`, `backend/main.py` |
| **US-B6** | [Issue #6](https://github.com/isacpkoshy/alpha-swing-backend/issues/6) — Zero-Cost Telegram Bot Breakout Alert Dispatcher | `epic:alerts` | `P1` | Phase 2 Backlog | ✅ **DONE** | `backend/engines/alert_engine.py`, `POST /api/v1/alerts` |
| **US-B7** | [Issue #7](https://github.com/isacpkoshy/alpha-swing-backend/issues/7) — Historical Swing Strategy Walk-Forward Backtester | `epic:quant-screener` | `P1` | Phase 2 Backlog | ✅ **DONE** | `backend/engines/backtester.py`, `GET /api/v1/screener/backtest/{symbol}` |
| **US-B8** | [Issue #8](https://github.com/isacpkoshy/alpha-swing-backend/issues/8) — Official NSE Bhavcopy EOD Delivery % Scraper | `epic:market-data` | `P1` | Phase 2 Backlog | 📋 **OPEN** | Planned (`free_nse_adapter.py`) |
| **US-B9** | [Issue #10](https://github.com/isacpkoshy/alpha-swing-backend/issues/10) — Zero-Cost 24/7 Cloud Backend Deployment & Market-Hours Cron | `epic:performance` | `P0` | Phase 2 Backlog | ✅ **DONE** | `render.yaml`, `Dockerfile`, `.github/workflows/nse_cloud_cron.yml` |

---

## 2. Frontend Repository (`alpha-swing-frontend`)

- **Open Backlog Issues**: [https://github.com/isacpkoshy/alpha-swing-frontend/issues](https://github.com/isacpkoshy/alpha-swing-frontend/issues)
- **Completed MVP Issues**: [https://github.com/isacpkoshy/alpha-swing-frontend/issues?q=is%3Aissue+is%3Aclosed](https://github.com/isacpkoshy/alpha-swing-frontend/issues?q=is%3Aissue+is%3Aclosed)

| Story ID | GitHub Issue | Epic Label | Priority | Milestone | Status | Code Implementation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **US-F1** | [Issue #1](https://github.com/isacpkoshy/alpha-swing-frontend/issues/1) — TradingView / Deepvue 12-Col Split Terminal & Regime Bar | `epic:chart-terminal` | `P0` | Phase 1 MVP | ✅ **DONE** | `index.html` (Header & Grid Layout) |
| **US-F2** | [Issue #2](https://github.com/isacpkoshy/alpha-swing-frontend/issues/2) — Interactive HTML5 Chart (`15m/1D/1W`) & R:R Overlays | `epic:chart-terminal` | `P0` | Phase 1 MVP | ✅ **DONE** | `index.html` (`drawTradingViewChart`) |
| **US-F3** | [Issue #3](https://github.com/isacpkoshy/alpha-swing-frontend/issues/3) — Sortable 12-Col Screener Table, ATR Selector & Live Sync | `epic:quant-screener` | `P0` | Phase 1 MVP | ✅ **DONE** | `index.html` (`sortTable`, `syncLiveUniverse`) |
| **US-F4** | [Issue #4](https://github.com/isacpkoshy/alpha-swing-frontend/issues/4) — Right Inspector: AI Concall Desk & Position Sizer | `epic:ai-brain` | `P0` | Phase 1 MVP | ✅ **DONE** | `index.html` (`renderAIInspector`, `recalculatePositionSize`) |
| **US-F5** | [Issue #5](https://github.com/isacpkoshy/alpha-swing-frontend/issues/5) — Portfolio Audit, Zero-Cost CSV Importer & Stress Matrix | `epic:portfolio-risk` | `P0` | Phase 1 MVP | ✅ **DONE** | `index.html` (`importBrokerCsv`, `runStressTest`) |
| **US-F6** | [Issue #6](https://github.com/isacpkoshy/alpha-swing-frontend/issues/6) — Custom Multi-Factor Screener Rule Builder Drawer | `epic:quant-screener` | `P1` | Phase 2 Backlog | 📋 **OPEN** | Planned (`index.html` Filter Drawer) |
| **US-F7** | [Issue #7](https://github.com/isacpkoshy/alpha-swing-frontend/issues/7) — One-Click Price Alert & Telegram Notification Modal | `epic:alerts` | `P1` | Phase 2 Backlog | ✅ **DONE** | `index.html` (`toggleAlertsModal`, `createAlertLive`) |
| **US-F8** | [Issue #8](https://github.com/isacpkoshy/alpha-swing-frontend/issues/8) — Strategy Backtest Tear-Sheet & Equity Curve Tab | `epic:chart-terminal` | `P1` | Phase 2 Backlog | ✅ **DONE** | `index.html` (`renderBacktestInspector`, Equity Canvas) |
| **US-F9** | [Issue #10](https://github.com/isacpkoshy/alpha-swing-frontend/issues/10) — Zero-Cost 24/7 Cloud Terminal Hosting via GitHub Pages | `epic:chart-terminal` | `P0` | Phase 2 Backlog | ✅ **DONE** | `.github/workflows/deploy-pages.yml`, Cloud API Switcher |
