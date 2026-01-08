"""Funding rate checker for filtering fake arbitrage."""
import aiohttp
import logging
from typing import Dict, Optional

class FundingRateChecker:
    """Fetch funding rates from exchanges to filter fake arbitrage."""
    
    def __init__(self, max_funding_rate: float = 0.5):
        """
        Args:
            max_funding_rate: Maximum acceptable funding rate (%). 
                              Default 0.5% = filter out extreme funding.
        """
        self.max_rate = max_funding_rate / 100  # Convert to decimal
        self.logger = logging.getLogger("FundingRate")
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Cache funding rates (refresh every scan)
        self.binance_rates: Dict[str, float] = {}
        self.mexc_rates: Dict[str, float] = {}
    
    async def init_session(self):
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None
    
    async def fetch_binance_funding(self) -> Dict[str, float]:
        """Fetch all funding rates from Binance Futures."""
        await self.init_session()
        
        try:
            url = "https://fapi.binance.com/fapi/v1/premiumIndex"
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return {}
                
                data = await resp.json()
                rates = {}
                
                for item in data:
                    symbol = item.get("symbol", "")
                    rate = float(item.get("lastFundingRate", 0))
                    if symbol.endswith("USDT"):
                        rates[symbol] = rate
                
                self.binance_rates = rates
                self.logger.info(f"Binance funding: {len(rates)} pairs")
                return rates
                
        except Exception as e:
            self.logger.error(f"Binance funding error: {e}")
            return {}
    
    async def fetch_mexc_funding(self) -> Dict[str, float]:
        """Fetch funding rates from MEXC Futures."""
        await self.init_session()
        
        try:
            url = "https://contract.mexc.com/api/v1/contract/funding_rate"
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return {}
                
                data = await resp.json()
                if not data.get("success") or "data" not in data:
                    return {}
                
                rates = {}
                for item in data["data"]:
                    symbol = item.get("symbol", "").replace("_", "")
                    rate = float(item.get("fundingRate", 0))
                    rates[symbol] = rate
                
                self.mexc_rates = rates
                self.logger.info(f"MEXC funding: {len(rates)} pairs")
                return rates
                
        except Exception as e:
            self.logger.error(f"MEXC funding error: {e}")
            return {}
    
    async def refresh_all(self):
        """Refresh funding rates from all exchanges."""
        import asyncio
        await asyncio.gather(
            self.fetch_binance_funding(),
            self.fetch_mexc_funding(),
            return_exceptions=True
        )
    
    def get_funding_rate(self, symbol: str, exchange: str) -> Optional[float]:
        """Get funding rate for a symbol on an exchange."""
        if exchange == "Binance":
            return self.binance_rates.get(symbol)
        elif exchange == "MEXC":
            return self.mexc_rates.get(symbol)
        return None
    
    def is_funding_ok(self, symbol: str, mexc_signal: str, other_exchange: str) -> tuple[bool, str]:
        """
        Check if funding rates are acceptable for this trade.
        
        Returns:
            (is_ok, reason)
        """
        mexc_rate = self.mexc_rates.get(symbol)
        other_rate = None
        
        if other_exchange == "Binance":
            other_rate = self.binance_rates.get(symbol)
        
        # If we can't get rates, allow but warn
        if mexc_rate is None and other_rate is None:
            return True, "NO_DATA"
        
        # Check extreme funding
        rates_to_check = []
        if mexc_rate is not None:
            rates_to_check.append(("MEXC", mexc_rate))
        if other_rate is not None:
            rates_to_check.append((other_exchange, other_rate))
        
        for ex, rate in rates_to_check:
            if abs(rate) > self.max_rate:
                return False, f"{ex} funding {rate*100:.3f}% too high"
        
        # Check if funding works against our position
        # If MEXC Long and MEXC funding is very negative = bad
        # If MEXC Short and MEXC funding is very positive = bad
        if mexc_rate is not None:
            if mexc_signal == "MEXC_LONG" and mexc_rate < -self.max_rate:
                return False, f"MEXC funding {mexc_rate*100:.3f}% against long"
            if mexc_signal == "MEXC_SHORT" and mexc_rate > self.max_rate:
                return False, f"MEXC funding {mexc_rate*100:.3f}% against short"
        
        return True, "OK"
    
    def get_combined_funding_cost(self, symbol: str, other_exchange: str) -> Optional[float]:
        """
        Calculate combined funding cost per 8 hours.
        Returns percentage cost (negative = you pay, positive = you receive).
        """
        mexc_rate = self.mexc_rates.get(symbol, 0)
        other_rate = 0
        
        if other_exchange == "Binance":
            other_rate = self.binance_rates.get(symbol, 0)
        
        # For hedged position, you pay/receive on both sides
        # Net cost depends on position direction, simplified here
        return (abs(mexc_rate) + abs(other_rate)) * 100  # Return as percentage
