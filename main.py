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
        # PROVA CON API v2 (più stabile)
        self.base_url = "https://toncenter.com/api/v2"  # ← CAMBIA A v2
        # self.base_url = TONCENTER_API_V3  # ← COMMENTA QUESTA
        
        self.headers = TONCENTER_HEADERS
        self.timeout = HTTP_TIMEOUT
        self.min_request_interval = TONCENTER_RATE_LIMIT
        
        print(f"[DEBUG] Using API: {self.base_url}")
    
    async def get_transactions(self, address: str, limit: int = 10) -> list:
    """Fetch transactions - test multiple approaches"""
    
    # Testa diverse combinazioni di parametri
    test_cases = [
        {"archival": "true"},   # 1. Con archival
        {},                     # 2. Senza archival (più transazioni)
        {"archival": "false"},  # 3. Solo non-archival
    ]
    
    for params_test in test_cases:
        try:
            print(f"[DEBUG] Testing params: {params_test}")
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Parametri base
                base_params = {
                    "address": address,
                    "limit": limit,
                }
                # Combina con test case
                params = {**base_params, **params_test}
                
                url = f"{self.base_url}/getTransactions"
                
                async with session.get(url, headers=self.headers, params=params) as response:
                    
                    print(f"[DEBUG] Status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        txs = data.get("transactions", [])
                        print(f"[TON Center] ✅ Got {len(txs)} transactions with params: {params_test}")
                        
                        if txs:
                            # Mostra qualche info sulle transazioni
                            for i, tx in enumerate(txs[:3]):  # Prime 3 transazioni
                                print(f"  TX {i}: utime={tx.get('utime')}, hash={tx.get('hash', '')[:10]}...")
                            return txs
                        else:
                            print(f"[TON Center] ⚠️ 0 transactions with params: {params_test}")
                            continue  # Prova combinazione successiva
                    
                    else:
                        error_text = await response.text()
                        print(f"[DEBUG] Failed: {error_text[:100]}")
                        continue
        
        except Exception as e:
            print(f"[DEBUG] Error: {e}")
            continue
    
    print(f"[TON Center] ❌ No transactions found with any parameters")
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
                
                async with session.post(url, headers=self.headers, json=payload) as response:
                    
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

# Debug verification
print("[DEBUG] ✅ TonCenterAPI class structure verified")
print(f"[DEBUG] Methods available: {[m for m in dir(toncenter_api) if not m.startswith('_')]}")

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
        print(f"[DEBUG] Last utime from file: {last_utime} ({time.ctime(last_utime) if last_utime > 0 else 'epoch'})")
        
        # 2. FETCH TRANSACTIONS
        print(f"[royalty_trs] Fetching transactions for {royalty_address}...", flush=True)
        transactions = await toncenter_api.get_transactions(royalty_address, limit=25)
        
        # DEBUG DETTAGLIATO ARRAY
        print(f"[DEBUG] Transactions variable type: {type(transactions)}")
        print(f"[DEBUG] Transactions is None? {transactions is None}")
        print(f"[DEBUG] Transactions is list? {isinstance(transactions, list)}")
        
        if transactions is None:
            print(f"[DEBUG] ❌ get_transactions() returned None (API error?)", flush=True)
            return None
        
        if not transactions:  # Lista vuota
            print(f"[DEBUG] ✅ get_transactions() returned EMPTY list []", flush=True)
            print(f"[DEBUG] This means: TON Center API responded with 200 but no transactions for this address", flush=True)
            print(f"[DEBUG] Address {royalty_address} may have 0 transactions or wrong address", flush=True)
            return None
        
        print(f"[royalty_trs] Found {len(transactions)} transactions for {royalty_address[-6:]}", flush=True)
        
        # DEBUG: Mostra prime 3 transazioni
        print(f"[DEBUG] First 3 transactions sample:")
        for i, tx in enumerate(transactions[:3]):
            tx_time = tx.get("utime", 0)
            tx_hash = tx.get("hash", "")[:10] + "..." if tx.get("hash") else "no-hash"
            tx_type = "IN" if tx.get("in_msg") else "OUT"
            print(f"  TX{i}: utime={tx_time} ({time.ctime(tx_time) if tx_time > 0 else 'N/A'})")
            print(f"       hash: {tx_hash}, type: {tx_type}")
            
            if tx.get("in_msg"):
                source = tx["in_msg"].get("source", {}).get("address", "no-source")
                print(f"       source: {source[-8:] if source else 'no-source'}")
        
        # STATISTICHE
        stats = {
            "total": len(transactions),
            "already_processed": 0,      # tx_time <= last_utime
            "new_transactions": 0,       # tx_time > last_utime
            "new_no_source": 0,          # nuove ma senza source address
            "new_not_sale": 0,           # nuove ma non vendite NFT
            "new_invalid_sale": 0,       # nuove con sale data invalido
            "new_nft_sales": 0,          # nuove vendite NFT valide
            "new_monitored": 0,          # nuove in collezioni monitorate
            "utime_range": {
                "min": min(tx.get("utime", 0) for tx in transactions) if transactions else 0,
                "max": max(tx.get("utime", 0) for tx in transactions) if transactions else 0,
            }
        }
        
        latest_utime = last_utime
        processed_count = 0
        
        # 3. PROCESS TRANSACTIONS
        for tx in transactions:
            tx_time = tx.get("utime", 0)
            
            # FILTRO 1: UTIME (già processate?)
            if tx_time <= last_utime:
                stats["already_processed"] += 1
                continue
            
            # NUOVA TRANSAZIONE
            stats["new_transactions"] += 1
            
            if tx_time > latest_utime:
                latest_utime = tx_time
            
            in_msg = tx.get("in_msg", {})
            source = in_msg.get("source", {}).get("address")
            
            # FILTRO 2: SOURCE ADDRESS
            if not source:
                stats["new_no_source"] += 1
                print(f"[DEBUG] ⚠️ New transaction {tx_time} has NO source address", flush=True)
                continue
            
            print(f"[royalty_trs] Processing transaction from {source[-6:]} (utime: {tx_time})", flush=True)
            
            # FILTRO 3: È UNA VENDITA NFT?
            stack, method_used = await toncenter_api.get_sale_data_with_retry(source)
            
            if not stack:
                stats["new_not_sale"] += 1
                print(f"[royalty_trs] ❌ No sale data found for {source[-6:]} (not NFT sale)", flush=True)
                continue
            
            print(f"[royalty_trs] ✅ Success with {method_used}! Stack has {len(stack)} items", flush=True)
            
            # FILTRO 4: PARSING DATI VENDITA
            sale_data = parse_sale_stack(stack)
            
            if not sale_data or not sale_data[1]:
                stats["new_invalid_sale"] += 1
                print(f"[royalty_trs] ❌ Invalid sale data", flush=True)
                continue
            
            # VENDITA NFT VALIDA!
            stats["new_nft_sales"] += 1
            sale_type = sale_data[0]
            print(f"[DEBUG] 🎯 NFT SALE FOUND! Type: {sale_type}")
            
            nft_address = sale_data[4] if len(sale_data) > 4 else None
            
            if not nft_address:
                continue
            
            print(f"[royalty_trs] Fetching NFT data for {nft_address[-6:]}...", flush=True)
            nft_data = await get_nft_data(nft_address)
            
            if not nft_data:
                print(f"[royalty_trs] ❌ NFT data not found for {nft_address[-6:]}", flush=True)
                continue
            
            collection_address = nft_data[1]
            
            # FILTRO 5: COLLEZIONE MONITORATA?
            if collection_address not in collections_list:
                print(f"[royalty_trs] ❌ Collection {collection_address[-6:]} not monitored", flush=True)
                continue
            
            stats["new_monitored"] += 1
            print(f"[royalty_trs] ✅ Collection {collection_address[-6:]} is monitored!", flush=True)
            
            print(f"[royalty_trs] Fetching floor for collection {collection_address[-6:]}...", flush=True)
            floor_data = await get_collection_floor(collection_address)
            floor_price, floor_link = floor_data
            
            # INVIO NOTIFICA
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
        
        # REPORT STATISTICHE FINALE
        print(f"\n[STATS] ======= TRANSACTION ANALYSIS =======")
        print(f"[STATS] Total transactions from API: {stats['total']}")
        print(f"[STATS] Time range: {stats['utime_range']['min']} → {stats['utime_range']['max']}")
        print(f"[STATS] Already processed (utime filter): {stats['already_processed']}")
        print(f"[STATS] New transactions found: {stats['new_transactions']}")
        print(f"[STATS]   - No source address: {stats['new_no_source']}")
        print(f"[STATS]   - Not NFT sales: {stats['new_not_sale']}")
        print(f"[STATS]   - Invalid sale data: {stats['new_invalid_sale']}")
        print(f"[STATS]   - Valid NFT sales: {stats['new_nft_sales']}")
        print(f"[STATS]   - In monitored collections: {stats['new_monitored']}")
        print(f"[STATS] Final notifications sent: {processed_count}")
        print(f"[STATS] Latest utime this cycle: {latest_utime}")
        print(f"[STATS] ====================================\n")
        
        # Aggiorna lastUtime solo se abbiamo processato qualcosa
        if processed_count > 0 or stats['new_transactions'] > 0:
            return latest_utime if latest_utime > last_utime else None
        else:
            return None
    
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
                
                results = []
                for addr in royalty_addresses:
                    result = await royalty_trs(addr)
                    if result:
                        results.append(result)
                
                if results:
                    last_utime = max(results)
                    write_last_utime(last_utime)
                    print(f"[CYCLE #{cycle_count}] ✅ Updated lastUtime: {last_utime}", flush=True)
                
                print(f"[CYCLE #{cycle_count}] Finished. Sleeping 180s (3min)...", flush=True)
                
                for i in range(6):
                    await asyncio.sleep(30)
                    minutes = (i + 1) * 0.5
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
    
    try:
        run_in_background()
        print("[MAIN] ✅ Web server started", flush=True)
        await asyncio.sleep(2)
    except Exception as e:
        print(f"[MAIN] ⚠️ Web server failed: {e}", flush=True)
    
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
