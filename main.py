import requests
import asyncio
import time
import traceback

from web_server import run_in_background
from pathlib import Path
from pytonlib import TonlibClient

from config import current_path, ton_config_url, royalty_addresses, get_methods, trs_limit, collections_list
from functions import parse_sale_stack
from nftData import get_nft_data, get_collection_floor
from tgMessage import tg_message

# === GLOBAL TON CLIENT ===
_ton_client = None

async def get_global_client():
    """Crea o restituisce un client TON globale condiviso."""
    global _ton_client
    if _ton_client is None:
        print("[INIT] Creating global TonLibClient...")
        config = requests.get(ton_config_url).json()
        keystore_dir = '/tmp/ton_keystore'
        Path(keystore_dir).mkdir(parents=True, exist_ok=True)
        
        _ton_client = TonlibClient(ls_index=2,
                                   config=config,
                                   keystore=keystore_dir,
                                   timeout=60)  # Aumentato a 60 secondi
        await _ton_client.init()
        print("[INIT] Global TonLibClient created successfully.")
    return _ton_client

async def close_global_client():
    """Chiude il client TON globale (usato all'uscita)."""
    global _ton_client
    if _ton_client:
        await _ton_client.close()
        _ton_client = None


async def royalty_trs(royalty_address):
    """Controlla le transazioni per un indirizzo royalty. Usa il client globale."""
    try:
        utimes = []
        
        # 1. LEGGI lastUtime in modo ASINCRONO e SICURO
        try:
            # Usa aiofiles per I/O asincrono, ma per semplicità facciamo così:
            with open(f'{current_path}/lastUtime', 'r') as f:
                last_utime = int(f.read().strip())
        except (FileNotFoundError, ValueError):
            # Se il file non esiste o è vuoto, inizia da 0
            last_utime = 0
            print(f"[royalty_trs] File lastUtime non trovato o vuoto. Inizio da timestamp 0.")
        
        # 2. PRENDI IL CLIENT GLOBALE
        client = await get_global_client()
        
        # 3. PRENDI LE TRANSAZIONI
        trs = None
        try:
            trs = await client.get_transactions(account=royalty_address, limit=trs_limit)
            print(f"[royalty_trs] Trovate {len(trs) if trs else 0} transazioni per {royalty_address[-6:]}")
        except Exception as e:
            print(f'[royalty_trs] Richiesta fallita per {royalty_address[-6:]}: {e}')
            return None  # Esci senza errori
        
        # 4. PROCESSALE TRANSAZIONI
        if trs is not None:
            for tr in trs[::-1]:  # Processa dalla più vecchia alla più nuova
                sc_address = tr['in_msg']['source']
                
                # Filtra transazioni vecchie o senza source
                if tr['utime'] <= last_utime or not sc_address:
                    continue
                
                # PROVA OGNI METODO
                for method in get_methods:
                    try:
                        response = await client.raw_run_method(
                            address=sc_address,
                            method=method,
                            stack_data=[]
                        )
                    except Exception as e:
                        print(f'[royalty_trs] Errore metodo {method} su {sc_address[-6:]}: {e}')
                        continue  # Prova il metodo successivo
                    
                    # SE IL METODO RESTITUISCE RISULTATO VALIDO
                    if response and response['exit_code'] == 0:
                        sale_contract_data = parse_sale_stack(response['stack'])
                        
                        if sale_contract_data and sale_contract_data[1]:  # sale_contract_data[1] = is_complete
                            sale_nft_data = await get_nft_data(client, sale_contract_data[4])
                            
                            if (sale_nft_data and sale_nft_data[1] in collections_list and sale_nft_data[0]):
                                collection_floor_data = get_collection_floor(sale_nft_data[1])
                                
                                # INVIA MESSAGGIO TELEGRAM IN BASE AL TIPO DI VENDITA
                                if sale_contract_data[0] == 'SaleFixPrice':
                                    tg_message(sale_contract_data[0], sale_contract_data[3], sale_contract_data[4],
                                              sale_contract_data[5], sale_nft_data[2], sale_contract_data[6],
                                              sale_nft_data[3], sale_nft_data[4], collection_floor_data[0],
                                              collection_floor_data[1])
                                
                                elif sale_contract_data[0] == 'SaleAuction':
                                    tg_message(sale_contract_data[0], sale_contract_data[3], sale_contract_data[4],
                                              sale_contract_data[5], sale_nft_data[2], sale_contract_data[11],
                                              sale_nft_data[3], sale_nft_data[4], collection_floor_data[0],
                                              collection_floor_data[1])
                                
                                elif sale_contract_data[0] == 'SaleOffer':
                                    tg_message(sale_contract_data[0], sale_contract_data[3], sale_contract_data[4],
                                              sale_contract_data[5], sale_nft_data[2], sale_contract_data[6],
                                              sale_nft_data[3], sale_nft_data[4], collection_floor_data[0],
                                              collection_floor_data[1])
                                
                                utimes.append(tr['utime'])
                                break  # Esci dal loop dei metodi, abbiamo trovato una vendita
        
        # 5. RESTITUISCI L'ULTIMO TIMESTAMP (o None)
        return utimes[-1] if utimes else None
        
    except Exception as e:
        # CATTURA QUALSIASI ALTRO ERRORE IMPREVISTO
        print(f"[royalty_trs CRITICAL] Errore imprevisto per {royalty_address[-6:]}: {e}")
        import traceback
        print(traceback.format_exc())
        return None


async def scheduler():
    print("=== [SCHEDULER] Started ===")
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            print(f"\n[CYCLE #{cycle_count}] Start at {time.strftime('%H:%M:%S')}")
            
            utimes = await asyncio.gather(*map(royalty_trs, royalty_addresses))
            utimes = [u for u in utimes if u is not None]
            
            if utimes:
                last = max(utimes)
                try:
                    open(f'{current_path}/lastUtime', 'w').write(str(last))
                    print(f"[CYCLE #{cycle_count}] Updated lastUtime: {last}")
                except Exception as e:
                    print(f"[CYCLE #{cycle_count}] Error saving lastUtime: {e}")
            
            print(f"[CYCLE #{cycle_count}] Finished. Sleeping 15s...")
            await asyncio.sleep(15)
            
    except asyncio.CancelledError:
        print("[SCHEDULER] Cancelled")
    except Exception as e:
        print(f"[SCHEDULER !!!] Fatal error: {type(e).__name__}: {e}")
        print(traceback.format_exc())
    finally:
        # Chiude il client globale quando lo scheduler termina
        await close_global_client()
        print("[SCHEDULER] Global client closed.")

import atexit

def cleanup_tonlib():
    """Tenta di pulire le risorse di pytonlib all'uscita."""
    try:
        # Qui si potrebbe fare una pulizia esplicita se il client fosse globale
        pass
    except Exception:
        pass

# Registra la funzione di cleanup
atexit.register(cleanup_tonlib)

if __name__ == '__main__':
    run_in_background()
    
    try:
        asyncio.run(scheduler())
    except KeyboardInterrupt:
        print("\n[MAIN] Bot stopped by user")
    except Exception as e:
        print(f"[MAIN] Bot crashed: {e}")
        print(traceback.format_exc())
        raise
