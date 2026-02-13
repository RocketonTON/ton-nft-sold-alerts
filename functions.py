# functions.py - TON Center API v3 COMPATIBLE
import aiohttp
import asyncio
import base64
import json
import re
from typing import Optional, Dict, Any, Tuple
from secretData import cmc_token
from config import tonorg_price_url, cmc_url, cmc_headers

# === TON CENTER API CONFIGURATION ===
from secretData import toncenter_api_key

TONCENTER_HEADERS = {
    "accept": "application/json",
    "Content-Type": "application/json"
}
if toncenter_api_key:
    TONCENTER_HEADERS["X-API-Key"] = toncenter_api_key

async def convert_ton_to_usd(ton: float) -> Optional[float]:
    """Convert TON to USD (async)"""
    try:
        # First try CoinGecko (free, reliable)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={'ids': 'the-open-network', 'vs_currencies': 'usd'},
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'the-open-network' in data and 'usd' in data['the-open-network']:
                        usd_price = data['the-open-network']['usd']
                        return round(float(ton) * usd_price, 2)
        
        # Fallback to CoinMarketCap if available
        if cmc_token:
            cmc_headers['X-CMC_PRO_API_KEY'] = cmc_token
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    cmc_url,
                    params={'slug': 'toncoin', 'convert': 'USD'},
                    headers=cmc_headers,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        ton_data = data.get('data', {})
                        if ton_data:
                            quote = ton_data.get('11419', {}).get('quote', {}).get('USD', {})
                            usd = quote.get('price', 0)
                            return round(float(ton) * usd, 2)
        
        # Final fallback: fixed approximate value
        return round(float(ton) * 7.5, 2)
        
    except Exception as e:
        print(f'[convert_ton_to_usd] Error: {e}')
        return None

# ============= FUNZIONI DI UTILITY PER LO STACK =============

def get_stack_value(item, default='0'):
    """Estrae il valore da uno stack item, sia dict (v3) che list (pytonlib)"""
    try:
        # CASO 1: Dict (API v3)
        if isinstance(item, dict):
            if 'value' in item:
                return item['value']
            elif 'num' in item:
                return item['num']
            elif 'cell' in item:
                return item['cell']
        
        # CASO 2: List (pytonlib)
        elif isinstance(item, list) and len(item) > 1:
            return item[1]
        
        # CASO 3: Stringa diretta
        elif isinstance(item, str):
            return item
        
        return default
    except:
        return default

def hex_to_int(value):
    """Converte hex in int, gestisce dict, list, string"""
    try:
        # Estrai il valore come stringa
        if isinstance(value, dict):
            hex_str = get_stack_value(value, '0')
        elif isinstance(value, list):
            hex_str = get_stack_value(value, '0')
        else:
            hex_str = str(value)
        
        hex_str = hex_str.strip()
        
        # Converti
        if hex_str.startswith('0x'):
            return int(hex_str, 16)
        elif hex_str.isdigit():
            return int(hex_str)
        else:
            try:
                return int(hex_str, 16)
            except:
                return 0
    except:
        return 0

def parse_address_from_cell(cell_data):
    """Estrae indirizzo da cella, gestisce dict (v3) e list (pytonlib)"""
    try:
        # CASO 1: API v3 - {"type": "cell", "cell": "boc_hex"}
        if isinstance(cell_data, dict):
            if cell_data.get('type') == 'cell':
                cell_boc = cell_data.get('cell', '')
                if cell_boc:
                    try:
                        from ton.utils import read_address_from_cell
                        from ton.boc import Cell
                        cell = Cell.one_from_boc(cell_boc)
                        address = read_address_from_cell(cell)
                        if address and address != 'addr_none':
                            return address
                    except ImportError:
                        # Se ton non è installato, restituisci il raw
                        return f"0:{cell_boc[:64]}"
                    except:
                        pass
        
        # CASO 2: Pytonlib - ["tvm.Cell", {"bytes": "base64"}]
        elif isinstance(cell_data, list) and len(cell_data) == 2:
            if cell_data[0] == 'tvm.Cell' and isinstance(cell_data[1], dict):
                cell_b64 = cell_data[1].get('bytes', '')
                if cell_b64:
                    try:
                        import base64
                        from ton.utils import read_address_from_cell
                        from ton.boc import Cell
                        cell_bytes = base64.b64decode(cell_b64)
                        cell = Cell.one_from_boc(cell_bytes)
                        address = read_address_from_cell(cell)
                        if address and address != 'addr_none':
                            return address
                    except:
                        pass
        
        return None
    except:
        return None

# ============= PARSING STACK VENDITA =============

def parse_sale_stack(stack: list) -> Optional[tuple]:
    """
    Parse sale stack - Supporta API v3 (dict) e pytonlib (list)
    """
    try:
        if not stack or len(stack) < 7:
            print(f"[parse_sale_stack] Stack too small: {len(stack) if stack else 0}")
            return None
        
        # DEBUG: mostra struttura stack
        print(f"[parse_sale_stack] Stack size: {len(stack)}")
        for i, item in enumerate(stack[:3]):
            if isinstance(item, dict):
                print(f"  [{i}] dict keys: {list(item.keys())}")
            elif isinstance(item, list):
                print(f"  [{i}] list len: {len(item)}")
            else:
                print(f"  [{i}] type: {type(item)}")
        
        # Determina tipo vendita dal primo elemento
        sale_type_value = get_stack_value(stack[0], '')
        sale_type = str(sale_type_value).upper()
        
        if 'AUC' in sale_type or '415543' in sale_type:
            return parse_auction_stack(stack)
        elif 'OFFER' in sale_type or '4f46464552' in sale_type:
            return parse_offer_stack(stack)
        else:
            return parse_fixprice_stack(stack)
            
    except Exception as e:
        print(f'[parse_sale_stack] Error: {e}')
        import traceback
        traceback.print_exc()
        return None

def parse_fixprice_stack(stack: list) -> Optional[tuple]:
    """Parse fixprice sale stack - Supporta dict e list"""
    try:
        if len(stack) < 7:
            return None
        
        action = 'SaleFixPrice'
        
        # Estrai valori gestendo dict/list
        is_complete = bool(hex_to_int(stack[1]))
        created_at = hex_to_int(stack[2])
        marketplace_address = parse_address_from_cell(stack[3])
        nft_address = parse_address_from_cell(stack[4])
        nft_owner_address = parse_address_from_cell(stack[5]) if len(stack) > 5 else None
        full_price = hex_to_int(stack[6]) / 1_000_000_000
        
        return (action, is_complete, created_at, marketplace_address,
                nft_address, nft_owner_address, full_price)
        
    except Exception as e:
        print(f'[parse_fixprice_stack] Error: {e}')
        return None

def parse_auction_stack(stack: list) -> Optional[tuple]:
    """Parse auction sale stack - Supporta dict e list"""
    try:
        if len(stack) < 20:
            return None
        
        action = 'SaleAuction'
        
        # Estrai valori
        is_end = bool(hex_to_int(stack[1]))
        end_time = hex_to_int(stack[2])
        marketplace_address = parse_address_from_cell(stack[3])
        nft_address = parse_address_from_cell(stack[4])
        nft_owner_address = parse_address_from_cell(stack[5])
        last_bid = hex_to_int(stack[6]) / 1_000_000_000
        last_member = parse_address_from_cell(stack[7])
        min_step = hex_to_int(stack[8]) / 1_000_000_000
        max_bid = hex_to_int(stack[15]) / 1_000_000_000
        min_bid = hex_to_int(stack[16]) / 1_000_000_000
        created_at = hex_to_int(stack[17])
        last_bid_at = hex_to_int(stack[18])
        is_canceled = bool(hex_to_int(stack[19]))
        
        return (action, is_end, created_at, marketplace_address, nft_address,
                nft_owner_address, min_bid, max_bid, min_step, last_bid_at,
                last_member, last_bid, is_canceled, end_time)
        
    except Exception as e:
        print(f'[parse_auction_stack] Error: {e}')
        return None

def parse_offer_stack(stack: list) -> Optional[tuple]:
    """Parse offer sale stack - Supporta dict e list"""
    try:
        if len(stack) < 8:
            return None
        
        action = 'SaleOffer'
        
        # Estrai valori
        is_complete = bool(hex_to_int(stack[1]))
        created_at = hex_to_int(stack[2])
        marketplace_address = parse_address_from_cell(stack[4])
        nft_address = parse_address_from_cell(stack[5])
        offer_owner_address = parse_address_from_cell(stack[6])
        full_price = hex_to_int(stack[7]) / 1_000_000_000
        
        return (action, is_complete, created_at, marketplace_address,
                nft_address, offer_owner_address, full_price)
        
    except Exception as e:
        print(f'[parse_offer_stack] Error: {e}')
        return None

# ============= FUNZIONI PER RECUPERARE NFT ADDRESS =============

async def get_nft_from_sale_contract(sale_address: str) -> Optional[str]:
    """
    Recupera NFT address da un contratto di vendita usando TON Center API v3
    """
    try:
        # Usa l'endpoint ufficiale nft/transfers
        url = "https://toncenter.com/api/v3/nft/transfers"
        params = {
            "sale_contract_address": sale_address,
            "limit": 1
        }
        
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    transfers = data.get('nft_transfers', [])
                    if transfers:
                        nft_address = transfers[0].get('nft_address')
                        if nft_address:
                            print(f"[get_nft] ✅ Trovato via nft/transfers: {nft_address[-12:]}")
                            return nft_address
    except Exception as e:
        print(f"[get_nft] Error: {e}")
    
    return None

def extract_nft_from_comment(tx: dict) -> Optional[str]:
    """
    Estrae NFT address dal commento della transazione
    """
    try:
        in_msg = tx.get('in_msg', {})
        message_content = in_msg.get('message_content', {})
        decoded = message_content.get('decoded', {})
        
        # Getgems, Disintar, Tonex mettono NFT address nel commento!
        nft_address = decoded.get('comment')
        
        if nft_address and isinstance(nft_address, str):
            # Pulisci l'indirizzo se necessario
            if nft_address.startswith('EQ') or nft_address.startswith('UQ'):
                # Converti in formato raw se serve
                pass
            elif nft_address.startswith('0:'):
                print(f"[get_nft] ✅ Trovato nel commento: {nft_address[-12:]}")
                return nft_address
        
        # Cerca nel body come fallback
        body = message_content.get('body', '')
        match = re.search(r'0:[0-9A-F]{64}', body)
        if match:
            nft_address = match.group(0)
            print(f"[get_nft] ✅ Trovato nel body: {nft_address[-12:]}")
            return nft_address
            
    except Exception as e:
        print(f"[get_nft] Error extracting comment: {e}")
    
    return None

async def get_nft_from_transaction_hash(tx_hash_hex: str) -> Optional[str]:
    """
    Trova NFT address usando lo HASH della transazione in FORMATO HEX!
    """
    try:
        url = "https://toncenter.com/api/v3/actions"
        params = {
            "transaction_hash": tx_hash_hex,  # ← QUI VA HEX, NON BASE64!
            "limit": 10
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=TONCENTER_HEADERS, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    actions = data.get('actions', [])
                    
                    for action in actions:
                        if action.get('type') == 'nft_transfer':
                            nft_address = action.get('details', {}).get('nft_address')
                            if nft_address:
                                print(f"[get_nft] ✅ NFT found via transaction hash: {nft_address[-12:]}")
                                return nft_address
        return None
    except Exception as e:
        print(f"[get_nft] ❌ Error: {e}")
        return None

def get_nft_from_transaction_messages(transaction_data):
    """
    Recupera l'indirizzo NFT analizzando i messaggi della transazione
    
    Args:
        transaction_data: dizionario con i dati della transazione dall'API
        
    Returns:
        str: indirizzo NFT se trovato, None altrimenti
    """
    try:
        # Prova a cercare nei messaggi in uscita (out_msgs)
        if 'out_msgs' in transaction_data and transaction_data['out_msgs']:
            for msg in transaction_data['out_msgs']:
                # Il messaggio verso l'NFT è tipicamente quello con destination
                if 'destination' in msg and msg.get('destination'):
                    destination = msg['destination']
                    
                    # Verifica se potrebbe essere un indirizzo NFT valido
                    # Gli NFT di solito hanno indirizzi che iniziano con EQ
                    if isinstance(destination, str) and destination.startswith('EQ'):
                        print(f"[DEBUG] 🎯 NFT trovato in out_msgs: {destination}")
                        return destination
                    
                    # Se destination è un dict con address
                    if isinstance(destination, dict) and 'address' in destination:
                        address = destination['address']
                        if address.startswith('EQ'):
                            print(f"[DEBUG] 🎯 NFT trovato in out_msgs (dict): {address}")
                            return address
        
        # Prova anche con i messaggi in entrata (in_msg)
        if 'in_msg' in transaction_data and transaction_data['in_msg']:
            in_msg = transaction_data['in_msg']
            
            if 'source' in in_msg and in_msg.get('source'):
                source = in_msg['source']
                
                if isinstance(source, str) and source.startswith('EQ'):
                    print(f"[DEBUG] 🎯 NFT trovato in in_msg source: {source}")
                    return source
                
                if isinstance(source, dict) and 'address' in source:
                    address = source['address']
                    if address.startswith('EQ'):
                        print(f"[DEBUG] 🎯 NFT trovato in in_msg source (dict): {address}")
                        return address
        
        # Ultimo tentativo: cerca in decoded_body se presente
        if 'decoded_body' in transaction_data:
            decoded = transaction_data['decoded_body']
            if isinstance(decoded, dict):
                # Cerca ricorsivamente negli attributi comuni
                for key in ['nft_address', 'nft', 'item_address', 'address']:
                    if key in decoded and decoded[key]:
                        address = decoded[key]
                        if isinstance(address, str) and address.startswith('EQ'):
                            print(f"[DEBUG] 🎯 NFT trovato in decoded_body[{key}]: {address}")
                            return address
        
        print("[DEBUG] ⚠️ Nessun indirizzo NFT trovato nei messaggi della transazione")
        return None
        
    except Exception as e:
        print(f"[DEBUG] ❌ Errore durante l'estrazione NFT dai messaggi: {e}")
        return None


def get_nft_from_stack_or_messages(transaction_data):
    """
    Metodo ibrido: prima prova lo stack (per compatibilità), 
    poi fallback ai messaggi
    
    Args:
        transaction_data: dizionario con i dati della transazione
        
    Returns:
        str: indirizzo NFT se trovato, None altrimenti
    """
    # Prova prima il metodo vecchio (stack)
    if 'compute_phase' in transaction_data:
        compute = transaction_data['compute_phase']
        if 'stack' in compute and compute['stack']:
            stack = compute['stack']
            
            # Cerca negli elementi dello stack
            for item in stack:
                if isinstance(item, dict):
                    # Cerca il campo 'address' o 'cell'
                    if 'address' in item and item['address']:
                        address = item['address']
                        if isinstance(address, str) and address.startswith('EQ'):
                            print(f"[DEBUG] 🎯 NFT trovato nello stack: {address}")
                            return address
    
    # Se non trovato nello stack, usa i messaggi
    print("[DEBUG] 🔄 Stack vuoto o non valido, uso il metodo dei messaggi...")
    return get_nft_from_transaction_messages(transaction_data)

async def get_nft_from_sale_contract_v2(sale_address: str) -> Optional[str]:
    """
    Recupera NFT address usando API v2 - NON cancella i dati!
    """
    try:
        from secretData import toncenter_api_key
        
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        if toncenter_api_key:
            headers["X-API-Key"] = toncenter_api_key
        
        # 🟢 ENDPOINT V2 - /getTransactions
        url = "https://toncenter.com/api/v2/getTransactions"
        params = {
            "address": sale_address,  # ← v2 usa "address", non "account"!
            "limit": 10
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    txs = data.get('transactions', [])
                    
                    # Cerca l'NFT transfer nella history del contratto
                    for tx in txs:
                        out_msgs = tx.get('out_msgs', [])
                        for msg in out_msgs:
                            # Cerca opcode nft_transfer (0x5fcc3d14)
                            if msg.get('opcode') == '0x5fcc3d14':
                                # In v2, l'NFT address è nel destination o nel commento
                                nft_address = msg.get('destination')
                                if nft_address:
                                    # Converti in formato RAW se necessario
                                    if nft_address.startswith('EQ') or nft_address.startswith('UQ'):
                                        from ton.utils import to_raw
                                        nft_address = to_raw(nft_address)
                                    print(f"[get_nft_v2] ✅ NFT found: {nft_address[-12:]}")
                                    return nft_address
        return None
    except Exception as e:
        print(f"[get_nft_v2] ❌ Error: {e}")
        return None

# Alias per retrocompatibilità
parse_address_from_cell_v3 = parse_address_from_cell
