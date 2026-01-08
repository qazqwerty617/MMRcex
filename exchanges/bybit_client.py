"""Bybit Futures API client."""
from typing import Dict, List, Optional
from .base_exchange import BaseExchange


class BybitClient(BaseExchange):
    """Bybit Linear Perpetual Futures API client."""
    
    BASE_URL = "https://api.bybit.com/v5"
    
    def __init__(self):
        super().__init__("Bybit")
    
    async def get_all_tickers(self) -> Dict[str, float]:
        """Get all linear futures tickers from Bybit."""
        url = f"{self.BASE_URL}/market/tickers"
        params = {"category": "linear"}  # USDT perpetual
        data = await self._get(url, params=params)
        
        if not data or "result" not in data or "list" not in data["result"]:
            self.logger.error("Failed to fetch Bybit tickers")
            return {}
        
        tickers = {}
        for ticker in data["result"]["list"]:
            try:
                symbol = ticker.get("symbol")
                # Только USDT perpetual
                if symbol and symbol.endswith("USDT"):
                    price = float(ticker.get("lastPrice", 0))
                    if price > 0:
                        tickers[symbol] = price
            except (ValueError, KeyError) as e:
                self.logger.debug(f"Skipping invalid ticker: {e}")
                continue
        
        self.logger.info(f"Loaded {len(tickers)} Bybit linear futures")
        return tickers
    
    async def get_ticker(self, symbol: str) -> Optional[float]:
        """Get price for a specific symbol."""
        url = f"{self.BASE_URL}/market/tickers"
        params = {"category": "linear", "symbol": symbol}
        data = await self._get(url, params=params)
        
        if data and "result" in data and "list" in data["result"]:
            try:
                return float(data["result"]["list"][0].get("lastPrice", 0))
            except (ValueError, KeyError, IndexError):
                pass
        
        return None
    
    async def get_all_symbols(self) -> List[str]:
        """Get list of all available symbols."""
        tickers = await self.get_all_tickers()
        return list(tickers.keys())
