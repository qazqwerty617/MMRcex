"""Advanced signal generation with smart cooldown based on spread changes."""
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from spread_detector import SpreadOpportunity


@dataclass
class SpreadHistory:
    """Tracks spread history for a symbol-exchange pair."""
    symbol: str
    exchange: str
    last_spread: float
    last_notification_time: datetime
    last_notification_spread: float
    notification_count: int = 0


class SmartSignalGenerator:
    """
    Advanced signal generator with intelligent cooldown.
    
    Features:
    - Tracks spread changes over time
    - Only notifies when spread changes by min_change_percent
    - Implements time-based cooldown as backup
    - Detects new spreads vs existing spread changes
    - Priority system for larger spreads
    """
    
    def __init__(
        self,
        min_spread_change_percent: float = 5.0,
        min_cooldown_minutes: int = 3,
        max_cooldown_minutes: int = 30
    ):
        """
        Args:
            min_spread_change_percent: Min % change in spread to trigger re-notification
            min_cooldown_minutes: Minimum time between notifications for same pair
            max_cooldown_minutes: Maximum time after which we forcefully re-notify
        """
        self.min_spread_change = min_spread_change_percent
        self.min_cooldown = timedelta(minutes=min_cooldown_minutes)
        self.max_cooldown = timedelta(minutes=max_cooldown_minutes)
        
        # Трекинг истории спредов: {symbol_exchange: SpreadHistory}
        self.spread_history: Dict[str, SpreadHistory] = {}
        self.logger = logging.getLogger("SmartSignalGenerator")
    
    def _get_key(self, symbol: str, exchange: str) -> str:
        """Generate unique key for symbol-exchange pair."""
        return f"{symbol}_{exchange}"
    
    def _calculate_spread_change(self, old_spread: float, new_spread: float) -> float:
        """Calculate absolute change in spread percentage."""
        return abs(new_spread - old_spread)
    
    def should_notify(self, opportunity: SpreadOpportunity) -> tuple[bool, str]:
        """
        Determine if we should send notification for this opportunity.
        
        Returns:
            (should_notify, reason)
        """
        key = self._get_key(opportunity.symbol, opportunity.other_exchange)
        now = datetime.now()
        
        # Новый спред - всегда уведомляем
        if key not in self.spread_history:
            self._update_history(opportunity, now)
            return True, "NEW_SPREAD"
        
        history = self.spread_history[key]
        time_since_last = now - history.last_notification_time
        spread_change = self._calculate_spread_change(
            history.last_notification_spread,
            opportunity.spread_percent
        )
        
        # Проверка минимального cooldown
        if time_since_last < self.min_cooldown:
            self.logger.debug(
                f"{key}: Min cooldown active ({time_since_last.seconds}s < {self.min_cooldown.seconds}s)"
            )
            return False, "MIN_COOLDOWN"
        
        # Проверка значительного изменения спреда
        if spread_change >= self.min_spread_change:
            self._update_history(opportunity, now)
            self.logger.info(
                f"{key}: Spread changed by {spread_change:.2f}% "
                f"({history.last_notification_spread:.2f}% -> {opportunity.spread_percent:.2f}%)"
            )
            return True, "SPREAD_CHANGED"
        
        # Проверка максимального cooldown (принудительное уведомление)
        if time_since_last >= self.max_cooldown:
            self._update_history(opportunity, now)
            self.logger.info(f"{key}: Max cooldown reached, forcing notification")
            return True, "MAX_COOLDOWN"
        
        # Спред не изменился достаточно, пропускаем
        remaining = (self.min_cooldown - time_since_last).seconds if time_since_last < self.min_cooldown else 0
        self.logger.debug(
            f"{key}: Spread change {spread_change:.2f}% < {self.min_spread_change}% threshold"
        )
        return False, "NO_SIGNIFICANT_CHANGE"
    
    def _update_history(self, opportunity: SpreadOpportunity, timestamp: datetime):
        """Update spread history for the opportunity."""
        key = self._get_key(opportunity.symbol, opportunity.other_exchange)
        
        if key in self.spread_history:
            history = self.spread_history[key]
            history.last_spread = opportunity.spread_percent
            history.last_notification_time = timestamp
            history.last_notification_spread = opportunity.spread_percent
            history.notification_count += 1
        else:
            self.spread_history[key] = SpreadHistory(
                symbol=opportunity.symbol,
                exchange=opportunity.other_exchange,
                last_spread=opportunity.spread_percent,
                last_notification_time=timestamp,
                last_notification_spread=opportunity.spread_percent,
                notification_count=1
            )
    
    def update_spread_without_notify(self, opportunity: SpreadOpportunity):
        """Update tracked spread value without triggering notification."""
        key = self._get_key(opportunity.symbol, opportunity.other_exchange)
        
        if key in self.spread_history:
            self.spread_history[key].last_spread = opportunity.spread_percent
    
    def filter_opportunities(
        self,
        opportunities: list[SpreadOpportunity]
    ) -> list[SpreadOpportunity]:
        """
        Filter opportunities based on smart cooldown.
        Returns only opportunities that should trigger notifications.
        """
        filtered = []
        reasons_count: Dict[str, int] = {}
        
        for opp in opportunities:
            should_send, reason = self.should_notify(opp)
            reasons_count[reason] = reasons_count.get(reason, 0) + 1
            
            if should_send:
                filtered.append(opp)
            else:
                # Обновляем трекинг текущего спреда без уведомления
                self.update_spread_without_notify(opp)
        
        # Логируем статистику
        self.logger.info(
            f"Filtered {len(filtered)}/{len(opportunities)} signals. "
            f"Reasons: {reasons_count}"
        )
        
        return filtered
    
    def get_active_spreads(self) -> list[SpreadHistory]:
        """Get list of currently tracked spreads."""
        return list(self.spread_history.values())
    
    def cleanup_old_entries(self, max_age_hours: int = 6):
        """Remove stale entries that haven't been seen in a while."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        old_keys = [
            key for key, history in self.spread_history.items()
            if history.last_notification_time < cutoff
        ]
        
        for key in old_keys:
            del self.spread_history[key]
        
        if old_keys:
            self.logger.info(f"Cleaned up {len(old_keys)} stale spread entries")
    
    def get_stats(self) -> dict:
        """Get statistics about tracked spreads."""
        if not self.spread_history:
            return {"total_tracked": 0, "avg_spread": 0, "max_spread": 0}
        
        spreads = [h.last_spread for h in self.spread_history.values()]
        return {
            "total_tracked": len(spreads),
            "avg_spread": sum(spreads) / len(spreads),
            "max_spread": max(spreads),
            "min_spread": min(spreads),
            "total_notifications": sum(h.notification_count for h in self.spread_history.values())
        }
