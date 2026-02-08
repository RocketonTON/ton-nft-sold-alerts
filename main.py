import asyncio
import time
import traceback
from pathlib import Path

from pytoniq_core import Address
from pytoniq import LiteBalancer

from web_server import run_in_background
from config import current_path, royalty_addresses, get_methods, trs_limit, collections_list
from functions import parse_sale_stack
from nftData import get_nft_data, get_collection_floor
from tgMessage import tg_message

# === GLOBAL TON CLIENT ===
_ton_client = None

async def get_global_client():
    """Crea o restituisce un client TON globale condiviso con pytoniq."""
    global _ton_client
    if _ton_client is None:
        print("[INIT] Creating global LiteBalancer client...")
        
        # LiteBalancer si connette automaticamente ai lite servers pubblici
        _ton_client = LiteBalancer.from_mainnet_config(trust_level=2)
        
        await _ton_client.start_up()
        print("[INIT] Global LiteBalancer client created successfully.")
    return _ton_client

async def close_global_client():
    """Chiude il client TON globale."""
    global _ton_client
    if _ton_client:
        await _ton_client.close_all()
        _ton_client = None
        print("[CLEANUP] Global client closed.")


async def royalty_trs(royalty_address):
    """Controlla le transazioni per un indirizzo royalty usando pytoniq."""
    try:
        utimes = []
        
        # 1. LEGGI lastUtime
        try:
            with open(f'{current_path}/lastUtime.txt', 'r') as f:
                last_utime = int(f.read().strip())
        except (FileNotFoundError, ValueError):
            last_utime = 0
            print(f"[royalty_trs] File lastUtime non trovato. Inizio da timestamp 0.")
        
        # 2. PRENDI IL CLIENT GLOBALE
        client = await get_global_client()
        
        # 3. Converti l'indirizzo in formato pytoniq
        addr = Address(royalty_address)
        
        # 4. PRENDI LE TRANSAZIONI
        trs = None
        try:
            trs = await client.get_transactions(address=addr, count=trs_limit)
            print(f"[royalty_trs] Trovate {len(trs) if trs else 0} transazioni per {royalty_address[-6:]}")
        except Exception as e:
            print(f'[royalty_trs] Richiesta fallita per {royalty_address[-6:]}: {e}')
            return None
        
        # 5. PROCESSA LE TRANSAZIONI
        if trs:
            for tr in reversed(trs):  # Dalla più vecchia alla più nuova
                # Estrai l'indirizzo sorgente del messaggio in entrata
                in_msg = tr.in_msg
                if not in_msg or not in_msg.info.src:
                    continue
                
                sc_address = in_msg.info.src.to_str(1, 1, 1)  # formato bounceable
                tr_utime = tr.now
                
                # Filtra transazioni vecchie
                if tr_utime <= last_utime:
                    continue
                
                # PROVA OGNI METODO GET
                for method in get_methods:
                    try:
                        response = await client.run_get_method(
                            address=sc_address,
                            method=method,
                            stack=[]
                        )
                    except Exception as e:
                        # Metodo non esistente o errore, passa al successivo
                        continue
                    
                    # SE IL METODO RESTITUISCE RISULTATO VALIDO
                    if response and len(response) > 0:
                        # Converti lo stack di pytoniq nel formato compatibile con parse_sale_stack
                        converted_stack = convert_pytoniq_stack(response)
                        
                        sale_contract_data = parse_sale_stack(converted_stack)
                        
                        if sale_contract_data and sale_contract_data[1]:  # is_complete
                            sale_nft_data = await get_nft_data(client, sale_contract_data[4])
                            
                            if (sale_nft_data and 
                                sale_nft_data[1] in collections_list and 
                                sale_nft_data[0]):
                                
                                collection_floor_data = get_collection_floor(sale_nft_data[1])
                                
                                # INVIA MESSAGGIO TELEGRAM
                                if sale_contract_data[0] == 'SaleFixPrice':
                                    tg_message(
                                        sale_contract_data[0], sale_contract_data[3], 
                                        sale_contract_data[4], sale_contract_data[5], 
                                        sale_nft_data[2], sale_contract_data[6],
                                        sale_nft_data[3], sale_nft_data[4], 
                                        collection_floor_data[0], collection_floor_data[1]
                                    )
                                
                                elif sale_contract_data[0] == 'SaleAuction':
                                    tg_message(
                                        sale_contract_data[0], sale_contract_data[3],
                                        sale_contract_data[4], sale_contract_data[5],
                                        sale_nft_data[2], sale_contract_data[11],
                                        sale_nft_data[3], sale_nft_data[4],
                                        collection_floor_data[0], collection_floor_data[1]
                                    )
                                
                                elif sale_contract_data[0] == 'SaleOffer':
                                    tg_message(
                                        sale_contract_data[0], sale_contract_data[3],
                                        sale_contract_data[4], sale_contract_data[5],
                                        sale_nft_data[2], sale_contract_data[6],
                                        sale_nft_data[3], sale_nft_data[4],
                                        collection_floor_data[0], collection_floor_data[1]
                                    )
                                
                                utimes.append(tr_utime)
                                break  # Esci dal loop dei metodi
        
        # 6. RESTITUISCI L'ULTIMO TIMESTAMP
        return utimes[-1] if utimes else None
        
    except Exception as e:
        print(f"[royalty_trs CRITICAL] Errore per {royalty_address[-6:]}: {e}")
        print(traceback.format_exc())
        return None


def convert_pytoniq_stack(pytoniq_stack):
    """
    Converte lo stack di pytoniq nel formato atteso da parse_sale_stack.
    
    pytoniq restituisce una lista di oggetti (int, Cell, Slice, etc)
    parse_sale_stack si aspetta il formato: [[tipo, valore], ...]
    """
    from pytoniq_core import Cell, Slice
    
    converted = []
    
    for item in pytoniq_stack:
        if isinstance(item, int):
            # Converti int in hex string
            converted.append(['num', hex(item)])
        
        elif isinstance(item, Cell):
            # Converti Cell in formato bytes base64
            converted.append(['tvm.Cell', {'bytes': item.to_boc(has_idx=False)}])
        
        elif isinstance(item, Slice):
            # Converti Slice in Cell poi in bytes
            cell = item.to_cell()
            converted.append(['tvm.Cell', {'bytes': cell.to_boc(has_idx=False)}])
        
        else:
            # Fallback: prova a convertire in stringa
            converted.append(['unknown', str(item)])
    
    return converted


async def scheduler():
    """Loop principale del bot."""
    print("=== [SCHEDULER] Started ===")
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            print(f"\n[CYCLE #{cycle_count}] Start at {time.strftime('%H:%M:%S')}")
            
            # Processa tutti gli indirizzi in parallelo
            utimes = await asyncio.gather(*[royalty_trs(addr) for addr in royalty_addresses])
            utimes = [u for u in utimes if u is not None]
            
            # Aggiorna lastUtime se ci sono nuove transazioni
            if utimes:
                last = max(utimes)
                try:
                    with open(f'{current_path}/lastUtime.txt', 'w') as f:
                        f.write(str(last))
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
        await close_global_client()


if __name__ == '__main__':
    # Avvia il web server in background (per Render)
    run_in_background()
    
    try:
        asyncio.run(scheduler())
    except KeyboardInterrupt:
        print("\n[MAIN] Bot stopped by user")
    except Exception as e:
        print(f"[MAIN] Bot crashed: {e}")
        print(traceback.format_exc())
        raise
