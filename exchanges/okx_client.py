"""OKX Futures API client."""
from typing import Dict, List, Optional, Tuple
from .base_exchange import BaseExchange


class OKXClient(BaseExchange):
    """OKX Perpetual Swap API client."""
    
    BASE_URL = "https://www.okx.com/api/v5"
    
    def __init__(self):
        super().__init__("OKX")
    
    async def get_all_tickers(self) -> Dict[str, float]:
        """Get all perpetual swap tickers from OKX."""
        url = f"{self.BASE_URL}/market/tickers"
        params = {"instType": "SWAP"}  # Perpetual swaps
        data = await self._get(url, params=params)
        
        if not data or "data" not in data:
            self.logger.error("Failed to fetch OKX tickers")
            return {}
        
        tickers = {}
        for ticker in data["data"]:
            try:
                inst_id = ticker.get("instId")
                # Формат: BTC-USDT-SWAP, нас интересуют только USDT
                if inst_id and "-USDT-SWAP" in inst_id:
                    # Преобразуем BTC-USDT-SWAP -> BTCUSDT
                    symbol = inst_id.replace("-USDT-SWAP", "USDT")
                    price = float(ticker.get("last", 0))
                    if price > 0:
                        tickers[symbol] = price
            except (ValueError, KeyError) as e:
                self.logger.debug(f"Skipping invalid ticker: {e}")
                continue
        
        self.logger.info(f"Loaded {len(tickers)} OKX perpetual swaps")
        return tickers
    
    async def get_ticker(self, symbol: str) -> Optional[float]:
        """Get price for a specific symbol."""
        # OKX использует формат BTC-USDT-SWAP
        okx_symbol = symbol.replace("USDT", "-USDT-SWAP")
        
        url = f"{self.BASE_URL}/market/ticker"
        params = {"instId": okx_symbol}
        data = await self._get(url, params=params)
        
        if data and "data" in data and len(data["data"]) > 0:
            try:
                return float(data["data"][0].get("last", 0))
            except (ValueError, KeyError, IndexError):
                pass
        
        return None
    
    async def get_all_symbols(self) -> List[str]:
        """Get list of all available symbols."""
        tickers = await self.get_all_tickers()
        return list(tickers.keys())

    async def get_orderbook_ticker(self, symbol: str) -> Optional[Tuple[float, float]]:
        """Get best bid and ask for validation."""
        # OKX format: BTC-USDT-SWAP
        okx_symbol = symbol.replace("USDT", "-USDT-SWAP")
        
        url = f"{self.BASE_URL}/market/books"
        params = {"instId": okx_symbol, "sz": 1}
        data = await self._get(url, params=params)
        
        if data and "data" in data and len(data["data"]) > 0:
            try:
                book = data["data"][0]
                bids = book.get("bids", [])
                asks = book.get("asks", [])
                
                if bids and asks:
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    return best_bid, best_ask
            except (ValueError, IndexError, KeyError):
                pass
        
        return None
