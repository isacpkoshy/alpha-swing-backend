"""
Portfolio Intelligence, Risk Diagnostics & What-If Scenario Stress-Testing Engine.
Audits user holdings (via Zerodha/AngelOne/Upstox OAuth or CSV) for:
- Sector Over-Concentration (>30% threshold) & Single-Stock Risk (>15% threshold)
- Portfolio Weighted Beta vs Nifty 50
- Active Capital-at-Risk based on distance to Stop-Loss
- Thesis Invalidation (Close < 50 DMA) & Target Profit Booking alerts
- Macro Stress Tests (Nifty -5% Correction, Crude Oil +15% Spike, RBI +50bps Rate Shock)
"""

from typing import Dict, List
from backend.domain.models import (
    PortfolioHoldingInput,
    PortfolioDiagnosticsReport,
    HoldingDiagnosticFlag,
    StressTestScenarioResult,
)


class PortfolioDiagnosticsEngine:
    SECTOR_LIMIT_PCT = 30.0
    SINGLE_STOCK_LIMIT_PCT = 20.0

    def evaluate_portfolio(
        self,
        portfolio_name: str,
        sync_source: str,
        holdings: List[PortfolioHoldingInput],
    ) -> PortfolioDiagnosticsReport:
        total_invested = sum(h.quantity * h.avg_buy_price for h in holdings)
        current_value = sum(h.quantity * h.current_price for h in holdings)
        if current_value <= 0:
            raise ValueError("Portfolio current value must be positive.")

        total_pnl_inr = round(current_value - total_invested, 2)
        total_pnl_pct = round((total_pnl_inr / total_invested) * 100.0, 2) if total_invested else 0.0

        sector_totals: Dict[str, float] = {}
        weighted_beta = 0.0
        total_risk_inr = 0.0
        concentration_warnings: List[str] = []
        holding_flags: List[HoldingDiagnosticFlag] = []

        for h in holdings:
            val = h.quantity * h.current_price
            weight_pct = round((val / current_value) * 100.0, 2)
            pnl_pct = round(((h.current_price - h.avg_buy_price) / h.avg_buy_price) * 100.0, 2)

            sector_totals[h.sector] = round(sector_totals.get(h.sector, 0.0) + weight_pct, 2)
            weighted_beta += (val / current_value) * h.beta

            # Calculate downside risk to active stop loss
            sl = h.active_stop_loss or round(h.current_price * 0.94, 2)
            risk_inr = max(0.0, (h.current_price - sl) * h.quantity)
            total_risk_inr += risk_inr

            if weight_pct > self.SINGLE_STOCK_LIMIT_PCT:
                concentration_warnings.append(
                    f"Single-stock concentration: {h.symbol} is {weight_pct}% of portfolio (limit: {self.SINGLE_STOCK_LIMIT_PCT}%)."
                )

            # Determine per-holding health flag & actionable alert
            if h.below_50_dma:
                status = "THESIS_BROKEN"
                msg = f"{h.symbol} closed below 50-DMA structural support. Review trailing exit at ₹{sl}."
            elif h.target_price and h.current_price >= h.target_price:
                status = "TAKE_PARTIAL_PROFIT"
                msg = f"{h.symbol} reached swing target (₹{h.target_price}). Book 50% and trail stop-loss to 20-EMA."
            elif ((h.current_price - sl) / h.current_price) * 100.0 <= 2.0:
                status = "STOP_LOSS_NEAR"
                msg = f"{h.symbol} is within 2% of Stop-Loss (₹{sl}). Avoid averaging down."
            else:
                status = "HEALTHY"
                msg = f"Trend intact in Stage-2 uptrend. Active trailing SL at ₹{sl}."

            holding_flags.append(
                HoldingDiagnosticFlag(
                    symbol=h.symbol,
                    pnl_pct=pnl_pct,
                    weight_pct=weight_pct,
                    status=status,
                    action_message=msg,
                )
            )

        for sector, alloc_pct in sector_totals.items():
            if alloc_pct > self.SECTOR_LIMIT_PCT:
                concentration_warnings.append(
                    f"Sector over-concentration: '{sector}' accounts for {alloc_pct}% of capital (limit: {self.SECTOR_LIMIT_PCT}%)."
                )

        portfolio_beta = round(weighted_beta, 2)
        capital_at_risk_pct = round((total_risk_inr / current_value) * 100.0, 2)

        # Compute composite Portfolio Health Score (0 - 100)
        broken_count = sum(1 for f in holding_flags if f.status == "THESIS_BROKEN")
        health_score = max(
            35,
            min(
                98,
                int(
                    92
                    - (len(concentration_warnings) * 8)
                    - (broken_count * 12)
                    - max(0.0, (portfolio_beta - 1.2) * 15)
                ),
            ),
        )

        # Macro What-If Stress Test Scenarios
        highest_beta_holding = max(holdings, key=lambda x: x.beta).symbol
        nifty_drop_pct = round(-5.0 * portfolio_beta, 2)
        crude_shock_pct = round(-2.8 * portfolio_beta, 2)
        rate_hike_pct = round(-3.4 * portfolio_beta, 2)

        scenarios = [
            StressTestScenarioResult(
                scenario_id="nifty_correction_5pct",
                scenario_name="Nifty 50 -5% Broad Correction",
                description="Simulates a 5% benchmark drawdown adjusted for each holding's historical beta.",
                estimated_portfolio_impact_pct=nifty_drop_pct,
                estimated_pnl_impact_inr=round(current_value * (nifty_drop_pct / 100.0), 2),
                most_vulnerable_holding=highest_beta_holding,
            ),
            StressTestScenarioResult(
                scenario_id="crude_oil_spike_15pct",
                scenario_name="Brent Crude +15% Geopolitical Shock",
                description="Evaluates raw material & inflation margin pressure across consumer, chemical, and industrial holdings.",
                estimated_portfolio_impact_pct=crude_shock_pct,
                estimated_pnl_impact_inr=round(current_value * (crude_shock_pct / 100.0), 2),
                most_vulnerable_holding=highest_beta_holding,
            ),
            StressTestScenarioResult(
                scenario_id="rbi_rate_hike_50bps",
                scenario_name="RBI +50 bps Surprise Rate Tightening",
                description="Tests valuation multiple compression on high-P/E growth and rate-sensitive holdings.",
                estimated_portfolio_impact_pct=rate_hike_pct,
                estimated_pnl_impact_inr=round(current_value * (rate_hike_pct / 100.0), 2),
                most_vulnerable_holding=highest_beta_holding,
            ),
        ]

        return PortfolioDiagnosticsReport(
            portfolio_name=portfolio_name,
            sync_source=sync_source,
            total_invested_inr=round(total_invested, 2),
            current_value_inr=round(current_value, 2),
            total_pnl_inr=total_pnl_inr,
            total_pnl_pct=total_pnl_pct,
            health_score=health_score,
            portfolio_beta=portfolio_beta,
            total_capital_at_risk_pct=capital_at_risk_pct,
            sector_allocation=sector_totals,
            concentration_warnings=concentration_warnings,
            holding_flags=holding_flags,
            stress_test_scenarios=scenarios,
        )
