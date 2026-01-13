"""Main bot v3.2 - With Funding Rate Filter and Topic support."""
import asyncio
import logging
import yaml
from datetime import datetime
from typing import Dict, Tuple
from colorama import Fore, Style, init as colorama_init

from exchanges.mexc_client import MEXCClient
from exchanges.binance_client import BinanceClient
from exchanges.bybit_client import BybitClient
from exchanges.gate_client import GateClient
from exchanges.kucoin_client import KuCoinClient
from exchanges.okx_client import OKXClient
from exchanges.bingx_client import BingXClient

from spread_detector import SpreadDetector
from signal_generator import SmartSignalGenerator
from telegram_notifier import TelegramNotifier
from funding_checker import FundingRateChecker


class SpreadMonitor:
    """Spread monitor with funding rate filter."""
    
    def __init__(self, config_path: str = "config.yaml"):
        colorama_init()
        self._setup_logging()
        self.logger = logging.getLogger("Monitor")
        
        self.config = self._load_config(config_path)
        
        # Clients
        self.mexc = MEXCClient()
        self.binance = BinanceClient()
        self.other = {
            "Bybit": BybitClient(),
            "Gate": GateClient(),
            "KuCoin": KuCoinClient(),
            "OKX": OKXClient(),
            "BingX": BingXClient()
        }
        
        # Detector
        self.detector = SpreadDetector(
            min_spread_percent=self.config['spread']['min_threshold'],
            min_volume_usdt=self.config['spread'].get('min_volume_usdt', 500_000),
        )
        
        # Funding rate checker
        max_funding = self.config['spread'].get('max_funding_rate', 0.5)
        self.funding = FundingRateChecker(max_funding_rate=max_funding)
        
        # Smart cooldown
        self.signals = SmartSignalGenerator(
            min_spread_change_percent=self.config['spread'].get('min_change_percent', 5.0),
            min_cooldown_minutes=self.config['spread'].get('min_cooldown_minutes', 3),
            max_cooldown_minutes=self.config['spread'].get('max_cooldown_minutes', 30)
        )
        
        # Telegram with topic support
        self.telegram = TelegramNotifier(
            bot_token=self.config['telegram']['bot_token'],
            chat_id=str(self.config['telegram']['chat_id']),
            message_thread_id=self.config['telegram'].get('message_thread_id')
        )
        
        self.running = False
        self.scan_count = 0
        self.alerts_sent = 0
        self.funding_rejected = 0
    
    def _setup_logging(self):
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("telegram").setLevel(logging.WARNING)
        logging.basicConfig(
            level=logging.INFO,
            format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} | '
                   f'{Fore.YELLOW}%(name)-12s{Style.RESET_ALL} | %(message)s',
            datefmt='%H:%M:%S'
        )
    
    def _load_config(self, path: str) -> dict:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    async def fetch_prices(self) -> Tuple[Dict, Dict]:
        """Fetch all prices."""
        start = datetime.now()
        
        tasks = {
            "MEXC": self.mexc.get_all_tickers_with_volume(),
            "Binance": self.binance.get_all_tickers_with_volume(),
        }
        for name, client in self.other.items():
            tasks[name] = client.get_all_tickers()
        
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results_dict = dict(zip(tasks.keys(), results))
        
        mexc_data = results_dict.get("MEXC", {})
        if isinstance(mexc_data, Exception):
            mexc_data = {}
        
        binance_data = results_dict.get("Binance", {})
        if isinstance(binance_data, Exception):
            binance_data = {}
        
        other_data = {"Binance": binance_data}
        for name in self.other.keys():
            raw = results_dict.get(name, {})
            if isinstance(raw, Exception):
                other_data[name] = {}
            else:
                other_data[name] = {s: (p, 1e9) for s, p in raw.items()}
        
        elapsed = (datetime.now() - start).total_seconds()
        self.logger.info(f"Prices: MEXC:{len(mexc_data)} Binance:{len(binance_data)} [{elapsed:.1f}s]")
        
        return mexc_data, other_data
    
    async def validate_opportunity(self, opp: SpreadOpportunity) -> bool:
        """
        Validate opportunity using real order book data (Bids/Asks).
        Returns True if valid, and updates opp.spread_percent with real spread.
        """
        try:
            # 1. Get MEXC Orderbook
            mexc_ob = await self.mexc.get_orderbook_ticker(opp.symbol)
            if not mexc_ob:
                self.logger.debug(f"{opp.symbol}: No MEXC orderbook")
                return False
            mexc_bid, mexc_ask = mexc_ob

            # 2. Get Other Orderbook
            other_client = self.other.get(opp.other_exchange.split()[0]) # Fix potential naming issues
            if not other_client:
                # Fallback purely on name
                for name, client in self.other.items():
                    if name in opp.other_exchange:
                        other_client = client
                        break
            
            if not other_client:
                 self.logger.error(f"Client not found for {opp.other_exchange}")
                 return False

            other_ob = await other_client.get_orderbook_ticker(opp.symbol)
            if not other_ob:
                self.logger.debug(f"{opp.symbol}: No {opp.other_exchange} orderbook")
                return False
            other_bid, other_ask = other_ob

            # 3. Check Internal Spread (Liquidity Health)
            # If internal spread > 5%, market is too illiquid/broken
            mexc_spread = (mexc_ask - mexc_bid) / mexc_bid * 100
            other_spread = (other_ask - other_bid) / other_bid * 100
            
            if mexc_spread > 5.0 or other_spread > 5.0:
                self.logger.debug(f"{opp.symbol}: Illiquid (Internal Spreads: {mexc_spread:.1f}% / {other_spread:.1f}%)")
                return False

            # 4. Calculate Real Arbitrage Spread (Bid vs Ask)
            # If Signal is MEXC_LONG -> Buy MEXC (Ask), Sell Other (Bid)
            if opp.signal == "MEXC_LONG":
                entry_price = mexc_ask
                exit_price = other_bid
                if entry_price >= exit_price:
                    # No profit
                     self.logger.debug(f"{opp.symbol}: No real profit (Buy {entry_price} >= Sell {exit_price})")
                     return False
                
                real_spread = (exit_price - entry_price) / entry_price * 100
                
            else: # MEXC_SHORT -> Sell MEXC (Bid), Buy Other (Ask)
                entry_price = other_ask
                exit_price = mexc_bid
                if entry_price >= exit_price:
                      self.logger.debug(f"{opp.symbol}: No real profit (Buy {entry_price} >= Sell {exit_price})")
                      return False

                real_spread = (exit_price - entry_price) / entry_price * 100

            # Update opportunity with REAL spread
            old_spread = opp.spread_percent
            opp.spread_percent = real_spread
            opp.mexc_price = mexc_ask if opp.signal == "MEXC_LONG" else mexc_bid
            opp.other_price = other_bid if opp.signal == "MEXC_LONG" else other_ask
            
            # Check if still profitable
            if real_spread < self.config['spread']['min_threshold']:
                self.logger.debug(f"{opp.symbol}: Spread dropped {old_spread:.1f}% -> {real_spread:.1f}% after OB check")
                return False
                
            return True

        except Exception as e:
            self.logger.error(f"Validation error {opp.symbol}: {e}")
            return False

    async def scan_and_send(self):
        """Scan and send signals with funding filter."""
        self.scan_count += 1
        
        try:
            # Refresh funding rates every scan
            await self.funding.refresh_all()
            
            # Fetch prices
            mexc_data, other_data = await self.fetch_prices()
            
            if not mexc_data:
                return
            
            # Detect opportunities
            opps = self.detector.detect(mexc_data, other_data)
            
            if not opps:
                self.logger.info("No spreads found")
                return
            
            # Process each opportunity
            for opp in opps:
                # 0. Validate with Order Book (Quality Check)
                is_valid = await self.validate_opportunity(opp)
                if not is_valid:
                    continue

                # 1. Check funding rate
                funding_ok, funding_reason = self.funding.is_funding_ok(
                    opp.symbol, opp.signal, opp.other_exchange
                )
                
                if not funding_ok:
                    self.funding_rejected += 1
                    self.logger.info(f"REJECTED {opp.symbol}: {funding_reason}")
                    continue
                
                # 2. Check cooldown
                should, reason = self.signals.should_notify(opp)
                
                if should:
                    vol_m = opp.min_volume / 1e6
                    
                    # Get funding info for message
                    mexc_fr = self.funding.mexc_rates.get(opp.symbol, 0) * 100
                    binance_fr = self.funding.binance_rates.get(opp.symbol, 0) * 100 if opp.other_exchange == "Binance" else 0
                    
                    self.logger.info(
                        f"SENDING: {opp.symbol} {opp.spread_percent:.1f}% "
                        f"FR:{mexc_fr:.3f}%/{binance_fr:.3f}%"
                    )
                    
                    success = await self.telegram.send_notification_with_funding(
                        opp, reason, mexc_fr, binance_fr
                    )
                    if success:
                        self.alerts_sent += 1
                else:
                    self.signals.update_spread_without_notify(opp)
                    
        except Exception as e:
            self.logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()

    async def cleanup(self):
        await self.mexc.close_session()
        await self.binance.close_session()
        await self.funding.close_session()
        for c in self.other.values():
            await c.close_session()
    
    def _banner(self):
        print(f"""
{Fore.GREEN}=============================================
  SPREAD MONITOR v3.3 + DYNAMIC VALIDATION
============================================={Style.RESET_ALL}
""")
    
    async def run(self):
        self._banner()
        self.running = True
        
        max_fr = self.config['spread'].get('max_funding_rate', 0.5)
        self.logger.info(f"Spread: {self.config['spread']['min_threshold']}%+")
        self.logger.info(f"Volume: ${self.config['spread'].get('min_volume_usdt', 500000)/1e6:.1f}M+")
        self.logger.info(f"Max Funding Rate: {max_fr}%")
        
        await self.telegram.send_startup_message(
            min_spread=self.config['spread']['min_threshold'],
            exchanges=["MEXC", "Binance", "Bybit", "Gate", "KuCoin", "OKX", "BingX"]
        )
        
        interval = self.config['monitoring']['scan_interval_seconds']
        
        try:
            while self.running:
                start = datetime.now()
                await self.scan_and_send()
                
                if self.scan_count % 30 == 0:
                    self.signals.cleanup_old_entries()
                    self.logger.info(
                        f"Stats: Sent={self.alerts_sent} FundingRejected={self.funding_rejected}"
                    )
                
                elapsed = (datetime.now() - start).total_seconds()
                await asyncio.sleep(max(1, interval - elapsed))
                
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            await self.cleanup()
            self.logger.info(f"Done. Scans:{self.scan_count} Sent:{self.alerts_sent} Rejected:{self.funding_rejected}")


async def main():
    bot = SpreadMonitor()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBye!")
