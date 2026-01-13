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

    async def get_orderbook_ticker(self, symbol: str) -> Optional[Tuple[float, float]]:
        """Get best bid and ask for validation."""
        # BingX format: BTC-USDT
        bingx_symbol = symbol.replace("USDT", "-USDT") if "-" not in symbol else symbol
        
        url = f"{self.BASE_URL}/swap/v2/quote/depth"
        params = {"symbol": bingx_symbol, "limit": 5}
        data = await self._get(url, params=params)
        
        # Responses logic can vary, commonly data['data']['bids']...
        # Checking docs or assuming standard structure
        if data and "data" in data:
            try:
                bids = data["data"].get("bids", [])
                asks = data["data"].get("asks", [])
                
                if bids and asks:
                    # BingX often sends [{"p": "...", "v": ...}] or [[p,v],...]
                    # Let's inspect generic handling. Standard is usually [[price, vol]]
                    # But if it returns dicts, we handle it.
                    # Based on other APIs, list of lists is most common for depth.
                    
                    best_bid_raw = bids[0]
                    best_ask_raw = asks[0]
                    
                    # Similar to Gate, safe check
                    if isinstance(best_bid_raw, dict):
                         best_bid = float(best_bid_raw.get("p", best_bid_raw.get("price", 0)))
                    else:
                         best_bid = float(best_bid_raw[0])

                    if isinstance(best_ask_raw, dict):
                         best_ask = float(best_ask_raw.get("p", best_ask_raw.get("price", 0)))
                    else:
                         best_ask = float(best_ask_raw[0])
                    
                    return best_bid, best_ask
            except (ValueError, IndexError, KeyError):
                pass
        
        return None
