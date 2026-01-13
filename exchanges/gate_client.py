"""Gate.io Futures API client."""
from typing import Dict, List, Optional, Tuple
from .base_exchange import BaseExchange


class GateClient(BaseExchange):
    """Gate.io USDT Perpetual Futures API client."""
    
    BASE_URL = "https://api.gateio.ws/api/v4"
    
    def __init__(self):
        super().__init__("Gate")
    
    async def get_all_tickers(self) -> Dict[str, float]:
        """Get all USDT futures tickers from Gate.io."""
        url = f"{self.BASE_URL}/futures/usdt/tickers"
        data = await self._get(url)
        
        if not data:
            self.logger.error("Failed to fetch Gate.io tickers")
            return {}
        
        tickers = {}
        for ticker in data:
            try:
                contract = ticker.get("contract")
                # Контракты в формате BTC_USDT
                if contract and "_USDT" in contract:
                    # Преобразуем BTC_USDT -> BTCUSDT
                    symbol = contract.replace("_", "")
                    price = float(ticker.get("last", 0))
                    if price > 0:
                        tickers[symbol] = price
            except (ValueError, KeyError) as e:
                self.logger.debug(f"Skipping invalid ticker: {e}")
                continue
        
        self.logger.info(f"Loaded {len(tickers)} Gate.io USDT futures")
        return tickers
    
    async def get_ticker(self, symbol: str) -> Optional[float]:
        """Get price for a specific symbol."""
        # Gate использует формат BTC_USDT
        gate_symbol = symbol.replace("USDT", "_USDT") if "_" not in symbol else symbol
        
        url = f"{self.BASE_URL}/futures/usdt/contracts/{gate_symbol}"
        data = await self._get(url)
        
        if data and "last_price" in data:
            try:
                return float(data["last_price"])
            except ValueError:
                pass
        
        return None
    
    async def get_all_symbols(self) -> List[str]:
        """Get list of all available symbols."""
        tickers = await self.get_all_tickers()
        return list(tickers.keys())

    async def get_orderbook_ticker(self, symbol: str) -> Optional[Tuple[float, float]]:
        """Get best bid and ask for validation."""
        # Gate format: BTC_USDT
        gate_symbol = symbol.replace("USDT", "_USDT") if "_" not in symbol else symbol
        
        url = f"{self.BASE_URL}/futures/usdt/order_book"
        params = {"contract": gate_symbol, "limit": 1}
        data = await self._get(url, params=params)
        
        if data and "bids" in data and "asks" in data:
            try:
                bids = data.get("bids", [])
                asks = data.get("asks", [])
                
                if bids and asks:
                     # Gate bids: [{"p": "...", "s": ...}, ...] OR [[p, s], ...] depending on version
                     # Most v4 docs say: {"p":"1.2", "s":100}
                     # Let's handle both just in case, or look at typical response.
                     # Docs for /futures/usdt/order_book say:
                     # "bids": [ { "p": "1.2", "s": 100 }, ... ]
                     
                    best_bid_raw = bids[0]
                    best_ask_raw = asks[0]
                    
                    if isinstance(best_bid_raw, dict):
                        best_bid = float(best_bid_raw.get("p", 0))
                    else:
                         best_bid = float(best_bid_raw[0])
                         
                    if isinstance(best_ask_raw, dict):
                        best_ask = float(best_ask_raw.get("p", 0))
                    else:
                        best_ask = float(best_ask_raw[0])
                        
                    return best_bid, best_ask
            except (ValueError, IndexError, KeyError):
                pass
        
        return None
