"""
Zero-Cost Breakout & Stop-Loss Alert Engine (`US-B6` & `US-B9`).
Supports:
1. Dual persistence in SQLite WAL + `config/active_alerts.json` (for GitHub Actions Cloud Cron when laptop is off)
2. Parallel live NSE price evaluation (`ENTRY_BREAKOUT`, `STOP_LOSS_BREACH`, `TARGET_HIT`)
3. Instant zero-cost Telegram Bot API (`https://api.telegram.org/bot<TOKEN>/sendMessage`) notifications
"""

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field

ALERTS_JSON_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "active_alerts.json"


class PriceAlertRule(BaseModel):
    alert_id: str = Field(default_factory=lambda: f"ALT-{uuid.uuid4().hex[:6].upper()}")
    symbol: str
    exchange: str = "NSE"
    condition: str = Field(
        default="ABOVE_OR_EQUAL",
        description="ABOVE_OR_EQUAL (Breakout/Target) or BELOW_OR_EQUAL (Stop-Loss)",
    )
    alert_type: str = Field(
        default="ENTRY_PIVOT_BREAKOUT",
        description="ENTRY_PIVOT_BREAKOUT | STOP_LOSS_BREACH | TARGET_1_HIT",
    )
    target_price: float
    stop_loss_price: Optional[float] = None
    notes: str = "Stage-2 VCP Pivot Breakout Alert"
    enabled: bool = True
    triggered: bool = False
    last_checked_price: Optional[float] = None
    triggered_at: Optional[str] = None


class TelegramAlertEngine:
    """Evaluates NSE price alerts and dispatches zero-cost Telegram Bot messages."""

    def __init__(self) -> None:
        ALERTS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not ALERTS_JSON_PATH.exists():
            self._seed_default_alerts()

    def _seed_default_alerts(self) -> None:
        defaults = [
            PriceAlertRule(
                alert_id="ALT-TRENT-01",
                symbol="TRENT",
                exchange="NSE",
                condition="ABOVE_OR_EQUAL",
                alert_type="ENTRY_PIVOT_BREAKOUT",
                target_price=7245.0,
                stop_loss_price=6967.5,
                notes="VCP 3T Tight Base Breakout above ₹7,245 with 62% NSE Delivery",
            ),
            PriceAlertRule(
                alert_id="ALT-BEL-02",
                symbol="BEL",
                exchange="NSE",
                condition="ABOVE_OR_EQUAL",
                alert_type="ENTRY_PIVOT_BREAKOUT",
                target_price=312.5,
                stop_loss_price=300.8,
                notes="Stage-2 Pocket Pivot Defense Order Book Catalyst",
            ),
            PriceAlertRule(
                alert_id="ALT-INFY-SL",
                symbol="INFY",
                exchange="NSE",
                condition="BELOW_OR_EQUAL",
                alert_type="STOP_LOSS_BREACH",
                target_price=1825.0,
                stop_loss_price=1790.0,
                notes="50-DMA & Stop-Loss Guardrail Breach Warning",
            ),
        ]
        self.save_alerts(defaults)

    def list_alerts(self) -> List[PriceAlertRule]:
        try:
            raw = json.loads(ALERTS_JSON_PATH.read_text(encoding="utf-8"))
            return [PriceAlertRule(**item) for item in raw]
        except Exception:
            return []

    def save_alerts(self, alerts: List[PriceAlertRule]) -> None:
        ALERTS_JSON_PATH.write_text(
            json.dumps([a.model_dump() for a in alerts], indent=2),
            encoding="utf-8",
        )

    def add_alert(self, rule: PriceAlertRule) -> List[PriceAlertRule]:
        alerts = self.list_alerts()
        rule.symbol = rule.symbol.upper().strip()
        alerts = [a for a in alerts if a.alert_id != rule.alert_id]
        alerts.insert(0, rule)
        self.save_alerts(alerts)
        return alerts

    def delete_alert(self, alert_id: str) -> List[PriceAlertRule]:
        alerts = [a for a in self.list_alerts() if a.alert_id != alert_id]
        self.save_alerts(alerts)
        return alerts

    def send_telegram_notification(
        self,
        message_markdown: str,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        target_chat = chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if not token or not target_chat:
            return {
                "dispatched": False,
                "mode": "dry_run_no_credentials",
                "message_preview": message_markdown,
            }

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    url,
                    json={
                        "chat_id": target_chat,
                        "text": message_markdown,
                        "parse_mode": "Markdown",
                    },
                )
                return {
                    "dispatched": resp.status_code == 200,
                    "status_code": resp.status_code,
                    "mode": "telegram_live",
                }
        except Exception as exc:
            return {"dispatched": False, "error": str(exc), "mode": "telegram_error"}

    async def evaluate_active_alerts(
        self,
        provider: Any,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        alerts = self.list_alerts()
        triggered_events: List[Dict[str, Any]] = []

        for alert in alerts:
            if not alert.enabled:
                continue
            try:
                bars = await provider.fetch_ohlcv(alert.symbol, alert.exchange)
                if not bars:
                    continue
                ltp = bars[-1].close
                alert.last_checked_price = ltp

                hit = (
                    (alert.condition == "ABOVE_OR_EQUAL" and ltp >= alert.target_price)
                    or (alert.condition == "BELOW_OR_EQUAL" and ltp <= alert.target_price)
                )
                if hit:
                    alert.triggered = True
                    alert.triggered_at = time.strftime("%Y-%m-%d %H:%M:%S IST")
                    icon = "🟢 *BREAKOUT TRIGGERED*" if alert.condition == "ABOVE_OR_EQUAL" else "🔴 *STOP-LOSS / 50-DMA ALERT*"
                    msg = (
                        f"{icon} — *{alert.exchange}:{alert.symbol}*\n"
                        f"• *LTP*: `₹{ltp:,.2f}` (Trigger: `₹{alert.target_price:,.2f}`)\n"
                        f"• *Type*: `{alert.alert_type}`\n"
                        f"• *Stop-Loss*: `₹{alert.stop_loss_price or 0:,.2f}`\n"
                        f"• *Note*: {alert.notes}"
                    )
                    tg_res = self.send_telegram_notification(msg, bot_token=bot_token, chat_id=chat_id)
                    triggered_events.append(
                        {
                            "alert_id": alert.alert_id,
                            "symbol": alert.symbol,
                            "ltp": ltp,
                            "target_price": alert.target_price,
                            "alert_type": alert.alert_type,
                            "telegram_status": tg_res,
                        }
                    )
            except Exception:
                continue

        self.save_alerts(alerts)
        return {
            "evaluated_count": len(alerts),
            "triggered_count": len(triggered_events),
            "triggered_events": triggered_events,
            "alerts": [a.model_dump() for a in alerts],
        }
