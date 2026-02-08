"""
TON NFT Sales Bot - Main Entry Point
Monitors NFT sales on TON blockchain and sends Telegram notifications
"""

import asyncio
import time
import traceback
import requests
from pathlib import Path
import sys

# === DEBUG LOGGING ===
print("=" * 60, flush=True)
print("[DEBUG] Starting bot imports...", flush=True)
print("=" * 60, flush=True)

try:
    from web_server import run_in_background
    print("[DEBUG] ✅ web_server imported", flush=True)
except Exception as e:
    print(f"[DEBUG] ❌ web_server import failed: {e}", flush=True)
    sys.exit(1)

try:
    from config import current_path, royalty_addresses, collections_list
    print("[DEBUG] ✅ config imported", flush=True)
    print(f"[DEBUG] royalty_addresses: {royalty_addresses}", flush=True)
    print(f"[DEBUG] collections_list: {collections_list}", flush=True)
except Exception as e:
    print(f"[DEBUG] ❌ config import failed: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from nftData import get_collection_floor
    print("[DEBUG] ✅ nftData imported", flush=True)
except Exception as e:
    print(f"[DEBUG] ❌ nftData import failed: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from tgMessage import tg_message
    print("[DEBUG] ✅ tgMessage imported", flush=True)
except Exception as e:
    print(f"[DEBUG] ❌ tgMessage import failed: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from functions import convert_ton_to_usd
    from secretData import tonapi_token
    print("[DEBUG] ✅ functions and secrets imported", flush=True)
except Exception as e:
    print(f"[DEBUG] ❌ functions/secrets import failed: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

print("[DEBUG] All imports successful!", flush=True)
print("=" * 60, flush=True)

# === TONAPI CONFIGURATION ===
TONAPI_BASE = "https://tonapi.io/v2"
TONAPI_HEADERS = {
    "Authorization": f"Bearer {tonapi_token}"
}
HTTP_TIMEOUT = 10  # Unified timeout for all HTTP requests

def get_transactions_http_sync(address, limit=50):
    """Fetch transactions via TonAPI (synchronous)."""
    try:
        url = f"{TONAPI_BASE}/blockchain/accounts/{address}/transactions"
        params = {"limit": limit}
        
        response = requests.get(url, headers=TONAPI_HEADERS, params=params, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        return data.get("transactions", [])
    
    except Exception as e:
        print(f"[get_transactions_http] Error: {e}", flush=True)
        return []


async def get_transactions_http(address, limit=50):
    """Async wrapper for get_transactions_http_sync."""
    return await asyncio.to_thread(get_transactions_http_sync, address, limit)


def run_get_method_http_sync(address, method):
    """Execute a get method via TonAPI (synchronous)."""
    try:
        url = f"{TONAPI_BASE}/blockchain/accounts/{address}/methods/{method}"
        
        response = requests.get(url, headers=TONAPI_HEADERS, timeout=HTTP_TIMEOUT)
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        
        if not data.get("success", False):
            return None
        
        stack = data.get("stack", [])
        return stack if stack else None
    
    except Exception as e:
        return None


async def run_get_method_http(address, method):
    """Async wrapper for run_get_method_http_sync."""
    return await asyncio.to_thread(run_get_method_http_sync, address, method)


def parse_tonapi_stack(stack):
    """Convert TonAPI stack to expected format."""
    converted = []
    
    for item in stack:
        item_type = item.get("type") if isinstance(item, dict) else None
        
        if item_type == "num":
            num_val = int(item.get("num", "0"))
            converted.append(["num", hex(num_val)])
        
        elif item_type == "cell":
            cell_bytes = item.get("cell", "")
            converted.append(["tvm.Cell", {"bytes": cell_bytes}])
        
        elif item_type == "slice":
            cell_bytes = item.get("cell", "")
            converted.append(["tvm.Cell", {"bytes": cell_bytes}])
        
        else:
            converted.append(["unknown", str(item)])
    
    return converted


def get_nft_data_http_sync(nft_address):
    """Fetch NFT data via TonAPI (synchronous)."""
    try:
        url = f"{TONAPI_BASE}/nfts/{nft_address}"
        
        response = requests.get(url, headers=TONAPI_HEADERS, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        
        collection_address = data.get("collection", {}).get("address")
        owner_address = data.get("owner", {}).get("address")
        nft_name = data.get("metadata", {}).get("name", "Unknown NFT")
        nft_image = data.get("previews", [{}])[0].get("url", "") if data.get("previews") else ""
        
        init = bool(collection_address and owner_address)
        
        return init, collection_address, owner_address, nft_name, nft_image
    
    except Exception as e:
        print(f"[get_nft_data_http] Error for {nft_address}: {e}", flush=True)
        return None


async def get_nft_data_http(nft_address):
    """Async wrapper for get_nft_data_http_sync."""
    return await asyncio.to_thread(get_nft_data_http_sync, nft_address)


async def royalty_trs(royalty_address):
    """Check transactions for royalty address and process NFT sales."""
    try:
        utimes = []
        
        # Read last processed timestamp
        try:
            with open(f'{current_path}/lastUtime.txt', 'r') as f:
                last_utime = int(f.read().strip())
        except (FileNotFoundError, ValueError):
            last_utime = 0
            print(f"[royalty_trs] lastUtime file not found. Starting from 0.", flush=True)
        
        # Fetch transactions with timeout
        print(f"[royalty_trs] Fetching transactions for {royalty_address[-6:]}...", flush=True)
        try:
            transactions = await asyncio.wait_for(
                get_transactions_http(royalty_address, limit=50),
                timeout=20
            )
        except asyncio.TimeoutError:
            print(f"[royalty_trs] ⏱️ TIMEOUT fetching transactions", flush=True)
            return None
        
        if not transactions:
            print(f"[royalty_trs] No transactions found", flush=True)
            return None
        
        print(f"[royalty_trs] Found {len(transactions)} transactions", flush=True)
        
        # Process transactions from oldest to newest
        for tx in reversed(transactions):
            tx_time = tx.get("utime", 0)
            
            if tx_time <= last_utime:
                continue
            
            in_msg = tx.get("in_msg", {})
            source = in_msg.get("source", {}).get("address")
            
            if not source:
                continue
            
            # Try both get_sale_data and get_offer_data methods
            for method in ['get_sale_data', 'get_offer_data']:
                try:
                    stack = await asyncio.wait_for(
                        run_get_method_http(source, method),
                        timeout=15
                    )
                except asyncio.TimeoutError:
                    continue
                
                if not stack:
                    continue
                
                converted_stack = parse_tonapi_stack(stack)
                
                from functions import parse_sale_stack
                sale_data = parse_sale_stack(converted_stack)
                
                if not sale_data or not sale_data[1]:
                    continue
                
                # Fetch NFT data
                nft_address = sale_data[4]
                try:
                    nft_data = await asyncio.wait_for(
                        get_nft_data_http(nft_address),
                        timeout=15
                    )
                except asyncio.TimeoutError:
                    continue
                
                if not nft_data or nft_data[1] not in collections_list:
                    continue
                
                # Fetch collection floor price
                try:
                    collection_floor_data = await asyncio.wait_for(
                        asyncio.to_thread(get_collection_floor, nft_data[1]),
                        timeout=15
                    )
                except asyncio.TimeoutError:
                    collection_floor_data = (None, None)
                
                # Send Telegram notification
                try:
                    if sale_data[0] == 'SaleFixPrice':
                        await asyncio.wait_for(
                            asyncio.to_thread(
                                tg_message,
                                sale_data[0], sale_data[3], sale_data[4],
                                sale_data[5], nft_data[2], sale_data[6],
                                nft_data[3], nft_data[4],
                                collection_floor_data[0], collection_floor_data[1]
                            ),
                            timeout=10
                        )
                    elif sale_data[0] == 'SaleAuction':
                        await asyncio.wait_for(
                            asyncio.to_thread(
                                tg_message,
                                sale_data[0], sale_data[3], sale_data[4],
                                sale_data[5], nft_data[2], sale_data[11],
                                nft_data[3], nft_data[4],
                                collection_floor_data[0], collection_floor_data[1]
                            ),
                            timeout=10
                        )
                    elif sale_data[0] == 'SaleOffer':
                        await asyncio.wait_for(
                            asyncio.to_thread(
                                tg_message,
                                sale_data[0], sale_data[3], sale_data[4],
                                sale_data[5], nft_data[2], sale_data[6],
                                nft_data[3], nft_data[4],
                                collection_floor_data[0], collection_floor_data[1]
                            ),
                            timeout=10
                        )
                    print(f"[royalty_trs] ✅ Sale processed successfully", flush=True)
                except asyncio.TimeoutError:
                    print(f"[royalty_trs] ⏱️ TIMEOUT sending Telegram", flush=True)
                
                utimes.append(tx_time)
                break
        
        return utimes[-1] if utimes else None
    
    except Exception as e:
        print(f"[royalty_trs] CRITICAL: {e}", flush=True)
        traceback.print_exc()
        return None


async def scheduler():
    """Main bot loop."""
    print("=" * 60, flush=True)
    print("=== [SCHEDULER] Started (TonAPI Mode) ===", flush=True)
    print("=" * 60, flush=True)
    
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            
            try:
                print(f"\n[CYCLE #{cycle_count}] {time.strftime('%H:%M:%S')}", flush=True)
                
                # Process all royalty addresses
                results = await asyncio.gather(*[royalty_trs(addr) for addr in royalty_addresses])
                utimes = [u for u in results if u is not None]
                
                # Update lastUtime file
                if utimes:
                    last = max(utimes)
                    try:
                        with open(f'{current_path}/lastUtime.txt', 'w') as f:
                            f.write(str(last))
                        print(f"[CYCLE #{cycle_count}] ✅ Updated lastUtime: {last}", flush=True)
                    except Exception as e:
                        print(f"[CYCLE #{cycle_count}] ❌ Error saving: {e}", flush=True)
                
                print(f"[CYCLE #{cycle_count}] Sleeping 15s...", flush=True)
                
                # Heartbeat during sleep
                for i in range(15):
                    await asyncio.sleep(1)
                    if (i + 1) % 5 == 0:
                        print(f"[HEARTBEAT] {i+1}s", flush=True)
                    
            except Exception as e:
                print(f"[CYCLE #{cycle_count}] ❌ Error: {e}", flush=True)
                traceback.print_exc()
                await asyncio.sleep(5)
    
    except KeyboardInterrupt:
        print("[SCHEDULER] Stopped", flush=True)
    except Exception as e:
        print(f"[SCHEDULER] Fatal: {e}", flush=True)
        traceback.print_exc()


if __name__ == '__main__':
    print("[MAIN] Starting...", flush=True)
    
    try:
        run_in_background()
        print("[MAIN] ✅ Web server started", flush=True)
    except Exception as e:
        print(f"[MAIN] ❌ Web server failed: {e}", flush=True)
    
    try:
        asyncio.run(scheduler())
    except KeyboardInterrupt:
        print("[MAIN] Stopped by user", flush=True)
    except Exception as e:
        print(f"[MAIN] ❌ Crashed: {e}", flush=True)
        raise
