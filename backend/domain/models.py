"""
Core Domain Models for AlphaSwing India Platform.
Designed for multi-market (NSE, BSE, NASDAQ) and multi-asset (Equity, ETF, F&O, Crypto) extensibility.
"""

from datetime import datetime, date
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class AssetClass(str, Enum):
    EQUITY = "EQUITY"
    INDEX = "INDEX"
    ETF = "ETF"
    OPTION = "OPTION"
    FUTURE = "FUTURE"
    COMMODITY = "COMMODITY"
    CRYPTO = "CRYPTO"


class Timeframe(str, Enum):
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    D1 = "1d"
    W1 = "1w"


class TradeDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class SetupStatus(str, Enum):
    ACTIVE = "ACTIVE"
    TRIGGERED = "TRIGGERED"
    TARGET_1_HIT = "TARGET_1_HIT"
    TARGET_2_HIT = "TARGET_2_HIT"
    STOPPED_OUT = "STOPPED_OUT"
    INVALIDATED = "INVALIDATED"


class AIAlignmentVerdict(str, Enum):
    STRONG_ALIGNMENT = "STRONG_ALIGNMENT"
    MODERATE_ALIGNMENT = "MODERATE_ALIGNMENT"
    NEUTRAL = "NEUTRAL"
    CAUTION_CONFLICT = "CAUTION_CONFLICT"


class Instrument(BaseModel):
    symbol: str = Field(description="Exchange ticker symbol, e.g., TRENT")
    exchange_id: str = Field(default="NSE", description="Exchange identifier: NSE, BSE, NASDAQ")
    name: str
    asset_class: AssetClass = AssetClass.EQUITY
    sector: str
    industry: str
    market_cap_category: str = "LARGE_CAP"
    provider_mappings: Dict[str, str] = Field(default_factory=dict)
    extended_metadata: Dict[str, Any] = Field(default_factory=dict)


class OHLCVBar(BaseModel):
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    delivery_volume: Optional[int] = None
    delivery_percentage: Optional[float] = None
    ema_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    rsi_14: Optional[float] = None
    atr_14: Optional[float] = None
    rel_volume_20d: Optional[float] = None
    custom_indicators: Dict[str, Any] = Field(default_factory=dict)


class FundamentalSnapshot(BaseModel):
    symbol: str
    period_end_date: date
    market_cap_cr: float
    pe_ratio: float
    roe_pct: float
    roce_pct: float
    debt_to_equity: float
    sales_growth_yoy: float
    profit_growth_yoy: float
    promoter_holding_pct: float
    promoter_pledge_pct: float
    fii_holding_pct: float
    dii_holding_pct: float
    extra_ratios: Dict[str, Any] = Field(default_factory=dict)


class ChecklistItem(BaseModel):
    rule: str
    passed: bool
    detail: str


class AIThesisMemo(BaseModel):
    symbol: str = Field(description="Stock ticker symbol")
    verdict: AIAlignmentVerdict = Field(
        description="Alignment verdict between technical setup and qualitative fundamentals"
    )
    ai_conviction_score: int = Field(
        ge=0, le=100, description="AI qualitative conviction score from 0 to 100"
    )
    executive_summary: str = Field(
        description="Concise 2-3 sentence Second Opinion thesis combining technicals and fundamentals"
    )
    concall_highlights: List[str] = Field(
        description="Key takeaways from latest quarterly earnings concall, capex, guidance, order book"
    )
    sector_tailwinds: List[str] = Field(
        description="Sectoral, policy (PLI, budget), or macro catalysts supporting the move"
    )
    red_flags_and_risks: List[str] = Field(
        description="Key risks, margin pressures, promoter pledges, or upcoming event risks"
    )
    model_used: str = Field(default="gemini-3.8-flash")


class TradeSetupCard(BaseModel):
    setup_id: str
    symbol: str
    company_name: str
    exchange: str = "NSE"
    sector: str
    strategy_slug: str
    strategy_name: str
    timeframe: Timeframe = Timeframe.D1
    direction: TradeDirection = TradeDirection.LONG
    status: SetupStatus = SetupStatus.ACTIVE
    detected_at: datetime
    current_price: float
    trigger_price: float
    entry_zone_min: float
    entry_zone_max: float
    stop_loss_price: float
    stop_loss_pct: float
    target_1_price: float
    target_2_price: float
    target_3_price: float
    risk_reward_ratio: float
    quant_conviction_score: float
    delivery_pct: float
    rel_volume_20d: float
    holding_horizon: str = "10 - 25 Trading Days"
    setup_checklist: List[ChecklistItem]
    ai_memo: Optional[AIThesisMemo] = None
    disclaimer: str = (
        "Educational & Analytical Research Only. Not SEBI Registered Investment Advice."
    )


class PortfolioHoldingInput(BaseModel):
    symbol: str
    exchange: str = "NSE"
    sector: str
    quantity: float
    avg_buy_price: float
    current_price: float
    active_stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    beta: float = 1.0
    below_50_dma: bool = False


class StressTestScenarioResult(BaseModel):
    scenario_id: str
    scenario_name: str
    description: str
    estimated_portfolio_impact_pct: float
    estimated_pnl_impact_inr: float
    most_vulnerable_holding: str


class HoldingDiagnosticFlag(BaseModel):
    symbol: str
    pnl_pct: float
    weight_pct: float
    status: str  # 'HEALTHY', 'THESIS_BROKEN', 'TAKE_PARTIAL_PROFIT', 'STOP_LOSS_NEAR'
    action_message: str


class PortfolioDiagnosticsReport(BaseModel):
    portfolio_name: str
    sync_source: str
    total_invested_inr: float
    current_value_inr: float
    total_pnl_inr: float
    total_pnl_pct: float
    health_score: int
    portfolio_beta: float
    total_capital_at_risk_pct: float
    sector_allocation: Dict[str, float]
    concentration_warnings: List[str]
    holding_flags: List[HoldingDiagnosticFlag]
    stress_test_scenarios: List[StressTestScenarioResult]
