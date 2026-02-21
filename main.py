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
    from secretData import toncenter_api_key, bot_token as telegram_bot_token, notify_chat as telegram_chat_id
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
    from tgMessage import tg_message_async, send_telegram_message
    print("[DEBUG] ✅ tgMessage imported", flush=True)
except Exception as e:
    print(f"[DEBUG] ❌ tgMessage import failed: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from functions import parse_sale_stack, convert_ton_to_usd
    from functions import get_nft_from_sale_contract, extract_nft_from_comment
    from functions import get_nft_from_transaction_hash
    from functions import get_nft_from_transaction_messages # FIX: recupero NFT da messaggi
    from functions import get_nft_from_sale_contract_v2
    from functions import get_trace_id_from_tx
    from functions import get_nft_from_trace_via_tonapi
    from functions import get_nft_from_transaction_actions
    from functions import get_sale_data_v2
    from functions import get_sale_data_via_tonapi
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

# Helper function to safely access transaction data
def safe_tx_get(tx, key, default=None):
    """
    Safely get a value from transaction, handling multiple data types
    """
    if isinstance(tx, dict):
        return tx.get(key, default)
    elif isinstance(tx, list) and len(tx) > 0:
        # If tx is a list, maybe it's a simple array of values
        try:
            # Try to convert key to index
            idx = int(key) if isinstance(key, str) and key.isdigit() else key
            if isinstance(idx, int) and 0 <= idx < len(tx):
                return tx[idx]
        except:
            pass
        return default
    elif isinstance(tx, str):
        # If transaction is a string, log it and return default
        print(f"[WARN] Transaction is a string, not a dict: {tx[:50]}...")
        return default
    else:
        print(f"[WARN] Unknown transaction type: {type(tx)}")
        return default

class TonCenterAPI:
    
    def __init__(self):
        # ✅ USA CORRETTAMENTE L'API V3
        self.base_url = TONCENTER_API_V3  # "https://toncenter.com/api/v3"
        
        self.headers = TONCENTER_HEADERS
        self.timeout = HTTP_TIMEOUT
        self.min_request_interval = TONCENTER_RATE_LIMIT
        self.last_request_time = 0
        
        print(f"[DEBUG] Using API: {self.base_url}")
        print(f"[DEBUG] API Key present: {'Yes' if toncenter_api_key else 'No (rate limited)'}")

    async def _rate_limit(self):
        """Assicura almeno 1 secondo tra le richieste"""
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < 1.0:
            await asyncio.sleep(1.0 - time_since_last)
        self.last_request_time = time.time()
    
    async def get_transactions(self, address: str, limit: int = 25) -> list:
        await self._rate_limit()
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
        await self._rate_limit()
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

# Bot start time for uptime calculation
BOT_START_TIME = time.time()

def get_bot_uptime() -> str:
    """Calculate bot uptime in human readable format"""
    uptime = time.time() - BOT_START_TIME
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    seconds = int(uptime % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

async def send_example_sale_notification(chat_id: str = None):
    """Send an example NFT sale notification"""
    try:
        # Example data for a fake NFT sale
        example_data = {
            "sale_type": "SaleFixPrice",
            "seller": "EQCvA...6t3p",
            "buyer": "EQDgF...k9j8",
            "nft_address": "EQBYI...xY7p",
            "nft_name": "TON Punks #1234",
            "price": 15.5,  # TON
            "collection_name": "TON Punks",
            "marketplace_url": "https://getgems.io/collection/EQBvA...z1q6",
            "floor_price": 14.2,
            "floor_link": "https://getgems.io/collection/EQBvA...z1q6"
        }
        
        # Convert price to USD
        try:
            price_usd = await convert_ton_to_usd(example_data["price"])
            price_str = f"{example_data['price']:.2f} TON (≈${price_usd:.2f})"
        except:
            price_str = f"{example_data['price']:.2f} TON"
        
        # Create example message
        message = f"🎨 *EXAMPLE NFT SALE*\n\n"
        message += f"🏷️ *NFT:* {example_data['nft_name']}\n"
        message += f"📦 *Collection:* {example_data['collection_name']}\n"
        message += f"💰 *Price:* {price_str}\n"
        message += f"📊 *Floor Price:* {example_data['floor_price']:.2f} TON\n"
        message += f"👤 *Seller:* `{example_data['seller'][:8]}...`\n"
        message += f"🤝 *Buyer:* `{example_data['buyer'][:8]}...`\n"
        message += f"🔗 *View NFT:* [Getgems]({example_data['marketplace_url']})\n\n"
        message += f"📈 *This is an example notification*\n"
        message += f"Real sales will look similar to this!"
        
        # Send the message
        if chat_id:
            await send_telegram_message(message, chat_id=chat_id)
        else:
            # Send to default chat if no specific chat_id provided
            await send_telegram_message(message)
        
        print(f"[EXAMPLE] Example notification sent", flush=True)
        return True
        
    except Exception as e:
        print(f"[EXAMPLE] Error sending example: {e}", flush=True)
        return False

async def handle_telegram_command(command: str, chat_id: str, message_id: str = None):
    """Handle Telegram commands from users"""
    try:
        print(f"[TELEGRAM] Handling command: {command} from chat {chat_id}", flush=True)
        
        command = command.lower().strip()
        
        if command == "/start" or command == "/start@ton_nft_bot":
            message = "🤖 *Welcome to TON NFT Sales Bot!*\n\n"
            message += "I monitor NFT sales on the TON blockchain and send notifications when sales happen in your monitored collections.\n\n"
            message += "📋 *Available commands:*\n"
            message += "• /start - Welcome message\n"
            message += "• /help - Show all commands\n"
            message += "• /status - Bot status and stats\n"
            message += "• /example - Example NFT sale notification\n"
            message += "• /addresses - Show monitored royalty addresses\n"
            message += "• /collections - Show monitored collections\n"
            message += "• /ping - Check if bot is alive\n\n"
            message += "🔔 I'll automatically notify you when NFT sales occur!\n"
            message += "Bot is powered by TON Center API v3."
            
        elif command == "/help" or command == "/help@ton_nft_bot":
            message = "📋 *Available Commands:*\n\n"
            message += "• /start - Welcome message and introduction\n"
            message += "• /help - Show this help message\n"
            message += "• /status - Check bot status and statistics\n"
            message += "• /example - Send example NFT sale notification\n"
            message += "• /addresses - List monitored royalty addresses\n"
            message += "• /collections - List monitored NFT collections\n"
            message += "• /ping - Check if the bot is responsive\n\n"
            message += "🔄 *Bot cycles every 3 minutes*\n"
            message += "Checking for new NFT sales automatically!"
            
        elif command == "/status" or command == "/status@ton_nft_bot":
            last_utime = read_last_utime()
            last_time_str = time.ctime(last_utime) if last_utime > 0 else "Never"
            uptime_str = get_bot_uptime()
            
            message = "📊 *Bot Status Report*\n\n"
            message += f"⏱️ *Uptime:* {uptime_str}\n"
            message += f"🕒 *Last Check:* {last_time_str}\n"
            message += f"📍 *Royalty Addresses:* {len(royalty_addresses)}\n"
            message += f"🎨 *Collections Monitored:* {len(collections_list)}\n"
            message += f"🌐 *API:* TON Center v3\n"
            message += f"🔑 *API Key:* {'✅ Present' if toncenter_api_key else '⚠️ Not set (rate limited)'}\n"
            message += f"⏳ *Next Check:* Every 3 minutes\n\n"
            message += "✅ *Bot is running normally*"
            
        elif command == "/example" or command == "/example@ton_nft_bot":
            # Send example notification
            success = await send_example_sale_notification(chat_id)
            if success:
                return  # Message already sent by send_example_sale_notification
            else:
                message = "❌ Could not send example notification. Please try again later."
                
        elif command == "/addresses" or command == "/addresses@ton_nft_bot":
            if not royalty_addresses:
                message = "📭 No royalty addresses are currently being monitored."
            else:
                message = f"📍 *Monitored Royalty Addresses* ({len(royalty_addresses)}):\n\n"
                for i, addr in enumerate(royalty_addresses[:10]):  # Show max 10
                    message += f"{i+1}. `{addr}`\n"
                
                if len(royalty_addresses) > 10:
                    message += f"\n... and {len(royalty_addresses) - 10} more addresses"
                
                message += "\n\n👑 These addresses receive royalty payments from NFT sales."
                
        elif command == "/collections" or command == "/collections@ton_nft_bot":
            if not collections_list:
                message = "🎨 No NFT collections are currently being monitored."
            else:
                message = f"🎨 *Monitored NFT Collections* ({len(collections_list)}):\n\n"
                for i, addr in enumerate(collections_list[:10]):  # Show max 10
                    short_addr = addr[:8] + "..." + addr[-8:] if len(addr) > 16 else addr
                    message += f"{i+1}. `{short_addr}`\n"
                
                if len(collections_list) > 10:
                    message += f"\n... and {len(collections_list) - 10} more collections"
                
                message += "\n\n🔔 I'll notify you when NFTs from these collections are sold!"
                
        elif command == "/ping" or command == "/ping@ton_nft_bot":
            message = "🏓 *Pong!*\n\n"
            message += f"✅ Bot is alive and responding\n"
            message += f"⏱️ Uptime: {get_bot_uptime()}\n"
            message += f"🕒 Current time: {time.strftime('%H:%M:%S UTC')}\n"
            message += "🎯 Ready to monitor NFT sales!"
            
        
        await send_telegram_message(message, chat_id=chat_id, reply_to_message_id=message_id)
        print(f"[TELEGRAM] Command response sent for: {command}", flush=True)
        
    except Exception as e:
        print(f"[TELEGRAM] Error handling command {command}: {e}", flush=True)
        try:
            error_msg = "❌ Error processing command. Please try again."
            await send_telegram_message(error_msg, chat_id=chat_id, reply_to_message_id=message_id)
        except:
            pass

async def telegram_polling_handler():
    """Handle Telegram commands via polling"""
    try:
        if not telegram_bot_token:
            print("[TELEGRAM] No bot token configured, polling disabled", flush=True)
            return
        
        print(f"[TELEGRAM] Starting polling handler for bot", flush=True)
        
        # Bot info
        bot_username = None
        try:
            # Get bot info
            bot_info_url = f"https://api.telegram.org/bot{telegram_bot_token}/getMe"
            async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
                async with session.get(bot_info_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("ok"):
                            bot_username = data["result"].get("username")
                            print(f"[TELEGRAM] Bot username: @{bot_username}", flush=True)
        except Exception as e:
            print(f"[TELEGRAM] Error getting bot info: {e}", flush=True)
        
        last_update_id = 0
        
        while True:
            try:
                # Get updates from Telegram
                updates_url = f"https://api.telegram.org/bot{telegram_bot_token}/getUpdates"
                params = {
                    "offset": last_update_id + 1,
                    "timeout": 30,
                    "allowed_updates": ["message"]
                }
                
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=35)) as session:
                    async with session.get(updates_url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get("ok") and data.get("result"):
                                updates = data["result"]
                                
                                for update in updates:
                                    last_update_id = update["update_id"]
                                    
                                    if "message" in update and "text" in update["message"]:
                                        message = update["message"]
                                        chat_id = str(message["chat"]["id"])
                                        text = message["text"].strip()
                                        message_id = message.get("message_id")
                                        
                                        # Check if message is a command
                                        if text.startswith("/"):
                                            print(f"[TELEGRAM] Received command: {text} from chat {chat_id}", flush=True)
                                            await handle_telegram_command(text, chat_id, message_id)
                                        
                
                # Small delay between polling
                await asyncio.sleep(1)
                
            except asyncio.TimeoutError:
                # Timeout is normal for long polling
                continue
            except aiohttp.ClientError as e:
                print(f"[TELEGRAM] HTTP error in polling: {e}", flush=True)
                await asyncio.sleep(5)
            except Exception as e:
                print(f"[TELEGRAM] Error in polling handler: {e}", flush=True)
                await asyncio.sleep(5)
                
    except Exception as e:
        print(f"[TELEGRAM] Fatal error in polling handler: {e}", flush=True)
        traceback.print_exc()

async def royalty_trs(royalty_address: str):
    try:
        last_utime = read_last_utime()
        print(f"\n[DEBUG] 🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴")
        print(f"[DEBUG] 🔴 ROYALTY TRS START - {time.strftime('%H:%M:%S')}")
        print(f"[DEBUG] 🔴 Address: {royalty_address[-12:]}")
        print(f"[DEBUG] 🔴 Last utime: {last_utime} ({time.ctime(last_utime)})")
        print(f"[DEBUG] 🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n")
        
        transactions = await toncenter_api.get_transactions(royalty_address, limit=25)
        
        if not transactions:
            print(f"[DEBUG] ⚠️ No transactions found")
            return None
        
        print(f"[DEBUG] 📥 Received {len(transactions)} transactions")
        
        utimes = []
        processed_count = 0
        
        for idx, tx in enumerate(transactions[::-1]):
            tx_time = tx.get('now', 0)
            tx_hash_full = tx.get('hash', '')
            tx_hash_short = tx_hash_full[:16] if tx_hash_full else 'unknown'
            
            print(f"\n[DEBUG] ===== TX [{idx}] ===================")
            print(f"[DEBUG] Hash: {tx_hash_short}...")
            print(f"[DEBUG] Time: {tx_time} ({time.ctime(tx_time)})")
            
            in_msg = tx.get('in_msg', {})
            source_address = in_msg.get('source')
            
            # 🟢 SINGLE CONTINUE - LIKE PYTONLIB!
            if tx_time <= last_utime or not source_address:
                print(f"[DEBUG] ⏭️ TX {idx}: Skipped (timestamp or empty source)")
                continue
            
            print(f"[DEBUG] ✅ Source address: {source_address[-12:] if source_address else 'None'}")
            print(f"[DEBUG]    Value: {int(in_msg.get('value', 0)) / 1e9:.4f} TON")

            trace_id_b64 = tx.get('trace_id')
            trace_id_for_tonapi = None
            trace_id_hex_for_debug = None
            trace_id_raw = None
            
            # ✅ AGGIUNGI tx_hash_b64 QUI!
            tx_hash_b64 = tx.get('hash')

            if trace_id_b64:
                print(f"[DEBUG] ✅ Trace ID (Base64 originale): {trace_id_b64[:30]}...")
                trace_id_for_tonapi = trace_id_b64
                try:
                    import base64
                    trace_id_hex_for_debug = base64.b64decode(trace_id_b64).hex()
                    print(f"[DEBUG]    (Hex per debug): {trace_id_hex_for_debug[:30]}...")
                except Exception as e:
                    print(f"[DEBUG]    (Decodifica hex fallita: {e})")
                
            else:
                print(f"[DEBUG] ⚠️ No trace ID in this transaction")
                trace_id_for_tonapi = None
                trace_id_hex_for_debug = None
            
            # 🟢 1. GET SALE DATA - PRIMA PROVA CON V2 (dati sempre presenti!)
            print(f"[DEBUG] 🔍 Calling get_sale_data_v2() on {source_address[-12:]}...")
            stack = await get_sale_data_v2(source_address)
            
            if not stack:
                # Se v2 fallisce, prova con TonAPI come fallback
                print(f"[DEBUG] ⏭️ v2 failed, trying TonAPI...")
                stack = await get_sale_data_via_tonapi(source_address)
            
            if stack:
                print(f"[DEBUG] ✅ get_sale_data() success! Stack size: {len(stack)}")
                
                # 🟢 2. PARSE SALE STACK
                sale_data = parse_sale_stack(stack)
                
                if sale_data and sale_data[1]:  # is_complete = True (SOLD!)
                    print(f"[DEBUG] ✅ Sale completed! Type: {sale_data[0]}, Price: {sale_data[6] if len(sale_data) > 6 else 0} TON")
                    
                    nft_address = sale_data[4] if len(sale_data) > 4 else None
                    
                    if nft_address:
                        print(f"[DEBUG] ✅ NFT address found in stack: {nft_address[-12:]}")
                    else:
                        print(f"[DEBUG] ⚠️ NFT address MISSING from stack")
                        
                        # 🟢 3. FALLBACK: source_address potrebbe essere l'NFT stesso
                        if len(stack) == 1:
                            print(f"[DEBUG] 🔍 Stack size 1 - using source_address as NFT address")
                            nft_address = source_address
                            print(f"[DEBUG] ✅ NFT address from source: {nft_address[-12:]}")
                    
                    if nft_address:
                        print(f"[DEBUG] 📥 Fetching NFT data for {nft_address[-12:]}...")
                        nft_data = await get_nft_data(nft_address)
                        
                        if nft_data and nft_data[0] and nft_data[1]:
                            collection_address = nft_data[1]
                            print(f"[DEBUG] ✅ NFT data retrieved! Collection: {collection_address[-12:] if collection_address else 'None'}")
                            
                            # 🟢 5. CHECK MONITORED COLLECTION
                            if collection_address in collections_list:
                                print(f"[DEBUG] ✅✅✅ COLLECTION MONITORED! {collection_address[-12:]}")
                                
                                # 🟢 6. GET FLOOR PRICE
                                print(f"[DEBUG] 📊 Fetching floor price...")
                                floor_price, floor_link = await get_collection_floor(collection_address)
                                print(f"[DEBUG]    Floor: {floor_price} TON" if floor_price else "[DEBUG]    Floor: None")
                                
                                # 🟢 7. SEND NOTIFICATION
                                try:
                                    print(f"[DEBUG] 📨 SENDING TELEGRAM NOTIFICATION...")
                                    await tg_message_async(
                                        sale_data[0],
                                        sale_data[3] if len(sale_data) > 3 else None,
                                        nft_address,
                                        sale_data[5] if len(sale_data) > 5 else None,
                                        nft_data[2],
                                        sale_data[6] if len(sale_data) > 6 else 0,
                                        nft_data[3] if len(nft_data) > 3 else "Unknown NFT",
                                        nft_data[4] if len(nft_data) > 4 else "",
                                        floor_price,
                                        floor_link
                                    )
                                    print(f"[DEBUG] ✅✅✅ NOTIFICATION SENT SUCCESSFULLY!")
                                    utimes.append(tx_time)
                                    processed_count += 1
                                    
                                except Exception as e:
                                    print(f"[DEBUG] ❌❌❌ NOTIFICATION FAILED: {e}")
                                    import traceback
                                    traceback.print_exc()
                            else:
                                print(f"[DEBUG] ⚠️ Collection NOT monitored: {collection_address[-12:] if collection_address else 'None'}")
                                print(f"[DEBUG]    Monitored collections: {[c[-12:] for c in collections_list]}")
                        else:
                            print(f"[DEBUG] ❌ Failed to get NFT data")
                            if not nft_data:
                                print(f"[DEBUG]    nft_data is None")
                            else:
                                if not nft_data[0]:
                                    print(f"[DEBUG]    init flag is False")
                                if not nft_data[1]:
                                    print(f"[DEBUG]    collection address is missing")
                    else:
                        print(f"[DEBUG] ❌ No NFT address available - skipping transaction")
                else:
                    print(f"[DEBUG] ⏭️ Sale not completed (is_complete=False)")
            else:
                print(f"[DEBUG] ⏭️ Not a sale contract (get_sale_data returned None)")
        
        # 🟢 FINAL REPORT
        print(f"\n[DEBUG] 🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴")
        print(f"[DEBUG] 🔴 CYCLE COMPLETE - {time.strftime('%H:%M:%S')}")
        print(f"[DEBUG] 🔴 Processed: {processed_count}")
        print(f"[DEBUG] 🔴 Utimes: {utimes}")
        print(f"[DEBUG] 🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n")
        
        if utimes:
            new_utime = max(utimes)
            write_last_utime(new_utime)
            print(f"[DEBUG] 💾 Saved lastUtime: {new_utime} ({time.ctime(new_utime)})")
            return new_utime
        
        return None
        
    except Exception as e:
        print(f"[royalty_trs] ❌ CRITICAL ERROR: {e}")
        import traceback
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
    print("✅ Telegram commands enabled", flush=True)
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
    
    # Start Telegram polling handler in background
    if telegram_bot_token:
        asyncio.create_task(telegram_polling_handler())
        print("[MAIN] ✅ Telegram command handler started", flush=True)
    else:
        print("[MAIN] ⚠️ Telegram bot token not configured, commands disabled", flush=True)
    
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
