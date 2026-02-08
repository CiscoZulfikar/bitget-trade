import os
import ccxt
from config import BITGET_API_KEY, BITGET_SECRET_KEY, BITGET_PASSPHRASE

def mask(s):
    if not s: return "NONE"
    if len(s) < 6: return "*" * len(s)
    return s[:3] + "*" * (len(s)-6) + s[-3:]

print("\n🔍 DEBUGGING BITGET CREDENTIALS")
print("---------------------------------")
print(f"API KEY:    {mask(BITGET_API_KEY)} (Length: {len(BITGET_API_KEY)})")
print(f"SECRET:     {mask(BITGET_SECRET_KEY)} (Length: {len(BITGET_SECRET_KEY)})")
print(f"PASSPHRASE: {mask(BITGET_PASSPHRASE)} (Length: {len(BITGET_PASSPHRASE)})")
print("---------------------------------")

try:
    print("Testing connection...")
    exchange = ccxt.bitget({
        'apiKey': BITGET_API_KEY,
        'secret': BITGET_SECRET_KEY,
        'password': BITGET_PASSPHRASE,
        'options': {'defaultType': 'swap'}
    })
    balance = exchange.fetch_balance()
    print("✅ CONNECTION SUCCESS!")
    print(f"USDT Free: {balance['USDT']['free']}")
except Exception as e:
    print(f"❌ CONNECTION FAILED: {e}")

print("\nNOTE: Error 40012 means 'ApiKey/Password incorrect'.")
print("Check if your PASSPHRASE is correct (it is NOT your login password).")
print("Check if your API Key has IP white-listing enabled (and this IP is missing).")
