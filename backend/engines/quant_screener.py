"""
Deterministic Swing & Positional Quant Screener Engine.
Evaluates multi-factor technical + institutional delivery + fundamental criteria
and generates structured Actionable Trade Setup Cards (Entry Zone, ATR Stop-Loss, Targets 1/2/3, R:R).
"""

from datetime import datetime
from typing import List, Optional
import uuid

from backend.adapters.market_data.base import MarketDataProvider
from backend.domain.models import (
    Instrument,
    TradeSetupCard,
    ChecklistItem,
    Timeframe,
    TradeDirection,
    SetupStatus,
)


class QuantScreenerEngine:
    """
    Generates non-generic, high-conviction Swing Setup Cards with strict risk management:
    - Entry Zone: Current breakout pivot to +1.2% max chase limit
    - Stop-Loss: Trigger - 1.5 * ATR_14
    - Target 1: 1.5x Risk (Partial profit lock-in)
    - Target 2: 2.5x Risk (Core swing target)
    - Target 3: 4.0x Risk (Trailing positional runner above 20 EMA)
    """

    def __init__(self, provider: MarketDataProvider):
        self.provider = provider

    async def build_setup_card_for_instrument(
        self,
        inst: Instrument,
        exchange_id: str = "NSE",
        atr_multiplier: float = 1.5,
        min_delivery_pct: float = 50.0,
    ) -> Optional[TradeSetupCard]:
        bars = await self.provider.fetch_ohlcv(inst.symbol, exchange_id, Timeframe.D1, 50)
        fundamentals = await self.provider.fetch_fundamentals(inst.symbol, exchange_id)
        if not bars:
            return None

        latest = bars[-1]
        strat_slug = latest.custom_indicators.get("strategy_slug", "vcp-delivery-breakout")
        strat_name = latest.custom_indicators.get("strategy_name", "VCP + Delivery Breakout")

        close = latest.close
        atr = latest.atr_14 or (close * 0.025)

        trigger_price = round(close, 2)
        entry_min = round(close * 0.996, 2)
        entry_max = round(close * 1.012, 2)

        risk_per_share = round(max(0.05, atr_multiplier * atr), 2)
        stop_loss_price = round(trigger_price - risk_per_share, 2)
        stop_loss_pct = round((risk_per_share / trigger_price) * 100.0, 2)

        target_1 = round(trigger_price + (1.5 * risk_per_share), 2)
        target_2 = round(trigger_price + (2.5 * risk_per_share), 2)
        target_3 = round(trigger_price + (4.0 * risk_per_share), 2)
        rr_ratio = round(2.5 / (atr_multiplier / 1.5), 2)

        stage_2_aligned = bool(
            latest.ema_20
            and latest.sma_50
            and latest.sma_200
            and close > latest.ema_20 > latest.sma_50 > latest.sma_200
        )
        delivery_spike = (latest.delivery_percentage or 0.0) >= min_delivery_pct
        earnings_momentum = fundamentals.profit_growth_yoy >= 15.0 and fundamentals.roe_pct >= 15.0

        checklist = [
            ChecklistItem(
                rule="Stage-2 MA Ribbon Alignment (Price > 20EMA > 50SMA > 200SMA)",
                passed=stage_2_aligned,
                detail=f"20EMA: ₹{latest.ema_20} | 50SMA: ₹{latest.sma_50} | 200SMA: ₹{latest.sma_200}",
            ),
            ChecklistItem(
                rule=f"Institutional NSE Delivery Accumulation (>{min_delivery_pct:.0f}%)",
                passed=delivery_spike,
                detail=f"NSE Delivery: {latest.delivery_percentage}% ({latest.rel_volume_20d}x 20D Avg Vol)",
            ),
            ChecklistItem(
                rule="Earnings & Return Ratio Quality (YoY Profit >15%, ROE >15%)",
                passed=earnings_momentum,
                detail=f"YoY PAT Growth: +{fundamentals.profit_growth_yoy}% | ROE: {fundamentals.roe_pct}%",
            ),
            ChecklistItem(
                rule="Zero Promoter Pledge & Clean Balance Sheet",
                passed=fundamentals.promoter_pledge_pct == 0.0,
                detail=f"Promoter Pledge: {fundamentals.promoter_pledge_pct}% | D/E: {fundamentals.debt_to_equity}",
            ),
        ]

        passed_count = sum(1 for item in checklist if item.passed)
        quant_score = round(
            min(98.0, 68.0 + (passed_count * 6.5) + ((latest.rel_volume_20d or 1.0) * 2.0)),
            1,
        )

        return TradeSetupCard(
            setup_id=f"SETUP-{inst.symbol}-{uuid.uuid4().hex[:6].upper()}",
            symbol=inst.symbol,
            company_name=inst.name,
            exchange=inst.exchange_id,
            sector=inst.sector,
            strategy_slug=strat_slug,
            strategy_name=strat_name,
            timeframe=Timeframe.D1,
            direction=TradeDirection.LONG,
            status=SetupStatus.ACTIVE,
            detected_at=datetime.now(),
            current_price=close,
            trigger_price=trigger_price,
            entry_zone_min=entry_min,
            entry_zone_max=entry_max,
            stop_loss_price=stop_loss_price,
            stop_loss_pct=stop_loss_pct,
            target_1_price=target_1,
            target_2_price=target_2,
            target_3_price=target_3,
            risk_reward_ratio=rr_ratio,
            quant_conviction_score=quant_score,
            delivery_pct=latest.delivery_percentage or 0.0,
            rel_volume_20d=latest.rel_volume_20d or 1.0,
            setup_checklist=checklist,
        )

    async def scan_universe(
        self,
        exchange_id: str = "NSE",
        strategy_filter: Optional[str] = None,
        min_rr: float = 1.5,
        atr_multiplier: float = 1.5,
        min_delivery_pct: float = 0.0,
        min_rel_vol: float = 0.0,
    ) -> List[TradeSetupCard]:
        instruments = await self.provider.list_active_instruments(exchange_id)
        setup_cards: List[TradeSetupCard] = []

        for inst in instruments:
            card = await self.build_setup_card_for_instrument(
                inst,
                exchange_id,
                atr_multiplier=atr_multiplier,
                min_delivery_pct=max(50.0, min_delivery_pct),
            )
            if not card:
                continue
            if strategy_filter and strategy_filter != "ALL" and card.strategy_slug != strategy_filter:
                continue
            if card.risk_reward_ratio < min_rr:
                continue
            if card.delivery_pct < min_delivery_pct:
                continue
            if card.rel_volume_20d < min_rel_vol:
                continue
            setup_cards.append(card)

        return sorted(setup_cards, key=lambda c: c.quant_conviction_score, reverse=True)
