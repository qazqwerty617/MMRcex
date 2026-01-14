"""Telegram notifications with topic support."""
import logging
import requests
from spread_detector import SpreadOpportunity


class TelegramNotifier:
    """Simple notifications with topic/thread support."""
    
    def __init__(self, bot_token: str, chat_id: str, message_thread_id: int = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.thread_id = message_thread_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger("TG")
    
    def _send_sync(self, text: str, reply_markup: dict = None) -> bool:
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            
            # Add thread ID if specified
            if self.thread_id:
                payload["message_thread_id"] = self.thread_id

            if reply_markup:
                payload["reply_markup"] = reply_markup
            
            r = requests.post(
                f"{self.api_url}/sendMessage",
                json=payload,
                timeout=5
            )
            if r.status_code != 200:
                self.logger.error(f"Telegram Error {r.status_code}: {r.text}")
            return r.status_code == 200
        except Exception as e:
            self.logger.error(f"Send error: {e}")
            return False
    
    def get_updates(self, offset: int = None) -> list:
        try:
            params = {"timeout": 1, "allowed_updates": ["message"]}
            if offset:
                params["offset"] = offset
            
            r = requests.get(f"{self.api_url}/getUpdates", params=params, timeout=5)
            if r.status_code == 200:
                return r.json().get("result", [])
            return []
        except Exception as e:
            # Silent error for updates to avoid spamming logs
            return []

    def send_message(self, text: str, chat_id: str = None) -> bool:
        cid = chat_id if chat_id else self.chat_id
        try:
            payload = {"chat_id": cid, "text": text}
            requests.post(f"{self.api_url}/sendMessage", json=payload, timeout=5)
            return True
        except:
            return False
    
    def _fmt_price(self, price: float) -> str:
        if price >= 1000:
            return f"${price:,.0f}"
        elif price >= 1:
            return f"${price:.2f}"
        else:
            return f"${price:.4f}"
    
    def format_minimal(self, opp: SpreadOpportunity) -> str:
        """Minimal format with prices."""
        
        mp = self._fmt_price(opp.mexc_price)
        op = self._fmt_price(opp.other_price)
        
        if opp.signal == "MEXC_LONG":
            circle = "🟢"
            mexc_line = f"MEXC Long {mp}"
            other_line = f"{opp.other_exchange} Short {op}"
        else:
            circle = "🔴"
            mexc_line = f"MEXC Short {mp}"
            other_line = f"{opp.other_exchange} Long {op}"
        
        return (
            f"<b>{opp.symbol}</b>\n"
            f"{circle} {opp.spread_percent:.1f}%\n"
            f"{mexc_line}\n"
            f"{other_line}"
        )
    
    async def send_notification_with_funding(
        self, opp: SpreadOpportunity, reason: str, mexc_fr: float, other_fr: float
    ) -> bool:
        msg = self.format_minimal(opp)
        
        # Create button
        # Try to use a universal link or deep link if possible, otherwise web
        # MEXC Web: https://www.mexc.com/exchange/BTC_USDT
        symbol_fmt = opp.symbol.replace("/", "_")
        url = f"https://www.mexc.com/exchange/{symbol_fmt}"
        
        reply_markup = {
            "inline_keyboard": [[
                {"text": "Open App / Trade", "url": url}
            ]]
        }
        
        ok = self._send_sync(msg, reply_markup=reply_markup)
        if ok:
            self.logger.info(f"Sent: {opp.symbol}")
        return ok
    
    async def send_notification(self, opp: SpreadOpportunity, reason: str = "") -> bool:
        return await self.send_notification_with_funding(opp, reason, 0, 0)
    
    async def send_startup_message(self, min_spread: float, exchanges: list):
        self._send_sync(f"Bot started. Min spread: {min_spread}%")
    
    async def send_error_message(self, text: str):
        self._send_sync(f"Error: {text[:100]}")
