-- ============================================================================
-- AlphaSwing India: Extensible Multi-Asset, Multi-Market Schema
-- Engine: PostgreSQL 16 + TimescaleDB + pgvector
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "timescaledb";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ----------------------------------------------------------------------------
-- 1. EXCHANGES & MULTI-ASSET INSTRUMENTS
-- ----------------------------------------------------------------------------
CREATE TABLE exchanges (
    id VARCHAR(20) PRIMARY KEY,              -- 'NSE', 'BSE', 'NFO', 'NASDAQ', 'NYSE', 'MCX'
    name VARCHAR(100) NOT NULL,
    country_code CHAR(2) NOT NULL,           -- 'IN', 'US'
    currency VARCHAR(10) NOT NULL,           -- 'INR', 'USD'
    timezone VARCHAR(50) NOT NULL,           -- 'Asia/Kolkata'
    trading_hours JSONB NOT NULL,            -- {"open": "09:15", "close": "15:30", "days": [1,2,3,4,5]}
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE instruments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exchange_id VARCHAR(20) NOT NULL REFERENCES exchanges(id),
    symbol VARCHAR(50) NOT NULL,             -- 'TRENT', 'BEL', 'DIXON', 'HAL'
    isin VARCHAR(20),
    name VARCHAR(255) NOT NULL,
    asset_class VARCHAR(30) NOT NULL,        -- 'EQUITY', 'INDEX', 'ETF', 'OPTION', 'FUTURE', 'COMMODITY', 'CRYPTO'
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap_category VARCHAR(30),         -- 'LARGE_CAP', 'MID_CAP', 'SMALL_CAP'
    lot_size INT DEFAULT 1,
    tick_size NUMERIC(10, 4) DEFAULT 0.05,
    provider_mappings JSONB DEFAULT '{}',    -- {"yfinance": "TRENT.NS", "nselib": "TRENT", "zerodha": "500870"}
    extended_metadata JSONB DEFAULT '{}',    -- Option strike/expiry, index constituent flags, F&O ban status
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(exchange_id, symbol)
);

CREATE INDEX idx_instruments_sector ON instruments(sector);
CREATE INDEX idx_instruments_asset_class ON instruments(asset_class);
CREATE INDEX idx_instruments_provider_mappings ON instruments USING GIN (provider_mappings);

-- ----------------------------------------------------------------------------
-- 2. TIME-SERIES MARKET DATA & FUNDAMENTALS (TimescaleDB)
-- ----------------------------------------------------------------------------
CREATE TABLE market_data_ohlcv (
    time TIMESTAMPTZ NOT NULL,
    instrument_id UUID NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
    timeframe VARCHAR(10) NOT NULL,          -- '5m', '15m', '1h', '1d', '1w'
    open NUMERIC(18, 4) NOT NULL,
    high NUMERIC(18, 4) NOT NULL,
    low NUMERIC(18, 4) NOT NULL,
    close NUMERIC(18, 4) NOT NULL,
    volume BIGINT NOT NULL,
    delivery_volume BIGINT,                  -- NSE/BSE institutional accumulation metric
    delivery_percentage NUMERIC(6, 2),
    vwap NUMERIC(18, 4),
    ema_20 NUMERIC(18, 4),
    sma_50 NUMERIC(18, 4),
    sma_200 NUMERIC(18, 4),
    rsi_14 NUMERIC(6, 2),
    atr_14 NUMERIC(18, 4),
    rel_volume_20d NUMERIC(8, 2),
    custom_indicators JSONB DEFAULT '{}',    -- VCP contraction %, SuperTrend, Bollinger Width, Option OI
    PRIMARY KEY (time, instrument_id, timeframe)
);

SELECT create_hypertable('market_data_ohlcv', 'time', if_not_exists => TRUE);
CREATE INDEX idx_ohlcv_instrument_tf ON market_data_ohlcv(instrument_id, timeframe, time DESC);

CREATE TABLE fundamental_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    instrument_id UUID NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
    period_end_date DATE NOT NULL,
    market_cap_cr NUMERIC(18, 2),
    pe_ratio NUMERIC(10, 2),
    roe_pct NUMERIC(8, 2),
    roce_pct NUMERIC(8, 2),
    debt_to_equity NUMERIC(8, 2),
    sales_growth_yoy NUMERIC(8, 2),
    profit_growth_yoy NUMERIC(8, 2),
    promoter_holding_pct NUMERIC(6, 2),
    promoter_pledge_pct NUMERIC(6, 2),
    fii_holding_pct NUMERIC(6, 2),
    dii_holding_pct NUMERIC(6, 2),
    extra_ratios JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(instrument_id, period_end_date)
);

-- ----------------------------------------------------------------------------
-- 3. SCREENER STRATEGIES & ACTIONABLE TRADE SETUP CARDS
-- ----------------------------------------------------------------------------
CREATE TABLE screening_strategies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL,           -- 'SWING', 'POSITIONAL', 'MOMENTUM', 'MEAN_REVERSION'
    holding_period_days INT4RANGE,
    rule_definition JSONB NOT NULL,          -- Declarative AST for strategy evaluation
    risk_model_config JSONB NOT NULL,        -- {"sl_atr_mult": 1.5, "t1_rr": 1.5, "t2_rr": 2.5, "t3_rr": 4.0}
    is_system_strategy BOOLEAN DEFAULT TRUE,
    created_by UUID,
    version INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE trade_setups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    strategy_id UUID NOT NULL REFERENCES screening_strategies(id),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    timeframe VARCHAR(10) NOT NULL DEFAULT '1d',
    direction VARCHAR(10) NOT NULL DEFAULT 'LONG',
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    trigger_price NUMERIC(18, 4) NOT NULL,
    entry_zone_min NUMERIC(18, 4) NOT NULL,
    entry_zone_max NUMERIC(18, 4) NOT NULL,
    stop_loss_price NUMERIC(18, 4) NOT NULL,
    stop_loss_pct NUMERIC(6, 2) NOT NULL,
    target_1_price NUMERIC(18, 4) NOT NULL,
    target_2_price NUMERIC(18, 4) NOT NULL,
    target_3_price NUMERIC(18, 4),
    risk_reward_ratio NUMERIC(6, 2) NOT NULL,
    quant_conviction_score NUMERIC(5, 2),
    setup_checklist JSONB NOT NULL,
    chart_annotations JSONB DEFAULT '{}',
    outcome_return_pct NUMERIC(8, 2),
    closed_at TIMESTAMPTZ
);

CREATE INDEX idx_trade_setups_status_date ON trade_setups(status, detected_at DESC);

-- ----------------------------------------------------------------------------
-- 4. AI BRAIN (RAG KNOWLEDGE BASE & SECOND-OPINION MEMOS)
-- ----------------------------------------------------------------------------
CREATE TABLE corporate_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    instrument_id UUID NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
    doc_type VARCHAR(50) NOT NULL,           -- 'CONCALL_TRANSCRIPT', 'EARNINGS_RELEASE', 'BSE_ANNOUNCEMENT', 'NEWS'
    title TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    source_url TEXT,
    raw_text TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE document_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES corporate_documents(id) ON DELETE CASCADE,
    instrument_id UUID NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(768),                   -- gemini-embedding-001 / gemini-embedding-2
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_doc_embeddings_vec ON document_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE TABLE ai_thesis_memos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    trade_setup_id UUID REFERENCES trade_setups(id) ON DELETE SET NULL,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    model_used VARCHAR(100) NOT NULL DEFAULT 'gemini-3.8-flash',
    verdict VARCHAR(30) NOT NULL,            -- 'STRONG_ALIGNMENT', 'MODERATE_ALIGNMENT', 'NEUTRAL', 'CAUTION_CONFLICT'
    ai_conviction_score INT CHECK (ai_conviction_score BETWEEN 0 AND 100),
    executive_summary TEXT NOT NULL,
    concall_highlights JSONB NOT NULL,
    sector_tailwinds JSONB NOT NULL,
    red_flags_and_risks JSONB NOT NULL,
    citations JSONB DEFAULT '[]',
    expires_at TIMESTAMPTZ
);

-- ----------------------------------------------------------------------------
-- 5. USERS, PORTFOLIOS & DIAGNOSTIC STRESS TESTING
-- ----------------------------------------------------------------------------
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(150),
    password_hash TEXT,
    subscription_tier VARCHAR(30) DEFAULT 'FREE',
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE portfolios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    sync_source VARCHAR(30) NOT NULL,        -- 'MANUAL', 'CSV', 'ZERODHA', 'ANGELONE', 'UPSTOX'
    broker_connection_meta JSONB DEFAULT '{}',
    total_capital NUMERIC(18, 2),
    cash_balance NUMERIC(18, 2) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE portfolio_holdings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    quantity NUMERIC(18, 4) NOT NULL,
    avg_buy_price NUMERIC(18, 4) NOT NULL,
    active_stop_loss NUMERIC(18, 4),
    target_price NUMERIC(18, 4),
    linked_setup_id UUID REFERENCES trade_setups(id),
    notes TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(portfolio_id, instrument_id)
);

CREATE TABLE portfolio_diagnostics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    health_score INT CHECK (health_score BETWEEN 0 AND 100),
    portfolio_beta NUMERIC(6, 3),
    total_capital_at_risk_pct NUMERIC(6, 2),
    sector_allocation JSONB NOT NULL,
    concentration_warnings JSONB NOT NULL,
    holding_health_flags JSONB NOT NULL,
    stress_test_scenarios JSONB NOT NULL
);

-- Seed Initial Exchanges
INSERT INTO exchanges (id, name, country_code, currency, timezone, trading_hours) VALUES
('NSE', 'National Stock Exchange of India', 'IN', 'INR', 'Asia/Kolkata', '{"open": "09:15", "close": "15:30", "days": [1,2,3,4,5]}'),
('BSE', 'Bombay Stock Exchange', 'IN', 'INR', 'Asia/Kolkata', '{"open": "09:15", "close": "15:30", "days": [1,2,3,4,5]}'),
('NFO', 'NSE Futures & Options', 'IN', 'INR', 'Asia/Kolkata', '{"open": "09:15", "close": "15:30", "days": [1,2,3,4,5]}'),
('NASDAQ', 'NASDAQ Stock Market', 'US', 'USD', 'America/New_York', '{"open": "09:30", "close": "16:00", "days": [1,2,3,4,5]}')
ON CONFLICT (id) DO NOTHING;
