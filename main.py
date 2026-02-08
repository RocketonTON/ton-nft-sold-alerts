import asyncio
import time
import traceback
import requests
from pathlib import Path

from web_server import run_in_background
from config import current_path, royalty_addresses, collections_list
from nftData import get_collection_floor
from tgMessage import tg_message
from functions import convert_ton_to_usd

# === CONFIGURAZIONE TONAPI ===
TONAPI_BASE = "https://tonapi.io/v2"
TONAPI_HEADERS = {
    "Authorization": "Bearer AFH3J5APTYFZD6QAAAAFQRGBZFOIO26SOOJ5N2LD5YGJGDOBMFBDKA3HNZ72ZNUTFHSFRJI"  # Token pubblico
}

def get_transactions_http(address, limit=50):
    """Ottiene le transazioni via HTTP API (TonAPI)."""
    try:
        url = f"{TONAPI_BASE}/blockchain/accounts/{address}/transactions"
        params = {"limit": limit}
        
        response = requests.get(url, headers=TONAPI_HEADERS, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        return data.get("transactions", [])
    
    except Exception as e:
        print(f"[get_transactions_http] Error: {e}")
        return []


def run_get_method_http(address, method):
    """Esegue un get method via HTTP API."""
    try:
        url = f"{TONAPI_BASE}/blockchain/accounts/{address}/methods/{method}"
        
        response = requests.get(url, headers=TONAPI_HEADERS, timeout=15)
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        
        # Controlla se il metodo è stato eseguito con successo
        if not data.get("success", False):
            return None
        
        # Estrai lo stack
        stack = data.get("stack", [])
        return stack if stack else None
    
    except Exception as e:
        return None


def parse_tonapi_stack(stack):
    """
    Converte lo stack di TonAPI nel formato atteso.
    
    TonAPI restituisce: [{"type": "num", "num": "123"}, ...]
    Necessario: [["num", "0x7b"], ...]
    """
    converted = []
    
    for item in stack:
        item_type = item.get("type")
        
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
        
        response = requests.get(url, headers=TONAPI_HEADERS, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # Estrai i dati necessari
        collection_address = data.get("collection", {}).get("address")
        owner_address = data.get("owner", {}).get("address")
        nft_name = data.get("metadata", {}).get("name", "Unknown NFT")
        nft_image = data.get("previews", [{}])[0].get("url", "") if data.get("previews") else ""
        
        # TonAPI non ha campo "init", assumiamo True se abbiamo i dati
        init = bool(collection_address and owner_address)
        
        return init, collection_address, owner_address, nft_name, nft_image
    
    except Exception as e:
        print(f"[get_nft_data_http] Error for {nft_address}: {e}")
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
            print(f"[royalty_trs] File lastUtime non trovato. Inizio da timestamp 0.")
        
        # 2. OTTIENI TRANSAZIONI
        print(f"[royalty_trs] Fetching transactions for {royalty_address[-6:]}...")
        transactions = get_transactions_http(royalty_address, limit=50)
        
        if not transactions:
            print(f"[royalty_trs] No transactions found for {royalty_address[-6:]}")
            return None
        
        print(f"[royalty_trs] Found {len(transactions)} transactions for {royalty_address[-6:]}")
        
        # 3. PROCESSA TRANSAZIONI
        for tx in reversed(transactions):  # Dalla più vecchia alla più nuova
            tx_time = tx.get("utime", 0)
            
            # Filtra transazioni vecchie
            if tx_time <= last_utime:
                continue
            
            # Ottieni l'indirizzo del mittente
            in_msg = tx.get("in_msg", {})
            source = in_msg.get("source", {}).get("address")
            
            if not source:
                continue
            
            # PROVA I METODI GET
            get_methods = ['get_sale_data', 'get_offer_data']
            
            for method in get_methods:
                stack = run_get_method_http(source, method)
                
                if not stack:
                    continue
                
                # Converti lo stack
                converted_stack = parse_tonapi_stack(stack)
                
                # Parsing (importa la funzione esistente)
                from functions import parse_sale_stack
                sale_data = parse_sale_stack(converted_stack)
                
                if not sale_data or not sale_data[1]:  # sale_data[1] = is_complete
                    continue
                
                # Ottieni dati NFT
                nft_address = sale_data[4]
                nft_data = get_nft_data_http(nft_address)
                
                if not nft_data or nft_data[1] not in collections_list:
                    continue
                
                # Ottieni floor
                collection_floor_data = get_collection_floor(nft_data[1])
                
                # INVIA MESSAGGIO TELEGRAM
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
                break  # Esci dal loop dei metodi
        
        return utimes[-1] if utimes else None
    
    except Exception as e:
        print(f"[royalty_trs] CRITICAL Error for {royalty_address[-6:]}: {e}")
        traceback.print_exc()
        return None


async def scheduler():
    """Loop principale del bot."""
    print("=== [SCHEDULER] Started (HTTP API Mode) ===")
    print("✅ Using TonAPI instead of lite client - no connection issues!")
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            print(f"\n[CYCLE #{cycle_count}] Start at {time.strftime('%H:%M:%S')}")
            
            # Processa tutti gli indirizzi
            results = []
            for addr in royalty_addresses:
                result = await royalty_trs(addr)
                results.append(result)
            
            utimes = [u for u in results if u is not None]
            
            # Aggiorna lastUtime
            if utimes:
                last = max(utimes)
                try:
                    with open(f'{current_path}/lastUtime.txt', 'w') as f:
                        f.write(str(last))
                    print(f"[CYCLE #{cycle_count}] ✅ Updated lastUtime: {last}")
                except Exception as e:
                    print(f"[CYCLE #{cycle_count}] ❌ Error saving lastUtime: {e}")
            
            print(f"[CYCLE #{cycle_count}] Finished. Sleeping 15s...")
            await asyncio.sleep(9)
    
    except KeyboardInterrupt:
        print("\n[SCHEDULER] Stopped by user")
    except Exception as e:
        print(f"[SCHEDULER] Fatal error: {e}")
        traceback.print_exc()


if __name__ == '__main__':
    # Avvia il web server per Render
    run_in_background()
    
    try:
        asyncio.run(scheduler())
    except KeyboardInterrupt:
        print("\n[MAIN] Bot stopped by user")
    except Exception as e:
        print(f"[MAIN] Bot crashed: {e}")
        traceback.print_exc()
        raise
