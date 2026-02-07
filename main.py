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
                                   tonlib_timeout=10)
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
    utimes = list()
    last_utime = int(open(f'{current_path}/lastUtime', 'r').read())

    ### MODIFICA 1: Usa get_global_client(), NON get_client()
    client = await get_global_client()

    # 1. INIZIALIZZA `trs` a None PRIMA del try
    trs = None

    try:
        trs = await client.get_transactions(account=royalty_address,
                                            limit=trs_limit)
        print(f"[royalty_trs] Trovate {len(trs) if trs else 0} transazioni per {royalty_address[-6:]}")  # Log utile

    except Exception as e:
        print(f'Get Request for ({royalty_address}) address Failed! Check the logs\n{e}\n\n')
        
        ### MODIFICA 2: NON chiudere il client qui! Solo return.
        # RIMUOVI: await client.close()
        return None  # <-- Ritorna None esplicitamente

    if trs is not None:
        for tr in trs[::-1]:
            sc_address = tr['in_msg']['source']

            if tr['utime'] <= last_utime or tr['in_msg']['source'] == '':
                continue

            for method in get_methods:

                try:
                    response = await client.raw_run_method(address=sc_address,
                                                           method=method,
                                                           stack_data=[])

                except Exception as e:
                    print(
                        f'Error in raw run ({method}) method. Some problems with ({sc_address}) NFT sale contract. Check the logs:\n{e}')

                if response is not None and response['exit_code'] == 0:
                    sale_contract_data = parse_sale_stack(response['stack'])

                    if sale_contract_data is not None and sale_contract_data[1]:
                        sale_nft_data = await get_nft_data(client, sale_contract_data[4])

                        if sale_nft_data is not None and sale_nft_data[1] in collections_list and sale_nft_data[0]:
                            collection_floor_data = get_collection_floor(sale_nft_data[1])

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

    ### MODIFICA 3: NON chiudere il client qui! Verrà riutilizzato.
    # RIMUOVI COMPLETAMENTE: await client.close()

    try:
        return utimes[-1]
    except:
        return None  # Ritorna None invece di pass


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
