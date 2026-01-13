"""KuCoin Futures API client - Fixed version."""
from typing import Dict, List, Optional
from .base_exchange import BaseExchange


class KuCoinClient(BaseExchange):
    """KuCoin USDT Perpetual Futures API client."""
    
    BASE_URL = "https://api-futures.kucoin.com/api/v1"
    
    def __init__(self):
        super().__init__("KuCoin")
    
    async def get_all_tickers(self) -> Dict[str, float]:
        """Get all futures tickers from KuCoin."""
        # Сначала получаем список всех контрактов
        contracts_url = f"{self.BASE_URL}/contracts/active"
        contracts_data = await self._get(contracts_url)
        
        if not contracts_data or "data" not in contracts_data:
            self.logger.error("Failed to fetch KuCoin contracts list")
            return {}
        
        tickers = {}
        
        # Для каждого USDT контракта получаем цену
        for contract in contracts_data["data"]:
            try:
                symbol = contract.get("symbol")
                # Только USDT контракты (формат: XBTUSDTM)
                if not symbol or "USDT" not in symbol:
                    continue
                
                # Получаем последнюю цену из markPrice
                mark_price = contract.get("markPrice")
                if mark_price:
                    price = float(mark_price)
                    if price > 0:
                        # Нормализуем символ: XBTUSDTM -> BTCUSDT
                        normalized = self._normalize_symbol(symbol)
                        if normalized:
                            tickers[normalized] = price
            except (ValueError, KeyError) as e:
                self.logger.debug(f"Skipping contract: {e}")
                continue
        
        self.logger.info(f"Loaded {len(tickers)} KuCoin futures")
        return tickers
    
    def _normalize_symbol(self, symbol: str) -> Optional[str]:
        """
        Normalize KuCoin symbol to standard format.
        XBTUSDTM -> BTCUSDT
        ETHUSDTM -> ETHUSDT
        """
        if not symbol or "USDT" not in symbol:
            return None
        
        # Убираем суффикс M
        clean = symbol
        if clean.endswith("M"):
            clean = clean[:-1]
        
        # Специальные преобразования
        replacements = {
            "XBT": "BTC",  # KuCoin использует XBT вместо BTC
        }
        
        for old, new in replacements.items():
            if clean.startswith(old):
                clean = new + clean[len(old):]
        
        return clean
    
    async def get_ticker(self, symbol: str) -> Optional[float]:
        """Get price for a specific symbol."""
        # Преобразуем обратно в формат KuCoin
        kucoin_symbol = symbol
        if symbol.startswith("BTC"):
            kucoin_symbol = "XBT" + symbol[3:]
        if not kucoin_symbol.endswith("M"):
            kucoin_symbol += "M"
        
        url = f"{self.BASE_URL}/ticker"
        params = {"symbol": kucoin_symbol}
        data = await self._get(url, params=params)
        
        if data and "data" in data and "price" in data["data"]:
            try:
                return float(data["data"]["price"])
            except ValueError:
                pass
        
        return None
    
    async def get_all_symbols(self) -> List[str]:
        """Get list of all available symbols."""
        tickers = await self.get_all_tickers()
        return list(tickers.keys())

    async def get_orderbook_ticker(self, symbol: str) -> Optional[Tuple[float, float]]:
        """Get best bid and ask for validation."""
        # KuCoin format: XBTUSDTM
        kucoin_symbol = symbol
        if symbol.startswith("BTC"):
            kucoin_symbol = "XBT" + symbol[3:]
        if not kucoin_symbol.endswith("M"):
            kucoin_symbol += "M"
            
        url = f"{self.BASE_URL}/level1/depth"
        params = {"symbol": kucoin_symbol}
        data = await self._get(url, params=params)
        
        if data and "data" in data:
            try:
                d = data["data"]
                best_bid = float(d.get("bestBidPrice", 0))
                best_ask = float(d.get("bestAskPrice", 0))
                
                if best_bid > 0 and best_ask > 0:
                    return best_bid, best_ask
            except (ValueError, KeyError):
                pass
        
        return None
