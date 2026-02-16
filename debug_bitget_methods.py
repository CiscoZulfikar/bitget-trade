
import asyncio
import os
import ccxt.async_support as ccxt
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
SECRET = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

async def main():
    exchange = ccxt.bitget({
        'apiKey': API_KEY,
        'secret': SECRET,
        'password': PASSPHRASE,
        'options': {'defaultType': 'swap'}
    })
    
    print("Searching for TPSL / Plan / Position methods...")
    methods = dir(exchange)
    
    # Broader search
    candidates = [m for m in methods if 'tpsl' in m.lower() or 'plan' in m.lower() or 'position' in m.lower() or 'stop' in m.lower()] 
    # Narrow down to private methods usually starting with private
    candidates = [m for m in candidates if 'private' in m]
    
    print(f"Found {len(candidates)} candidates:")
    for c in sorted(candidates):
        print(c)
        
    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
