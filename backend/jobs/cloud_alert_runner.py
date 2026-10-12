"""
Standalone Cloud Cron Job (`US-B9` & `US-B6`) executed by GitHub Actions during NSE market hours
even when the user's laptop is completely turned OFF.
1. Optionally pings `CLOUD_BACKEND_URL` (Render / HuggingFace Spaces) so the 24/7 cloud API stays warm
2. Evaluates all active NSE Breakout & Stop-Loss alerts in `config/active_alerts.json`
3. Dispatches instant Telegram notifications via `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import httpx
from backend.adapters.market_data.base import DataProviderRegistry
import backend.adapters.market_data.free_nse_adapter  # Registers 'free_nse'
from backend.engines.alert_engine import TelegramAlertEngine


async def main() -> None:
    cloud_url = os.getenv("CLOUD_BACKEND_URL", "").strip().rstrip("/")
    if cloud_url:
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(f"{cloud_url}/api/v1/health")
                print(f"[Keep-Alive Ping] {cloud_url}/api/v1/health -> HTTP {r.status_code}")
        except Exception as exc:
            print(f"[Keep-Alive Ping Warning] {exc}")

    provider = DataProviderRegistry.get_provider("free_nse")
    if hasattr(provider, "sync_live_universe_parallel"):
        sync_stats = provider.sync_live_universe_parallel(exchange_id="NSE")
        print(f"[Parallel NSE Sync] {sync_stats}")

    engine = TelegramAlertEngine()
    summary = await engine.evaluate_active_alerts(provider)
    print(
        f"[Cloud Alert Evaluation] Evaluated={summary['evaluated_count']} | "
        f"Triggered={summary['triggered_count']}"
    )
    for ev in summary["triggered_events"]:
        print(f"  -> TRIGGERED: {ev['symbol']} @ ₹{ev['ltp']} ({ev['alert_type']}) | TG={ev['telegram_status']['mode']}")


if __name__ == "__main__":
    asyncio.run(main())
