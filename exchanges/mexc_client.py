"""MEXC Futures API client with volume data."""
from typing import Dict, List, Optional, Tuple
from .base_exchange import BaseExchange


class MEXCClient(BaseExchange):
    """MEXC Futures API client for perpetual contracts with volume."""
    
    BASE_URL = "https://contract.mexc.com/api/v1"
    
    def __init__(self):
        super().__init__("MEXC")
    
    async def get_all_tickers_with_volume(self) -> Dict[str, Tuple[float, float]]:
        """
        Get all perpetual futures tickers with volume from MEXC.
        Returns: {symbol: (price, volume_24h_usdt)}
        """
        url = f"{self.BASE_URL}/contract/ticker"
        data = await self._get(url)
        
        if not data or "data" not in data:
            self.logger.error("Failed to fetch MEXC tickers")
            return {}
        
        tickers = {}
        for ticker in data["data"]:
            try:
                symbol = ticker.get("symbol")
                # Только USDT perpetual контракты
                if symbol and "_USDT" in symbol:
                    # Преобразуем BTC_USDT -> BTCUSDT
                    normalized = symbol.replace("_", "")
                    last_price = float(ticker.get("lastPrice", 0))
                    
                    # Объём в USDT за 24h
                    volume_24h = float(ticker.get("volume24", 0))
                    
                    if last_price > 0:
                        tickers[normalized] = (last_price, volume_24h)
            except (ValueError, KeyError) as e:
                self.logger.debug(f"Skipping invalid ticker: {e}")
                continue
        
        self.logger.info(f"Loaded {len(tickers)} MEXC futures contracts")
        return tickers
    
    async def get_all_tickers(self) -> Dict[str, float]:
        """Get all perpetual futures tickers from MEXC (price only)."""
        tickers_with_vol = await self.get_all_tickers_with_volume()
        return {symbol: price for symbol, (price, _) in tickers_with_vol.items()}
    
    async def get_ticker(self, symbol: str) -> Optional[float]:
        """Get price for a specific symbol."""
        # Для MEXC нужен формат BTC_USDT
        mexc_symbol = symbol.replace("USDT", "_USDT") if "_" not in symbol else symbol
        
        url = f"{self.BASE_URL}/contract/ticker"
        data = await self._get(url, params={"symbol": mexc_symbol})
        
        if data and "data" in data and len(data["data"]) > 0:
            try:
                return float(data["data"][0].get("lastPrice", 0))
            except (ValueError, KeyError, IndexError):
                pass
        
        return None
    
    async def get_all_symbols(self) -> List[str]:
        """Get list of all available symbols."""
        tickers = await self.get_all_tickers()
        return list(tickers.keys())

    async def get_orderbook_ticker(self, symbol: str) -> Optional[Tuple[float, float]]:
        """Get best bid and ask from orderbook."""
        # MEXC symbol format: BTC_USDT
        mexc_symbol = symbol.replace("USDT", "_USDT") if "_" not in symbol else symbol
        
        # Limit 5 is enough for best bid/ask
        url = f"{self.BASE_URL}/contract/depth/{mexc_symbol}"
        data = await self._get(url, params={"limit": 5})
        
        if data and "data" in data:
            try:
                bids = data["data"].get("bids", [])
                asks = data["data"].get("asks", [])
                
                if bids and asks:
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    return best_bid, best_ask
            except (ValueError, IndexError, KeyError):
                pass
        
        return None
