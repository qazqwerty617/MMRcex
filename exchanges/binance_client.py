"""Binance Futures API client with volume data."""
from typing import Dict, List, Optional, Tuple
from .base_exchange import BaseExchange


class BinanceClient(BaseExchange):
    """Binance USDT-M Futures API client with volume."""
    
    BASE_URL = "https://fapi.binance.com/fapi/v1"
    
    def __init__(self):
        super().__init__("Binance")
    
    async def get_all_tickers_with_volume(self) -> Dict[str, Tuple[float, float]]:
        """
        Get all futures tickers with 24h volume from Binance.
        Returns: {symbol: (price, volume_24h_usdt)}
        """
        url = f"{self.BASE_URL}/ticker/24hr"
        data = await self._get(url)
        
        if not data:
            self.logger.error("Failed to fetch Binance tickers")
            return {}
        
        tickers = {}
        for ticker in data:
            try:
                symbol = ticker.get("symbol")
                # Только USDT perpetual
                if symbol and symbol.endswith("USDT"):
                    price = float(ticker.get("lastPrice", 0))
                    # quoteVolume = объём в USDT
                    volume = float(ticker.get("quoteVolume", 0))
                    
                    if price > 0:
                        tickers[symbol] = (price, volume)
            except (ValueError, KeyError) as e:
                self.logger.debug(f"Skipping invalid ticker: {e}")
                continue
        
        self.logger.info(f"Loaded {len(tickers)} Binance futures")
        return tickers
    
    async def get_all_tickers(self) -> Dict[str, float]:
        """Get all futures tickers from Binance (price only)."""
        tickers_with_vol = await self.get_all_tickers_with_volume()
        return {symbol: price for symbol, (price, _) in tickers_with_vol.items()}
    
    async def get_ticker(self, symbol: str) -> Optional[float]:
        """Get price for a specific symbol."""
        url = f"{self.BASE_URL}/ticker/price"
        data = await self._get(url, params={"symbol": symbol})
        
        if data and "price" in data:
            try:
                return float(data["price"])
            except ValueError:
                pass
        
        return None
    
    async def get_all_symbols(self) -> List[str]:
        """Get list of all available symbols."""
        tickers = await self.get_all_tickers()
        return list(tickers.keys())

    async def get_orderbook_ticker(self, symbol: str) -> Optional[Tuple[float, float]]:
        """Get best bid and ask for validation."""
        url = f"{self.BASE_URL}/ticker/bookTicker"
        data = await self._get(url, params={"symbol": symbol})
        
        if data and "bidPrice" in data and "askPrice" in data:
            try:
                best_bid = float(data["bidPrice"])
                best_ask = float(data["askPrice"])
                
                if best_bid > 0 and best_ask > 0:
                    return best_bid, best_ask
            except ValueError:
                pass
        
        return None
