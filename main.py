import requests
import asyncio
import sys

from pathlib import Path
from pytonlib import TonlibClient
from telegram.ext import Application  # <-- NUOVO IMPORT

from config import current_path, ton_config_url, royalty_addresses, get_methods, trs_limit, collections_list, bot_token, TELEGRAM_CHAT_ID
from functions import parse_sale_stack
from nftData import get_nft_data, get_collection_floor
from tgMessage import tg_message

# ============================================
# INIZIALIZZAZIONE BOT TELEGRAM
# ============================================
if not bot_token:
    print("[MAIN] ❌ ERRORE CRITICO: TELEGRAM_BOT_TOKEN non configurato")
    sys.exit(1)

# Crea l'oggetto Application per il bot
application = Application.builder().token(bot_token).build()
print("[MAIN] ✅ Bot Telegram inizializzato")

# Condividi l'application con tgMessage
import tgMessage
tg_message.application = application  # Fornisci l'application a tg_message

# ============================================
# SHIM PER CRC16 (NECESSARIO PER TONSDK)
# ============================================
class CRC16Shim:
    @staticmethod
    def crc16xmodem(data, crc=0):
        """Implementazione CRC-16/XMODEM per compatibilità."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        for byte in data:
            crc ^= (byte << 8) & 0xFFFF
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ 0x1021) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
        return crc

sys.modules['crc16'] = CRC16Shim()

# ============================================
# FUNZIONI TON
# ============================================
async def get_client():
    config = requests.get(ton_config_url, timeout=10).json()
    keystore_dir = '/tmp/ton_keystore'
    Path(keystore_dir).mkdir(parents=True, exist_ok=True)

    client = TonlibClient(
        ls_index=3,  # Potresti cambiare anche questo, prova 0, 1, 3...
        config=config,
        keystore=keystore_dir,
        tonlib_timeout=30,  # <-- AUMENTA da 10 a 30 secondi
    )
    await client.init()
    return client

async def royalty_trs(royalty_address):
    try:
        utimes = list()
        LAST_UTIME_PATH = '/tmp/lastUtime.txt'
        
        # Leggi last_utime
        try:
            with open(LAST_UTIME_PATH, 'r') as f:
                last_utime = int(f.read().strip())
        except FileNotFoundError:
            print(f"[royalty_trs] Creating new lastUtime file", flush=True)
            last_utime = 0
            with open(LAST_UTIME_PATH, 'w') as f:
                f.write('0')
        except ValueError:
            print(f"[royalty_trs] Invalid content, resetting to 0", flush=True)
            last_utime = 0
            with open(LAST_UTIME_PATH, 'w') as f:
                f.write('0')
        
        print(f"[royalty_trs] Processing {royalty_address}, last_utime: {last_utime}", flush=True)
        
        # Ottieni client
        client = await get_client()
        
        try:
            # Ottieni transazioni
            trs = await client.get_transactions(account=royalty_address, limit=trs_limit)
            
            if not trs:
                print(f"[royalty_trs] No transactions found for {royalty_address}", flush=True)
                await client.close()
                return None
            
            # Processa transazioni
            for tr in trs[::-1]:
                sc_address = tr['in_msg']['source']
                
                if not sc_address or tr['utime'] <= last_utime:
                    continue
                
                for method in get_methods:
                    try:
                        response = await client.raw_run_method(address=sc_address, method=method, stack_data=[])
                        
                        if response and response['exit_code'] == 0:
                            sale_contract_data = parse_sale_stack(response['stack'])
                            
                            if sale_contract_data and sale_contract_data[1]:
                                sale_nft_data = await get_nft_data(client, sale_contract_data[4])
                                
                                if (sale_nft_data and sale_nft_data[1] in collections_list and sale_nft_data[0]):
                                    collection_floor_data = get_collection_floor(sale_nft_data[1])
                                    
                                    # Invio messaggio
                                    if sale_contract_data[0] == 'SaleFixPrice':
                                        await tg_message(sale_contract_data[0], sale_contract_data[3], sale_contract_data[4],
                                                       sale_contract_data[5], sale_nft_data[2], sale_contract_data[6],
                                                       sale_nft_data[3], sale_nft_data[4], collection_floor_data[0],
                                                       collection_floor_data[1])
                                    elif sale_contract_data[0] == 'SaleAuction':
                                        await tg_message(sale_contract_data[0], sale_contract_data[3], sale_contract_data[4],
                                                       sale_contract_data[5], sale_nft_data[2], sale_contract_data[11],
                                                       sale_nft_data[3], sale_nft_data[4], collection_floor_data[0],
                                                       collection_floor_data[1])
                                    elif sale_contract_data[0] == 'SaleOffer':
                                        await tg_message(sale_contract_data[0], sale_contract_data[3], sale_contract_data[4],
                                                       sale_contract_data[5], sale_nft_data[2], sale_contract_data[6],
                                                       sale_nft_data[3], sale_nft_data[4], collection_floor_data[0],
                                                       collection_floor_data[1])
                                    
                                    utimes.append(tr['utime'])
                    
                    except Exception as e:
                        print(f"[royalty_trs] Error in method {method} for {sc_address}: {e}", flush=True)
                        continue
            
            await client.close()
            
            # Restituisci l'ultimo utime
            return utimes[-1] if utimes else None
            
        except Exception as e:
            print(f"[royalty_trs] Failed to get transactions for {royalty_address}: {e}", flush=True)
            await client.close()
            return None
            
    except Exception as e:
        print(f"[royalty_trs] Critical error: {e}", flush=True)
        return None

async def scheduler():
    print("[SCHEDULER] ✅ Scheduler avviato")
    while True:
        utimes = await asyncio.gather(*map(royalty_trs, royalty_addresses))
        utimes = list(filter(None, utimes))
        try:
            if len(utimes) > 0:
                with open('/tmp/lastUtime.txt', 'w') as f:
                    f.write(str(max(utimes)))
                print(f"[SCHEDULER] Aggiornato lastUtime a: {max(utimes)}", flush=True)
        except Exception as e:
            print(f"[SCHEDULER] ❌ Errore nel salvataggio lastUtime: {e}", flush=True)

        await asyncio.sleep(15)

# ============================================
# AVVIO APPLICAZIONE
# ============================================
if __name__ == '__main__':
    print("[MAIN] 🚀 Avvio applicazione...")
    asyncio.run(scheduler())
