"""Spread detection with strict filters but ALL tokens."""
from typing import Dict, List, Tuple
from dataclasses import dataclass
import logging


# Черный список - проблемные токены
BLACKLIST = {
    "STRAXUSDT", "IDEXUSDT", "DGBUSDT", "SNTUSDT", "XCNUSDT",
    "VOXELUSDT", "FISUSDT", "TOKENUSDT", "OBOLUSDT", "REIUSDT",
    "SKATEUSDT", "MEGAUSDT", "MILKUSDT", "PONKEUSDT", "ORBSUSDT",
}


@dataclass
class SpreadOpportunity:
    """Spread opportunity."""
    symbol: str
    mexc_price: float
    other_exchange: str
    other_price: float
    spread_percent: float
    signal: str
    mexc_volume: float = 0.0
    other_volume: float = 0.0
    quality_score: int = 0
    
    @property
    def min_volume(self) -> float:
        return min(self.mexc_volume, self.other_volume) if self.other_volume else self.mexc_volume


class SpreadDetector:
    """Strict detector for ALL tokens."""
    
    def __init__(
        self,
        min_spread_percent: float = 10.0,
        min_volume_usdt: float = 500_000,
    ):
        self.min_spread = min_spread_percent
        self.min_volume = min_volume_usdt
        self.logger = logging.getLogger("Detector")
    
    def calculate_quality(self, spread: float, min_vol: float) -> int:
        """Quality based on volume + spread."""
        score = 0
        
        # Volume (0-50)
        if min_vol >= 10_000_000:
            score += 50
        elif min_vol >= 5_000_000:
            score += 40
        elif min_vol >= 2_000_000:
            score += 30
        elif min_vol >= 1_000_000:
            score += 20
        elif min_vol >= 500_000:
            score += 10
        
        # Spread (0-40)
        if spread >= 25:
            score += 40
        elif spread >= 20:
            score += 35
        elif spread >= 15:
            score += 25
        elif spread >= 10:
            score += 15
        
        # Bonus
        if min_vol >= 2_000_000 and spread >= 15:
            score += 10
        
        return min(100, score)
    
    def detect(
        self,
        mexc_data: Dict[str, Tuple[float, float]],
        other_data: Dict[str, Dict[str, Tuple[float, float]]]
    ) -> List[SpreadOpportunity]:
        """Detect spread opportunities with strict filtering."""
        
        opps = []
        
        for symbol, (mexc_price, mexc_vol) in mexc_data.items():
            # Skip blacklist
            if symbol in BLACKLIST:
                continue
            
            # Skip low MEXC volume
            if mexc_vol < self.min_volume:
                continue
            
            for exchange, ex_data in other_data.items():
                if symbol not in ex_data:
                    continue
                
                other_price, other_vol = ex_data[symbol]
                min_vol = min(mexc_vol, other_vol) if other_vol else mexc_vol
                
                # Skip low volume on other exchange
                if min_vol < self.min_volume:
                    continue
                
                # Calculate spread
                spread = abs(mexc_price - other_price) / min(mexc_price, other_price) * 100
                
                if spread < self.min_spread:
                    continue
                
                quality = self.calculate_quality(spread, min_vol)
                
                # Strict: require quality 40+
                if quality < 40:
                    continue
                
                signal = "MEXC_LONG" if other_price > mexc_price else "MEXC_SHORT"
                
                opps.append(SpreadOpportunity(
                    symbol=symbol,
                    mexc_price=mexc_price,
                    other_exchange=exchange,
                    other_price=other_price,
                    spread_percent=spread,
                    signal=signal,
                    mexc_volume=mexc_vol,
                    other_volume=other_vol,
                    quality_score=quality
                ))
        
        # Sort by quality
        opps.sort(key=lambda x: x.quality_score, reverse=True)
        
        self.logger.info(f"Found {len(opps)} opportunities (Q40+, $500K+)")
        return opps
