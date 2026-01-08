import asyncio
from exchanges.mexc_client import MEXCClient
from exchanges.binance_client import BinanceClient
from exchanges.bybit_client import BybitClient
from exchanges.gate_client import GateClient
from exchanges.kucoin_client import KuCoinClient
from exchanges.okx_client import OKXClient
from exchanges.bingx_client import BingXClient

async def check_overlaps():
    print("Fetching pairs from all exchanges...")
    
    clients = {
        "MEXC": MEXCClient(),
        "Binance": BinanceClient(),
        "Bybit": BybitClient(),
        "Gate": GateClient(),
        "KuCoin": KuCoinClient(),
        "OKX": OKXClient(),
        "BingX": BingXClient()
    }
    
    tickers = {}
    
    # Fetch all concurrently
    tasks = [client.get_all_symbols() for client in clients.values()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for name, result in zip(clients.keys(), results):
        if isinstance(result, Exception):
            print(f"Error fetching {name}: {result}")
            tickers[name] = set()
        else:
            tickers[name] = set(result)
            print(f"{name}: {len(tickers[name])} pairs")
            
    mexc_pairs = tickers["MEXC"]
    
    print("\n--- Common Pairs with MEXC ---")
    print(f"MEXC Total: {len(mexc_pairs)}")
    
    for name in ["Binance", "Bybit", "Gate", "KuCoin", "OKX", "BingX"]:
        other_pairs = tickers.get(name, set())
        common = mexc_pairs.intersection(other_pairs)
        print(f"MEXC + {name}: {len(common)} pairs")
        
    # Close sessions
    for client in clients.values():
        await client.close_session()

if __name__ == "__main__":
    asyncio.run(check_overlaps())
