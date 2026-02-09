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
from config import TONCENTER_RATE_LIMIT, TONCENTER_API_V3
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
    from config import current_path, royalty_addresses, collections_list
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
        # ✅ USA CORRETTAMENTE L'API V3
        self.base_url = TONCENTER_API_V3  # "https://toncenter.com/api/v3"
        
        self.headers = TONCENTER_HEADERS
        self.timeout = HTTP_TIMEOUT
        self.min_request_interval = TONCENTER_RATE_LIMIT
        
        print(f"[DEBUG] Using API: {self.base_url}")
        print(f"[DEBUG] API Key present: {'Yes' if toncenter_api_key else 'No (rate limited)'}")
    
    async def get_transactions(self, address: str, limit: int = 25) -> list:
        """Fetch transactions using correct TON Center API v3 endpoint and parameters - FIXED VERSION"""
        
        print(f"\n[DEBUG] get_transactions called for: {address[-8:]}")
        print(f"[DEBUG] Base URL: {self.base_url}")
        
        # Endpoint corretto per v3
        endpoint = "/transactions"
        url = f"{self.base_url}{endpoint}"
        
        # Test diverse strategie per la v3
        test_cases = [
            {
                "name": "desc_with_archival",
                "params": {
                    "account": address,
                    "limit": limit,
                    "sort": "desc",
                    "archival": "true"
                }
            },
            {
                "name": "desc_no_archival",
                "params": {
                    "account": address,
                    "limit": limit,
                    "sort": "desc",
                    "archival": "false"
                }
            }
        ]
        
        for test_case in test_cases:
            try:
                print(f"\n[DEBUG] Testing strategy: {test_case['name']}")
                print(f"[DEBUG] Request URL: {url}")
                print(f"[DEBUG] Request params: {test_case['params']}")
                
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.get(
                        url, 
                        headers=self.headers, 
                        params=test_case['params']
                    ) as response:
                        
                        status = response.status
                        print(f"[DEBUG] Response status: {status}")
                        
                        if status == 200:
                            # PRIMA: Leggi la risposta RAW per debug
                            raw_response = await response.text()
                            print(f"[DEBUG] Raw response length: {len(raw_response)} chars")
                            print(f"[DEBUG] First 500 chars of response: {raw_response[:500]}")
                            
                            try:
                                data = await response.json()
                                print(f"[DEBUG] Successfully parsed JSON")
                                
                                # ANALISI DELLA STRUTTURA DELLA RISPOSTA
                                print(f"[DEBUG] Response keys: {list(data.keys())}")
                                
                                # CERCA LE TRANSAZIONI IN VARI PUNTI POSSIBILI
                                txs = []
                                
                                # Caso 1: direttamente in "transactions"
                                if "transactions" in data:
                                    txs = data["transactions"]
                                    print(f"[DEBUG] Found {len(txs)} transactions in 'transactions' key")
                                
                                # Caso 2: in "result" -> "transactions"
                                elif "result" in data and isinstance(data["result"], dict):
                                    if "transactions" in data["result"]:
                                        txs = data["result"]["transactions"]
                                        print(f"[DEBUG] Found {len(txs)} transactions in 'result.transactions'")
                                
                                # Caso 3: la risposta è direttamente un array
                                elif isinstance(data, list):
                                    txs = data
                                    print(f"[DEBUG] Response is direct array with {len(txs)} items")
                                
                                print(f"[TON Center] ✅ Got {len(txs)} transactions with {test_case['name']}")
                                
                                if txs:
                                    # DEBUG DETTAGLIATO DELLA PRIMA TRANSAZIONE
                                    print(f"[DEBUG] Analyzing first transaction structure:")
                                    
                                    if isinstance(txs[0], dict):
                                        print(f"[DEBUG] First TX is a dict with keys: {list(txs[0].keys())}")
                                        
                                        # Stampa i valori chiave
                                        important_keys = ["now", "hash", "lt", "account", "in_msg", "out_msgs"]
                                        for key in important_keys:
                                            if key in txs[0]:
                                                value = txs[0][key]
                                                print(f"  {key}: {type(value)} = {str(value)[:100]}")
                                        
                                        # Analisi speciale per 'account'
                                        if "account" in txs[0]:
                                            account_data = txs[0]["account"]
                                            print(f"  account type: {type(account_data)}")
                                            if isinstance(account_data, dict):
                                                print(f"  account keys: {list(account_data.keys())}")
                                                if "address" in account_data:
                                                    print(f"  account.address: {account_data['address'][-8:]}")
                                        
                                        # Analisi speciale per 'in_msg'
                                        if "in_msg" in txs[0]:
                                            in_msg = txs[0]["in_msg"]
                                            print(f"  in_msg type: {type(in_msg)}")
                                            if isinstance(in_msg, dict):
                                                print(f"  in_msg keys: {list(in_msg.keys())}")
                                                if "source" in in_msg:
                                                    source = in_msg["source"]
                                                    print(f"  source type: {type(source)}")
                                                    if isinstance(source, dict) and "address" in source:
                                                        print(f"  source.address: {source['address'][-8:]}")
                                    
                                    elif isinstance(txs[0], list):
                                        print(f"[DEBUG] First TX is a list with {len(txs[0])} items")
                                        for i, item in enumerate(txs[0][:5]):
                                            print(f"  [{i}] type: {type(item)}, value: {str(item)[:50]}")
                                    
                                    elif isinstance(txs[0], str):
                                        print(f"[DEBUG] First TX is a string: {txs[0][:100]}")
                                    
                                    return txs
                                else:
                                    print(f"[TON Center] ⚠️ 0 transactions in parsed data")
                                    # Mostra cosa c'è nella risposta
                                    print(f"[DEBUG] Full response structure:")
                                    print(json.dumps(data, indent=2)[:1000])
                                    continue
                            
                            except json.JSONDecodeError as e:
                                print(f"[DEBUG] ❌ JSON decode error: {e}")
                                print(f"[DEBUG] Raw response that failed to parse: {raw_response[:200]}")
                                continue
                            except Exception as e:
                                print(f"[DEBUG] ❌ Error parsing response: {e}")
                                continue
                        
                        elif status == 429:
                            print(f"[TON Center] ⛔ Rate limit hit with {test_case['name']}")
                            await asyncio.sleep(2)
                            continue
                        else:
                            error_text = await response.text()
                            print(f"[DEBUG] API Error {status}: {error_text[:200]}")
                            continue
            
            except asyncio.TimeoutError:
                print(f"[DEBUG] Timeout with {test_case['name']}")
                continue
            except aiohttp.ClientError as e:
                print(f"[DEBUG] HTTP error with {test_case['name']}: {str(e)[:100]}")
                continue
            except Exception as e:
                print(f"[DEBUG] Unexpected error with {test_case['name']}: {type(e).__name__}: {str(e)[:100]}")
                continue
        
        print(f"[TON Center] ❌ No transactions found with any strategy")
        return []
    
    async def run_get_method(self, address: str, method: str, stack: list = None) -> list:
        """Execute a get method on a smart contract - API v3 COMPATIBLE"""
        try:
            print(f"[DEBUG] run_get_method called: address={address[-8:]}, method={method}")
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # ✅ Endpoint corretto per v3
                url = f"{self.base_url}/runGetMethod"
                
                # ✅ Payload corretto per v3
                payload = {
                    "address": address,
                    "method": method,
                    "stack": stack if stack is not None else []
                }
                
                print(f"[DEBUG] run_get_method payload: {json.dumps(payload, indent=2)[:200]}...")
                
                async with session.post(url, headers=self.headers, json=payload) as response:
                    
                    status = response.status
                    print(f"[DEBUG] run_get_method status: {status}")
                    
                    if status == 429:
                        print(f"[TON Center] ⛔ Rate limit in get_method {method}", flush=True)
                        return None
                    
                    if status != 200:
                        error_text = await response.text()
                        print(f"[DEBUG] run_get_method error {status}: {error_text[:200]}")
                        return None
                    
                    data = await response.json()
                    print(f"[DEBUG] run_get_method raw response keys: {list(data.keys())}")
                    
                    # ✅ Controlla il formato di risposta della v3
                    if "ok" in data:
                        # Formato v3: {"ok": true, "result": {"stack": [...]}}
                        if data.get("ok") and "result" in data:
                            result_stack = data["result"].get("stack", [])
                            print(f"[TON Center] ✅ get_method {method} succeeded (v3 format), stack size: {len(result_stack)}")
                            return result_stack
                        else:
                            print(f"[TON Center] ❌ get_method {method} failed (v3 format), ok={data.get('ok')}")
                            return None
                    
                    # Fallback: formato v2 legacy
                    elif "success" in data:
                        if data.get("success", False):
                            stack_data = data.get("stack", [])
                            print(f"[TON Center] ✅ get_method {method} succeeded (v2 legacy), stack size: {len(stack_data)}")
                            return stack_data
                        else:
                            print(f"[TON Center] ❌ get_method {method} failed (v2 legacy)")
                            return None
                    
                    # Altri formati possibili
                    elif "stack" in data:
                        stack_data = data.get("stack", [])
                        print(f"[TON Center] ✅ get_method {method} succeeded (direct stack), stack size: {len(stack_data)}")
                        return stack_data
                    
                    else:
                        print(f"[TON Center] ❌ Unknown response format for {method}")
                        print(f"[DEBUG] Full response: {json.dumps(data, indent=2)[:500]}")
                        return None
        
        except asyncio.TimeoutError:
            print(f"[TON Center] Timeout in get_method {method}", flush=True)
            return None
        except aiohttp.ClientError as e:
            print(f"[TON Center] HTTP error in get_method {method}: {e}", flush=True)
            return None
        except Exception as e:
            print(f"[TON Center] Error in get_method {method}: {e}", flush=True)
            traceback.print_exc()
            return None
    
    async def get_sale_data_with_retry(self, source_address: str) -> tuple:
        """Get sale data with retry logic - UPDATED FOR API v3"""
        methods = ['get_sale_data', 'get_offer_data', 'get_nft_data']  # Aggiunto get_nft_data come fallback
        
        for method in methods:
            print(f"\n[RETRY] Trying method: {method} for {source_address[-8:]}", flush=True)
            
            for attempt in range(3):  # 3 tentativi per metodo
                try:
                    stack = await self.run_get_method(source_address, method)
                    
                    if stack is not None:
                        print(f"[RETRY] ✅ {method} succeeded on attempt {attempt+1}", flush=True)
                        
                        # DEBUG: stampa la struttura dello stack
                        print(f"[DEBUG] Stack structure for {method}:")
                        for i, item in enumerate(stack[:5]):  # Mostra primi 5 elementi
                            print(f"  [{i}] type: {type(item)}, value: {str(item)[:100]}")
                        
                        return stack, method
                    
                    print(f"[RETRY] ❌ {method} returned None on attempt {attempt+1}", flush=True)
                    
                    if attempt < 2:
                        wait_time = 2 * (attempt + 1)  # Backoff esponenziale: 2, 4 secondi
                        print(f"[RETRY] Waiting {wait_time}s before retry...", flush=True)
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"[RETRY] ❌ {method} failed on final attempt", flush=True)
                        
                except Exception as e:
                    print(f"[RETRY] Exception in {method} attempt {attempt+1}: {e}", flush=True)
                    if attempt < 2:
                        await asyncio.sleep(2)
        
        print(f"[RETRY] ❌ All methods failed for {source_address[-8:]}", flush=True)
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
    """Check transactions for royalty address and process NFT sales - UPDATED FOR API v3"""
    try:
        # 1. READ lastUtime
        last_utime = read_last_utime()
        print(f"\n[DEBUG] Last utime from file: {last_utime} ({time.ctime(last_utime) if last_utime > 0 else 'epoch'})")
        
        # 2. FETCH TRANSACTIONS CON API V3
        print(f"[royalty_trs] Fetching transactions for {royalty_address[-8:]}...", flush=True)
        transactions = await toncenter_api.get_transactions(royalty_address, limit=25)
        
        # DEBUG
        print(f"[DEBUG] Transactions variable type: {type(transactions)}")
        print(f"[DEBUG] Is None? {transactions is None}")
        print(f"[DEBUG] Is list? {isinstance(transactions, list)}")
        print(f"[DEBUG] Length: {len(transactions) if transactions else 0}")
        
        if transactions is None:
            print(f"[DEBUG] ❌ get_transactions() returned None (API error?)", flush=True)
            return None
        
        if not transactions:
            print(f"[DEBUG] ✅ get_transactions() returned EMPTY list []", flush=True)
            print(f"[DEBUG] This means API v3 responded but found no transactions", flush=True)
            
            # Verifica aggiuntiva: prova un test diretto
            await test_direct_api_call(royalty_address)
            return None
        
        print(f"[royalty_trs] Found {len(transactions)} transactions for {royalty_address[-8:]}", flush=True)
        
        # MODIFICA: La v3 usa "now" invece di "utime"
        print(f"[DEBUG] First 3 transactions sample (API v3 format):")
        for i, tx in enumerate(transactions[:3]):
            tx_time = tx.get("now", 0)  # ✅ "now" in v3
            tx_hash = tx.get("hash", "")[:10] + "..." if tx.get("hash") else "no-hash"
            tx_lt = tx.get("lt", "N/A")
            
            print(f"  TX{i}: now={tx_time} ({time.ctime(tx_time) if tx_time > 0 else 'N/A'})")
            print(f"       hash: {tx_hash}, lt: {tx_lt}")
            
            if tx.get("in_msg"):
                source = tx["in_msg"].get("source", {}).get("address", "no-source")
                value = int(tx["in_msg"].get("value", 0)) / 1e9  # Converti nanoTON a TON
                print(f"       source: {source[-8:] if source else 'no-source'}, value: {value:.2f} TON")
        
        # STATISTICHE AGGIORNATE PER V3
        stats = {
            "total": len(transactions),
            "already_processed": 0,      # tx_time <= last_utime
            "new_transactions": 0,       # tx_time > last_utime
            "new_no_source": 0,          # nuove ma senza source address
            "new_not_sale": 0,           # nuove ma non vendite NFT
            "new_invalid_sale": 0,       # nuove con sale data invalido
            "new_nft_sales": 0,          # nuove vendite NFT valide
            "new_monitored": 0,          # nuove in collezioni monitorate
            "time_range": {
                "min": min(tx.get("now", 0) for tx in transactions) if transactions else 0,
                "max": max(tx.get("now", 0) for tx in transactions) if transactions else 0,
            }
        }
        
        latest_utime = last_utime
        processed_count = 0
        
        # 3. PROCESS TRANSACTIONS (con timestamp "now" invece di "utime")
        for tx in transactions:
            tx_time = tx.get("now", 0)  # ✅ Usa "now" invece di "utime"
            
            # FILTRO 1: TIMESTAMP
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
            
            print(f"[royalty_trs] Processing transaction from {source[-8:]} (time: {tx_time})", flush=True)
            
            # FILTRO 3: È UNA VENDITA NFT?
            stack, method_used = await toncenter_api.get_sale_data_with_retry(source)
            
            if not stack:
                stats["new_not_sale"] += 1
                print(f"[royalty_trs] ❌ No sale data found for {source[-8:]} (not NFT sale)", flush=True)
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
            
            print(f"[royalty_trs] Fetching NFT data for {nft_address[-8:]}...", flush=True)
            nft_data = await get_nft_data(nft_address)
            
            if not nft_data:
                print(f"[royalty_trs] ❌ NFT data not found for {nft_address[-8:]}", flush=True)
                continue
            
            collection_address = nft_data[1]
            
            # FILTRO 5: COLLEZIONE MONITORATA?
            if collection_address not in collections_list:
                print(f"[royalty_trs] ❌ Collection {collection_address[-8:]} not monitored", flush=True)
                continue
            
            stats["new_monitored"] += 1
            print(f"[royalty_trs] ✅ Collection {collection_address[-8:]} is monitored!", flush=True)
            
            print(f"[royalty_trs] Fetching floor for collection {collection_address[-8:]}...", flush=True)
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
                traceback.print_exc()
        
        # REPORT STATISTICHE FINALE
        print(f"\n[STATS] ======= TRANSACTION ANALYSIS (API v3) =======")
        print(f"[STATS] Total transactions from API: {stats['total']}")
        print(f"[STATS] Time range: {stats['time_range']['min']} → {stats['time_range']['max']}")
        print(f"[STATS] Already processed (time filter): {stats['already_processed']}")
        print(f"[STATS] New transactions found: {stats['new_transactions']}")
        print(f"[STATS]   - No source address: {stats['new_no_source']}")
        print(f"[STATS]   - Not NFT sales: {stats['new_not_sale']}")
        print(f"[STATS]   - Invalid sale data: {stats['new_invalid_sale']}")
        print(f"[STATS]   - Valid NFT sales: {stats['new_nft_sales']}")
        print(f"[STATS]   - In monitored collections: {stats['new_monitored']}")
        print(f"[STATS] Final notifications sent: {processed_count}")
        print(f"[STATS] Latest timestamp this cycle: {latest_utime}")
        print(f"[STATS] ==============================================\n")
        
        # Aggiorna lastUtime solo se abbiamo processato qualcosa
        if processed_count > 0 or stats['new_transactions'] > 0:
            return latest_utime if latest_utime > last_utime else None
        else:
            return None
    
    except Exception as e:
        print(f"[royalty_trs] CRITICAL Error for {royalty_address[-8:]}: {e}", flush=True)
        traceback.print_exc()
        return None

async def test_direct_api_call(address: str):
    """Test diretto per verificare che l'API v3 funzioni - FIXED VERSION"""
    try:
        print(f"\n[DIRECT TEST] Testing API v3 directly for {address[-8:]}")
        
        test_url = f"{TONCENTER_API_V3}/transactions"
        params = {
            "account": address,
            "limit": 5,
            "sort": "desc"
        }
        
        async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
            async with session.get(test_url, headers=TONCENTER_HEADERS, params=params) as response:
                print(f"[DIRECT TEST] Status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"[DIRECT TEST] Response keys: {list(data.keys())}")
                    
                    # CERCA TRANSAZIONI IN VARI PUNTI
                    txs = []
                    
                    # Caso 1: direttamente in "transactions"
                    if "transactions" in data:
                        txs = data["transactions"]
                        print(f"[DIRECT TEST] Found {len(txs)} transactions in 'transactions' key")
                    
                    # Caso 2: in "result" -> "transactions"
                    elif "result" in data and isinstance(data["result"], dict):
                        if "transactions" in data["result"]:
                            txs = data["result"]["transactions"]
                            print(f"[DIRECT TEST] Found {len(txs)} transactions in 'result.transactions'")
                    
                    print(f"[DIRECT TEST] Total transactions found: {len(txs)}")
                    
                    if txs:
                        print(f"[DIRECT TEST] Sample transaction structure:")
                        
                        # VERIFICA IL TIPO DELLA PRIMA TRANSAZIONE
                        first_tx = txs[0]
                        print(f"  Type of first TX: {type(first_tx)}")
                        
                        if isinstance(first_tx, dict):
                            print(f"  Keys in first TX: {list(first_tx.keys())}")
                            
                            # Stampa sicura dei valori (usa get solo se è dict)
                            safe_get = lambda obj, key: obj.get(key, 'N/A') if isinstance(obj, dict) else f'Not a dict: {type(obj)}'
                            
                            print(f"  Hash: {safe_get(first_tx, 'hash')[:15]}...")
                            print(f"  Time (now): {safe_get(first_tx, 'now')}")
                            
                            # Gestione sicura dell'account
                            account_data = safe_get(first_tx, 'account')
                            if isinstance(account_data, dict):
                                print(f"  Account address: {account_data.get('address', 'N/A')[-10:]}")
                            else:
                                print(f"  Account: {account_data}")
                        
                        elif isinstance(first_tx, list):
                            print(f"  First TX is a list with {len(first_tx)} items")
                            for i, item in enumerate(first_tx[:3]):
                                print(f"    [{i}]: type={type(item)}, value={str(item)[:50]}")
                        
                        elif isinstance(first_tx, str):
                            print(f"  First TX is a string: {first_tx[:100]}")
                    
                    else:
                        print(f"[DIRECT TEST] API returned success but empty transactions array")
                        print(f"[DIRECT TEST] Full response structure:")
                        print(json.dumps(data, indent=2)[:1000])
                        
                        # Stampa altri campi utili
                        if "total" in data:
                            print(f"[DIRECT TEST] Total count in response: {data['total']}")
                
                else:
                    error_text = await response.text()
                    print(f"[DIRECT TEST] Error: {error_text[:200]}")
    
    except Exception as e:
        print(f"[DIRECT TEST] Exception: {e}")
        traceback.print_exc()


async def scheduler():
    """Main bot loop - UPDATED LOG MESSAGES"""
    print("\n" + "=" * 60, flush=True)
    print("=== [SCHEDULER] Started (TON Center API v3 - Consistent) ===", flush=True)
    print(f"✅ API Version: v3 ({TONCENTER_API_V3})", flush=True)
    print("✅ All methods updated for API v3 compatibility", flush=True)
    print("=" * 60 + "\n", flush=True)
    
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            
            try:
                print(f"\n[CYCLE #{cycle_count}] Start at {time.strftime('%H:%M:%S')}", flush=True)
                print(f"[CYCLE #{cycle_count}] Using TON Center API v3", flush=True)
                
                results = []
                for addr in royalty_addresses:
                    print(f"[CYCLE #{cycle_count}] Processing address: {addr[-8:]}", flush=True)
                    result = await royalty_trs(addr)
                    if result:
                        results.append(result)
                
                if results:
                    last_utime = max(results)
                    write_last_utime(last_utime)
                    print(f"[CYCLE #{cycle_count}] ✅ Updated lastUtime: {last_utime}", flush=True)
                else:
                    print(f"[CYCLE #{cycle_count}] ⚠️ No new transactions to process", flush=True)
                
                print(f"[CYCLE #{cycle_count}] Finished. Sleeping 180s (3min)...", flush=True)
                
                for i in range(6):
                    await asyncio.sleep(30)
                    minutes = (i + 1) * 0.5
                    print(f"[HEARTBEAT] {minutes}min / 3min (API v3)", flush=True)
                    
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
    print("\n[MAIN] TON NFT Bot starting (TON Center API v3)...", flush=True)
    
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
