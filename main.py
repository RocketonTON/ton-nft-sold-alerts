"""
TON NFT Sales Bot - TON Center Version
Main entry point with async/await consistency
"""
import asyncio
import time
import traceback
import aiohttp
import json
from pathlib import Path
from config import TONCENTER_RATE_LIMIT
import sys

# === DEBUG LOGGING ===
print("=" * 60, flush=True)
print("[DEBUG] Starting TON NFT Bot (TON Center Version)...", flush=True)
print("=" * 60, flush=True)

try:
    from web_server import run_in_background
    print("[DEBUG] ✅ web_server imported", flush=True)
except Exception as e:
    print(f"[DEBUG] ❌ web_server import failed: {e}", flush=True)
    # Continue anyway, web server is optional

try:
    from config import current_path, royalty_addresses, collections_list, TONCENTER_API_V3
    from secretData import toncenter_api_key
    print("[DEBUG] ✅ config imported", flush=True)
    print(f"[DEBUG] royalty_addresses: {len(royalty_addresses)}", flush=True)
    print(f"[DEBUG] collections_list: {len(collections_list)}", flush=True)
except Exception as e:
    print(f"[DEBUG] ❌ config import failed: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from nftData import get_nft_data, get_collection_floor
    print("[DEBUG] ✅ nftData imported", flush=True)
except Exception as e:
    print(f"[DEBUG] ❌ nftData import failed: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from tgMessage import tg_message_async
    print("[DEBUG] ✅ tgMessage imported", flush=True)
except Exception as e:
    print(f"[DEBUG] ❌ tgMessage import failed: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from functions import parse_sale_stack, convert_ton_to_usd
    print("[DEBUG] ✅ functions imported", flush=True)
except Exception as e:
    print(f"[DEBUG] ❌ functions import failed: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

print("[DEBUG] All imports successful!", flush=True)
print("=" * 60, flush=True)

# === TON CENTER API CONFIGURATION ===
TONCENTER_HEADERS = {
    "accept": "application/json",
    "Content-Type": "application/json"
}
if toncenter_api_key:
    TONCENTER_HEADERS["X-API-Key"] = toncenter_api_key

HTTP_TIMEOUT = aiohttp.ClientTimeout(total=20)

class TonCenterAPI:
    
    def __init__(self):
        self.base_url = TONCENTER_API_V3
        self.headers = TONCENTER_HEADERS
        self.timeout = HTTP_TIMEOUT
        self.min_request_interval = TONCENTER_RATE_LIMIT
    
    async def get_transactions(self, address: str, limit: int = 10) -> list:
        """Fetch transactions for an address"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"{self.base_url}/getTransactions"
                params = {
                    "address": address,
                    "limit": limit
                }
                
                async with session.get(url, headers=self.headers, 
                                     params=params) as response:
                    
                    if response.status == 429:
                        print(f"[TON Center] ⛔ Rate limit exceeded for {address[-6:]}", flush=True)
                        return []
                    
                    if response.status != 200:
                        print(f"[TON Center] HTTP {response.status} for {address[-6:]}", flush=True)
                        return []
                    
                    data = await response.json()
                    return data.get("transactions", [])
        
        except asyncio.TimeoutError:
            print(f"[TON Center] Timeout for {address[-6:]}", flush=True)
            return []
        except Exception as e:
            print(f"[TON Center] Error for {address[-6:]}: {e}", flush=True)
            return []
    
    async def run_get_method(self, address: str, method: str, stack: list = None) -> list:
        """Execute a get method on a smart contract"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"{self.base_url}/runGetMethod"
                payload = {
                    "address": address,
                    "method": method,
                    "stack": stack if stack is not None else []
                }
                
                async with session.post(url, headers=self.headers, 
                                      json=payload) as response:
                    
                    if response.status == 429:
                        print(f"[TON Center] ⛔ Rate limit in get_method {method}", flush=True)
                        return None
                    
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    
                    if not data.get("success", False):
                        return None
                    
                    return data.get("stack", [])
        
        except asyncio.TimeoutError:
            print(f"[TON Center] Timeout in get_method {method}", flush=True)
            return None
        except Exception as e:
            print(f"[TON Center] Error in get_method {method}: {e}", flush=True)
            return None
    
    async def get_sale_data_with_retry(self, source_address: str) -> tuple:
        """Get sale data with retry logic"""
        methods = ['get_sale_data', 'get_offer_data']
        
        for method in methods:
            print(f"[RETRY] Trying {method}...", flush=True)
            
            for attempt in range(3):
                stack = await self.run_get_method(source_address, method)
                
                if stack is not None:
                    print(f"[RETRY] ✅ {method} succeeded on attempt {attempt+1}", flush=True)
                    return stack, method
                
                if attempt < 2:
                    print(f"[RETRY] ❌ {method} failed, waiting 2s...", flush=True)
                    await asyncio.sleep(2)
                else:
                    print(f"[RETRY] ❌ {method} failed on final attempt", flush=True)
        
        return None, None

# Global API instance
toncenter_api = TonCenterAPI()

def read_last_utime() -> int:
    """Read last processed timestamp"""
    try:
        with open(f'{current_path}/lastUtime.txt', 'r') as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        print(f"[lastUtime] File not found. Starting from 0.", flush=True)
        return 0

def write_last_utime(utime: int):
    """Write last processed timestamp"""
    try:
        with open(f'{current_path}/lastUtime.txt', 'w') as f:
            f.write(str(utime))
    except Exception as e:
        print(f"[lastUtime] Error saving: {e}", flush=True)

async def royalty_trs(royalty_address: str):
    """Check transactions for royalty address and process NFT sales"""
    try:
        # 1. READ lastUtime
        last_utime = read_last_utime()
        
        # 2. FETCH TRANSACTIONS
        print(f"[royalty_trs] Fetching transactions for {royalty_address[-6:]}...", flush=True)
        transactions = await toncenter_api.get_transactions(royalty_address, limit=25)
        
        if not transactions:
            print(f"[royalty_trs] No transactions found for {royalty_address[-6:]}", flush=True)
            return None
        
        print(f"[royalty_trs] Found {len(transactions)} transactions for {royalty_address[-6:]}", flush=True)
        
        # Debug info
        if transactions:
            print(f"[DEBUG] First tx utime: {transactions[0].get('utime', 'N/A')}", flush=True)
            print(f"[DEBUG] Last tx utime: {transactions[-1].get('utime', 'N/A')}", flush=True)
        
        latest_utime = last_utime
        processed_count = 0
        
        # 3. PROCESS TRANSACTIONS (from newest to oldest)
        for tx in transactions:
            tx_time = tx.get("utime", 0)
            
            if tx_time <= last_utime:
                continue
            
            # Update latest utime
            if tx_time > latest_utime:
                latest_utime = tx_time
            
            in_msg = tx.get("in_msg", {})
            source = in_msg.get("source", {}).get("address")
            
            if not source:
                continue
            
            print(f"[royalty_trs] Processing transaction from {source[-6:]} (utime: {tx_time})", flush=True)
            
            # GET SALE DATA WITH RETRY
            stack, method_used = await toncenter_api.get_sale_data_with_retry(source)
            
            if not stack:
                print(f"[royalty_trs] ❌ No sale data found for {source[-6:]}", flush=True)
                continue
            
            print(f"[royalty_trs] ✅ Success with {method_used}! Stack has {len(stack)} items", flush=True)
            
            # PARSE SALE DATA
            sale_data = parse_sale_stack(stack)
            
            if not sale_data or not sale_data[1]:
                print(f"[royalty_trs] ❌ Invalid sale data", flush=True)
                continue
            
            nft_address = sale_data[4] if len(sale_data) > 4 else None
            
            if not nft_address:
                continue
            
            # GET NFT DATA
            print(f"[royalty_trs] Fetching NFT data for {nft_address[-6:]}...", flush=True)
            nft_data = await get_nft_data(nft_address)
            
            if not nft_data:
                print(f"[royalty_trs] ❌ NFT data not found for {nft_address[-6:]}", flush=True)
                continue
            
            # CHECK COLLECTION
            collection_address = nft_data[1]
            if collection_address not in collections_list:
                print(f"[royalty_trs] ❌ Collection {collection_address[-6:]} not monitored", flush=True)
                continue
            
            print(f"[royalty_trs] ✅ Collection {collection_address[-6:]} is monitored!", flush=True)
            
            # GET FLOOR PRICE
            print(f"[royalty_trs] Fetching floor for collection {collection_address[-6:]}...", flush=True)
            floor_data = await get_collection_floor(collection_address)
            floor_price, floor_link = floor_data
            
            # SEND TELEGRAM NOTIFICATION
            try:
                if sale_data[0] == 'SaleFixPrice':
                    price = sale_data[6] if len(sale_data) > 6 else 0
                    await tg_message_async(
                        sale_data[0], sale_data[3], sale_data[4],
                        sale_data[5], nft_data[2], price,
                        nft_data[3], nft_data[4],
                        floor_price, floor_link
                    )
                
                elif sale_data[0] == 'SaleAuction':
                    price = sale_data[11] if len(sale_data) > 11 else 0
                    await tg_message_async(
                        sale_data[0], sale_data[3], sale_data[4],
                        sale_data[5], nft_data[2], price,
                        nft_data[3], nft_data[4],
                        floor_price, floor_link
                    )
                
                elif sale_data[0] == 'SaleOffer':
                    price = sale_data[6] if len(sale_data) > 6 else 0
                    await tg_message_async(
                        sale_data[0], sale_data[3], sale_data[4],
                        sale_data[5], nft_data[2], price,
                        nft_data[3], nft_data[4],
                        floor_price, floor_link
                    )
                
                print(f"[royalty_trs] ✅ Telegram notification sent for {nft_data[3]}", flush=True)
                processed_count += 1
                
            except Exception as e:
                print(f"[royalty_trs] ❌ Telegram error: {e}", flush=True)
        
        print(f"[royalty_trs] Processed {processed_count} new sales", flush=True)
        return latest_utime if latest_utime > last_utime else None
    
    except Exception as e:
        print(f"[royalty_trs] CRITICAL Error for {royalty_address[-6:]}: {e}", flush=True)
        traceback.print_exc()
        return None

async def scheduler():
    """Main bot loop"""
    print("\n" + "=" * 60, flush=True)
    print("=== [SCHEDULER] Started (TON Center API - Async) ===", flush=True)
    print("✅ Using python-telegram-bot (async)", flush=True)
    print("✅ Using TON Center API v3", flush=True)
    print("=" * 60 + "\n", flush=True)
    
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            
            try:
                print(f"\n[CYCLE #{cycle_count}] Start at {time.strftime('%H:%M:%S')}", flush=True)
                
                # Process all royalty addresses
                results = []
                for addr in royalty_addresses:
                    result = await royalty_trs(addr)
                    if result:
                        results.append(result)
                
                # Update lastUtime if new transactions found
                if results:
                    last_utime = max(results)
                    write_last_utime(last_utime)
                    print(f"[CYCLE #{cycle_count}] ✅ Updated lastUtime: {last_utime}", flush=True)
                
                print(f"[CYCLE #{cycle_count}] Finished. Sleeping 180s (3min)...", flush=True)
                
                # Sleep with heartbeat
                for i in range(6):
                    await asyncio.sleep(30)
                    minutes = (i + 1) * 0.5  # 0.5, 1.0, 1.5, 2.0, 2.5, 3.0 min
                    print(f"[HEARTBEAT] {minutes}min / 3min", flush=True)
                    
            except Exception as cycle_error:
                print(f"[CYCLE #{cycle_count}] ❌ Error in cycle: {cycle_error}", flush=True)
                traceback.print_exc()
                await asyncio.sleep(5)
    
    except KeyboardInterrupt:
        print("\n[SCHEDULER] Stopped by user", flush=True)
    except Exception as e:
        print(f"[SCHEDULER] Fatal error: {e}", flush=True)
        traceback.print_exc()

async def main():
    """Main async entry point"""
    print("\n[MAIN] TON NFT Bot starting (TON Center)...", flush=True)
    
    # Start web server in background (for Render)
    try:
        run_in_background()
        print("[MAIN] ✅ Web server started", flush=True)
        await asyncio.sleep(2)  # Let web server start
    except Exception as e:
        print(f"[MAIN] ⚠️ Web server failed: {e}", flush=True)
        # Continue without web server
    
    # Start main scheduler
    try:
        await scheduler()
    except KeyboardInterrupt:
        print("\n[MAIN] Bot stopped by user", flush=True)
    except Exception as e:
        print(f"[MAIN] ❌ Bot crashed: {e}", flush=True)
        traceback.print_exc()
        raise

if __name__ == '__main__':
    asyncio.run(main())
