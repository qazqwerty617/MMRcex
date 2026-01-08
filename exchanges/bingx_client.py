"""BingX Futures API client."""
from typing import Dict, List, Optional
from .base_exchange import BaseExchange


class BingXClient(BaseExchange):
    """BingX Perpetual Futures API client."""
    
    BASE_URL = "https://open-api.bingx.com/openApi"
    
    def __init__(self):
        super().__init__("BingX")
    
    async def get_all_tickers(self) -> Dict[str, float]:
        """Get all perpetual futures tickers from BingX."""
        url = f"{self.BASE_URL}/swap/v2/quote/ticker"
        data = await self._get(url)
        
        if not data or "data" not in data:
            self.logger.error("Failed to fetch BingX tickers")
            return {}
        
        tickers = {}
        for ticker in data["data"]:
            try:
                symbol = ticker.get("symbol")
                # Формат: BTC-USDT, нас интересуют USDT пары
                if symbol and "-USDT" in symbol:
                    # Преобразуем BTC-USDT -> BTCUSDT
                    normalized = symbol.replace("-", "")
                    price = float(ticker.get("lastPrice", 0))
                    if price > 0:
                        tickers[normalized] = price
            except (ValueError, KeyError) as e:
                self.logger.debug(f"Skipping invalid ticker: {e}")
                continue
        
        self.logger.info(f"Loaded {len(tickers)} BingX perpetual futures")
        return tickers
    
    async def get_ticker(self, symbol: str) -> Optional[float]:
        """Get price for a specific symbol."""
        # BingX использует формат BTC-USDT
        bingx_symbol = symbol.replace("USDT", "-USDT") if "-" not in symbol else symbol
        
        url = f"{self.BASE_URL}/swap/v2/quote/ticker"
        params = {"symbol": bingx_symbol}
        data = await self._get(url, params=params)
        
        if data and "data" in data and "lastPrice" in data["data"]:
            try:
                return float(data["data"]["lastPrice"])
            except ValueError:
                pass
        
        return None
    
    async def get_all_symbols(self) -> List[str]:
        """Get list of all available symbols."""
        tickers = await self.get_all_tickers()
        return list(tickers.keys())
