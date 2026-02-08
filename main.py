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

def get_transactions_http(address, limit=50):
    """Ottiene le transazioni via HTTP API (TonAPI)."""
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


def run_get_method_http(address, method):
    """Esegue un get method via HTTP API."""
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


def parse_tonapi_stack(stack):
    """Converte lo stack di TonAPI nel formato atteso."""
    converted = []
    
    for item in stack:
        item_type = item.get("type") if isinstance(item, dict) else None
        
        if item_type == "num":
            # Converti decimal string in hex
            num_val = int(item.get("num", "0"))
            converted.append(["num", hex(num_val)])
        
        elif item_type == "cell":
            # Cell in formato base64
            cell_bytes = item.get("cell", "")
            converted.append(["tvm.Cell", {"bytes": cell_bytes}])
        
        elif item_type == "slice":
            # Slice - convertiamo in cell
            cell_bytes = item.get("cell", "")
            converted.append(["tvm.Cell", {"bytes": cell_bytes}])
        
        else:
            converted.append(["unknown", str(item)])
    
    return converted


def get_nft_data_http(nft_address):
    """Ottiene i dati NFT via TonAPI."""
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
        
        # 2. OTTIENI TRANSAZIONI
        print(f"[royalty_trs] Fetching transactions for {royalty_address[-6:]}...", flush=True)
        transactions = get_transactions_http(royalty_address, limit=50)
        
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
            # Calcola source qui solo per debug
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
                stack = run_get_method_http(source, method)
                
                if not stack:
                    continue
                
                converted_stack = parse_tonapi_stack(stack)
                
                from functions import parse_sale_stack
                sale_data = parse_sale_stack(converted_stack)
                
                if not sale_data or not sale_data[1]:
                    continue
                
                nft_address = sale_data[4]
                nft_data = get_nft_data_http(nft_address)
                
                if not nft_data or nft_data[1] not in collections_list:
                    continue
                
                collection_floor_data = get_collection_floor(nft_data[1])
                
                if sale_data[0] == 'SaleFixPrice':
                    tg_message(
                        sale_data[0], sale_data[3], sale_data[4],
                        sale_data[5], nft_data[2], sale_data[6],
                        nft_data[3], nft_data[4],
                        collection_floor_data[0], collection_floor_data[1]
                    )
                
                elif sale_data[0] == 'SaleAuction':
                    tg_message(
                        sale_data[0], sale_data[3], sale_data[4],
                        sale_data[5], nft_data[2], sale_data[11],
                        nft_data[3], nft_data[4],
                        collection_floor_data[0], collection_floor_data[1]
                    )
                
                elif sale_data[0] == 'SaleOffer':
                    tg_message(
                        sale_data[0], sale_data[3], sale_data[4],
                        sale_data[5], nft_data[2], sale_data[6],
                        nft_data[3], nft_data[4],
                        collection_floor_data[0], collection_floor_data[1]
                    )
                
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
    print("=== [SCHEDULER] Started (HTTP API Mode) ===", flush=True)
    print("✅ Using TonAPI instead of lite client - no connection issues!", flush=True)
    print("=" * 60 + "\n", flush=True)
    
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            print(f"\n[CYCLE #{cycle_count}] Start at {time.strftime('%H:%M:%S')}", flush=True)
            
            results = []
            for addr in royalty_addresses:
                result = await royalty_trs(addr)
                results.append(result)
            
            utimes = [u for u in results if u is not None]
            
            if utimes:
                last = max(utimes)
                try:
                    with open(f'{current_path}/lastUtime.txt', 'w') as f:
                        f.write(str(last))
                    print(f"[CYCLE #{cycle_count}] ✅ Updated lastUtime: {last}", flush=True)
                except Exception as e:
                    print(f"[CYCLE #{cycle_count}] ❌ Error saving lastUtime: {e}", flush=True)
            
            print(f"[CYCLE #{cycle_count}] Finished. Sleeping 15s...", flush=True)
            await asyncio.sleep(15)
    
    except KeyboardInterrupt:
        print("\n[SCHEDULER] Stopped by user", flush=True)
    except Exception as e:
        print(f"[SCHEDULER] Fatal error: {e}", flush=True)
        traceback.print_exc()


if __name__ == '__main__':
    print("\n[MAIN] Bot starting...", flush=True)
    
    # Avvia il web server per Render
    try:
        print("[MAIN] Starting web server...", flush=True)
        run_in_background()
        print("[MAIN] ✅ Web server started", flush=True)
    except Exception as e:
        print(f"[MAIN] ❌ Web server failed: {e}", flush=True)
        traceback.print_exc()
    
    # Avvia lo scheduler
    try:
        print("[MAIN] Starting scheduler...", flush=True)
        asyncio.run(scheduler())
    except KeyboardInterrupt:
        print("\n[MAIN] Bot stopped by user", flush=True)
    except Exception as e:
        print(f"[MAIN] ❌ Bot crashed: {e}", flush=True)
        traceback.print_exc()
        raise
