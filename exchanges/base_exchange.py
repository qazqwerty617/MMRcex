"""Base class for all exchange clients."""
import logging
from typing import Dict, List, Optional
import aiohttp
import asyncio


class BaseExchange:
    """Base class for exchange API clients."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"Exchange.{name}")
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def init_session(self):
        """Initialize aiohttp session."""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close_session(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _get(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make GET request with error handling."""
        try:
            await self.init_session()
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    self.logger.error(f"HTTP {response.status} for {url}")
                    return None
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout for {url}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return None
    
    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol format from MEXC to exchange-specific format.
        Override in child classes if needed.
        """
        return symbol
    
    async def get_ticker(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol.
        Must be implemented by child classes.
        """
        raise NotImplementedError("get_ticker must be implemented by child class")
    
    async def get_all_symbols(self) -> List[str]:
        """
        Get list of all available symbols.
        Must be implemented by child classes.
        """
        raise NotImplementedError("get_all_symbols must be implemented by child class")
    
    async def get_all_tickers(self) -> Dict[str, float]:
        """
        Get all tickers at once (more efficient than individual calls).
        Must be implemented by child classes.
        """
        raise NotImplementedError("get_all_tickers must be implemented by child class")

    async def get_orderbook_ticker(self, symbol: str) -> Optional[tuple[float, float]]:
        """
        Get best bid and best ask for validation.
        Returns: (best_bid, best_ask) or None
        """
        raise NotImplementedError("get_orderbook_ticker must be implemented by child class")
