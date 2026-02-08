import asyncio
import time
import traceback
import requests
from pathlib import Path
import sys

# === LOG DI DEBUG ===
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
    print("[DEBUG] ✅ functions imported", flush=True)
except Exception as e:
    print(f"[DEBUG] ❌ functions import failed: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

print("[DEBUG] All imports successful!", flush=True)
print("=" * 60, flush=True)

# === CONFIGURAZIONE TONAPI ===
TONAPI_BASE = "https://tonapi.io/v2"
TONAPI_HEADERS = {
    "Authorization": "Bearer AFH3J5APTYFZD6QAAAAFQRGBZFOIO26SOOJ5N2LD5YGJGDOBMFBDKA3HNZ72ZNUTFHSFRJI"
}
HTTP_TIMEOUT = 10  # Timeout unico per tutte le richieste HTTP

def get_transactions_http_sync(address, limit=50):
    """Versione SINCRONA - verrà chiamata con to_thread."""
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
    """Wrapper ASINCRONO."""
    return await asyncio.to_thread(get_transactions_http_sync, address, limit)


def run_get_method_http_sync(address, method):
    """Versione SINCRONA - verrà chiamata con to_thread."""
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
    """Wrapper ASINCRONO."""
    return await asyncio.to_thread(run_get_method_http_sync, address, method)


def parse_tonapi_stack(stack):
    """Converte lo stack di TonAPI nel formato atteso."""
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
    """Versione SINCRONA - verrà chiamata con to_thread."""
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
    """Wrapper ASINCRONO."""
    return await asyncio.to_thread(get_nft_data_http_sync, nft_address)


async def royalty_trs(royalty_address):
    """Controlla le transazioni per un indirizzo royalty usando HTTP API."""
    try:
        utimes = []
        
        # 1. LEGGI lastUtime
        try:
            with open(f'{current_path}/lastUtime.txt', 'r') as f:
                last_utime = int(f.read().strip())
        except (FileNotFoundError, ValueError):
            last_utime = 0
            print(f"[royalty_trs] File lastUtime non trovato. Inizio da timestamp 0.", flush=True)
        
        # 2. OTTIENI TRANSAZIONI (ORA ASINCRONO CON TIMEOUT)
        print(f"[royalty_trs] Fetching transactions for {royalty_address[-6:]}...", flush=True)
        try:
            transactions = await asyncio.wait_for(
                get_transactions_http(royalty_address, limit=50),
                timeout=20  # Max 20 secondi per fetch transazioni
            )
        except asyncio.TimeoutError:
            print(f"[royalty_trs] ⏱️ TIMEOUT fetching transactions for {royalty_address[-6:]}", flush=True)
            return None
        
        if not transactions:
            print(f"[royalty_trs] No transactions found for {royalty_address[-6:]}", flush=True)
            return None
        
        print(f"[royalty_trs] Found {len(transactions)} transactions for {royalty_address[-6:]}", flush=True)

        # === DEBUG SECTION 1 ===
        print(f"[DEBUG] last_utime from file: {last_utime}")
        print(f"[DEBUG] First transaction utime: {transactions[0]['utime'] if transactions else 'N/A'}")
        print(f"[DEBUG] Last transaction utime: {transactions[-1]['utime'] if transactions else 'N/A'}")
        
        new_count = 0
        for tx in reversed(transactions):
            if tx.get("utime", 0) > last_utime:
                new_count += 1
        print(f"[DEBUG] Transactions with utime > last_utime: {new_count}/{len(transactions)}")
        
        # 3. PROCESSA TRANSAZIONI
        for tx in reversed(transactions):
            tx_time = tx.get("utime", 0)

            # === DEBUG SECTION 2 ===
            debug_msg = f"[DEBUG TX] utime={tx_time}, is_new={tx_time > last_utime}"
            temp_source = tx.get("in_msg", {}).get("source", {}).get("address") if tx_time > last_utime else None
            if tx_time > last_utime and temp_source:
                debug_msg += f" ✓ NEW (source: {temp_source[-6:]})"
            print(debug_msg, flush=True)
            
            if tx_time <= last_utime:
                continue
            
            in_msg = tx.get("in_msg", {})
            source = in_msg.get("source", {}).get("address")
            
            if not source:
                continue
            
            get_methods = ['get_sale_data', 'get_offer_data']
            
            for method in get_methods:
                # ORA ASINCRONO CON TIMEOUT
                print(f"[DEBUG] Calling {method} on {source[-6:]}...", flush=True)
                try:
                    stack = await asyncio.wait_for(
                        run_get_method_http(source, method),
                        timeout=15  # Max 15 secondi per chiamata
                    )
                    print(f"[DEBUG] {method} on {source[-6:]} returned {len(stack) if stack else 0} items", flush=True)
                except asyncio.TimeoutError:
                    print(f"[DEBUG] ⏱️ TIMEOUT {method} on {source[-6:]} after 15s", flush=True)
                    continue
                
                if not stack:
                    continue
                
                converted_stack = parse_tonapi_stack(stack)
                
                from functions import parse_sale_stack
                sale_data = parse_sale_stack(converted_stack)
                
                if not sale_data or not sale_data[1]:
                    continue
                
                nft_address = sale_data[4]
                # ORA ASINCRONO CON TIMEOUT
                print(f"[DEBUG] Fetching NFT data for {nft_address[-6:]}...", flush=True)
                try:
                    nft_data = await asyncio.wait_for(
                        get_nft_data_http(nft_address),
                        timeout=15
                    )
                    print(f"[DEBUG] NFT data fetched: {nft_data[3] if nft_data else 'None'}", flush=True)
                except asyncio.TimeoutError:
                    print(f"[DEBUG] ⏱️ TIMEOUT fetching NFT data for {nft_address[-6:]}", flush=True)
                    continue
                
                if not nft_data or nft_data[1] not in collections_list:
                    continue
                
                # get_collection_floor è SINCRONA, ma wrappata CON TIMEOUT
                print(f"[DEBUG] Fetching floor for collection {nft_data[1][-6:]}...", flush=True)
                try:
                    collection_floor_data = await asyncio.wait_for(
                        asyncio.to_thread(get_collection_floor, nft_data[1]),
                        timeout=15
                    )
                    print(f"[DEBUG] Floor: {collection_floor_data[0] if collection_floor_data else 'None'} TON", flush=True)
                except asyncio.TimeoutError:
                    print(f"[DEBUG] ⏱️ TIMEOUT fetching floor - using None", flush=True)
                    collection_floor_data = (None, None)
                
                if sale_data[0] == 'SaleFixPrice':
                    print(f"[DEBUG] Sending Telegram message (FixPrice)...", flush=True)
                    try:
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
                        print(f"[DEBUG] ✅ Telegram message sent!", flush=True)
                    except asyncio.TimeoutError:
                        print(f"[DEBUG] ⏱️ TIMEOUT sending Telegram message", flush=True)
                
                elif sale_data[0] == 'SaleAuction':
                    print(f"[DEBUG] Sending Telegram message (Auction)...", flush=True)
                    try:
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
                        print(f"[DEBUG] ✅ Telegram message sent!", flush=True)
                    except asyncio.TimeoutError:
                        print(f"[DEBUG] ⏱️ TIMEOUT sending Telegram message", flush=True)
                
                elif sale_data[0] == 'SaleOffer':
                    print(f"[DEBUG] Sending Telegram message (Offer)...", flush=True)
                    try:
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
                        print(f"[DEBUG] ✅ Telegram message sent!", flush=True)
                    except asyncio.TimeoutError:
                        print(f"[DEBUG] ⏱️ TIMEOUT sending Telegram message", flush=True)
                
                utimes.append(tx_time)
                break

        # === DEBUG SECTION 3 ===
        print(f"[DEBUG] Total new transactions processed: {len(utimes)}")
        print(f"[DEBUG] Highest utime found: {max(utimes) if utimes else 'None'}")
        
        return utimes[-1] if utimes else None
    
    except Exception as e:
        print(f"[royalty_trs] CRITICAL Error for {royalty_address[-6:]}: {e}", flush=True)
        traceback.print_exc()
        return None


async def scheduler():
    """Loop principale del bot."""
    print("\n" + "=" * 60, flush=True)
    print("=== [SCHEDULER] Started (HTTP API Mode - FIXED) ===", flush=True)
    print("✅ All blocking I/O wrapped in asyncio.to_thread!", flush=True)
    print("=" * 60 + "\n", flush=True)
    
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            
            try:
                print(f"\n[CYCLE #{cycle_count}] Start at {time.strftime('%H:%M:%S')}", flush=True)
                
                results = []
                for addr in royalty_addresses:
                    result = await royalty_trs(addr)
                    results.append(result)
                
                utimes = [u for u in results if u is not None]
                
                if utimes:
                    last = max(utimes)
                    try:
                        # Anche la scrittura file è ora async
                        await asyncio.to_thread(lambda: open(f'{current_path}/lastUtime.txt', 'w').write(str(last)))
                        print(f"[CYCLE #{cycle_count}] ✅ Updated lastUtime: {last}", flush=True)
                    except Exception as e:
                        print(f"[CYCLE #{cycle_count}] ❌ Error saving lastUtime: {e}", flush=True)
                
                print(f"[CYCLE #{cycle_count}] Finished. Sleeping 15s...", flush=True)
                
                # Sleep con heartbeat
                for i in range(3):
                    await asyncio.sleep(5)
                    print(f"[HEARTBEAT] Alive... ({(i+1)*5}s)", flush=True)
                    
            except Exception as cycle_error:
                print(f"[CYCLE #{cycle_count}] ❌ Error in cycle: {cycle_error}", flush=True)
                traceback.print_exc()
                await asyncio.sleep(5)
    
    except KeyboardInterrupt:
        print("\n[SCHEDULER] Stopped by user", flush=True)
    except Exception as e:
        print(f"[SCHEDULER] Fatal error: {e}", flush=True)
        traceback.print_exc()


if __name__ == '__main__':
    print("\n[MAIN] Bot starting...", flush=True)
    
    try:
        print("[MAIN] Starting web server...", flush=True)
        run_in_background()
        print("[MAIN] ✅ Web server started", flush=True)
    except Exception as e:
        print(f"[MAIN] ❌ Web server failed: {e}", flush=True)
        traceback.print_exc()
    
    try:
        print("[MAIN] Starting scheduler...", flush=True)
        asyncio.run(scheduler())
    except KeyboardInterrupt:
        print("\n[MAIN] Bot stopped by user", flush=True)
    except Exception as e:
        print(f"[MAIN] ❌ Bot crashed: {e}", flush=True)
        traceback.print_exc()
        raise
