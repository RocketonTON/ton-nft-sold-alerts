import requests
import json
import base64

from config import tonorg_price_url, cmc_url, cmc_params, cmc_headers


def parse_sale_stack(stack):
    """
    Parsing dello stack di vendita - compatibile con TonAPI.
    """
    try:
        # Il primo elemento indica il tipo di vendita
        if len(stack) < 7:
            return None
        
        # Converti hex string in int per controllare il tipo
        try:
            sale_type_hex = stack[0][1]
            
            if sale_type_hex == '0x415543':  # AUC
                return parse_auction_stack(stack)
            if sale_type_hex == '0x4f46464552':  # OFFER
                return parse_offer_stack(stack)
        except:
            pass
        
        # SaleFixPrice
        action = 'SaleFixPrice'
        is_complete = bool(int(stack[1][1], 16))
        created_at = int(stack[2][1], 16)
        
        marketplace_address = parse_address_from_stack(stack[3])
        nft_address = parse_address_from_stack(stack[4])
        
        try:
            nft_owner_address = parse_address_from_stack(stack[5])
        except:
            nft_owner_address = None
        
        # Converti da nanoTON a TON
        full_price = int(stack[6][1], 16) / 1_000_000_000

        return action, is_complete, created_at, marketplace_address, nft_address, nft_owner_address, full_price

    except Exception as e:
        print(f'[parse_sale_stack] Error: {e}')
        return None


def parse_auction_stack(stack):
    """Parsing stack per aste."""
    try:
        action = 'SaleAuction'
        is_end = bool(int(stack[1][1], 16))
        created_at = int(stack[17][1], 16)
        
        marketplace_address = parse_address_from_stack(stack[3])
        nft_address = parse_address_from_stack(stack[4])
        nft_owner_address = parse_address_from_stack(stack[5])
        
        min_bid = int(stack[16][1], 16) / 1_000_000_000
        max_bid = int(stack[15][1], 16) / 1_000_000_000
        min_step = int(stack[8][1], 16) / 1_000_000_000
        last_bid_at = int(stack[18][1], 16)
        
        try:
            last_member = parse_address_from_stack(stack[7])
        except:
            last_member = None
        
        last_bid = int(stack[6][1], 16) / 1_000_000_000
        is_canceled = bool(int(stack[19][1], 16))
        end_time = int(stack[2][1], 16)

        return action, is_end, created_at, marketplace_address, nft_address, nft_owner_address, \
               min_bid, max_bid, min_step, last_bid_at, last_member, last_bid, is_canceled, end_time
    
    except Exception as e:
        print(f'[parse_auction_stack] Error: {e}')
        return None


def parse_offer_stack(stack):
    """Parsing stack per offerte."""
    try:
        action = 'SaleOffer'
        is_complete = bool(int(stack[1][1], 16))
        created_at = int(stack[2][1], 16)
        
        marketplace_address = parse_address_from_stack(stack[4])
        nft_address = parse_address_from_stack(stack[5])
        offer_owner_address = parse_address_from_stack(stack[6])
        
        full_price = int(stack[7][1], 16) / 1_000_000_000

        return action, is_complete, created_at, marketplace_address, nft_address, offer_owner_address, full_price
    
    except Exception as e:
        print(f'[parse_offer_stack] Error: {e}')
        return None


def parse_address_from_stack(stack_item):
    """
    Estrae un indirizzo da un elemento dello stack.
    Compatibile con formato TonAPI.
    """
    try:
        if stack_item[0] == 'tvm.Cell':
            # Estrai i bytes
            cell_bytes = stack_item[1]['bytes']
            
            # Se è base64 string, decodifica
            if isinstance(cell_bytes, str):
                cell_bytes = base64.b64decode(cell_bytes)
            
            # Importa le librerie necessarie
            from pytoniq_core import Cell
            
            # Crea una Cell da BoC
            cell = Cell.one_from_boc(cell_bytes)
            
            # Leggi l'indirizzo
            address = cell.begin_parse().load_address()
            
            return address.to_str(1, 1, 1)  # formato bounceable
        
        return None
    
    except Exception as e:
        # Fallback: se pytoniq non è disponibile, usa parsing manuale
        try:
            return parse_address_fallback(stack_item)
        except:
            print(f'[parse_address_from_stack] Error: {e}')
            return None


def parse_address_fallback(stack_item):
    """Parsing indirizzo senza pytoniq (base64 direct decode)."""
    # TODO: Implementare se necessario
    # Per ora ritorna None se pytoniq non è disponibile
    return None


def convert_ton_to_usd(ton):
    """Converte TON in USD usando CoinMarketCap API."""
    try:
        session = requests.Session()
        session.headers.update(cmc_headers)

        response = session.get(cmc_url, params=cmc_params, timeout=10)
        data = response.json()
        
        usd = data['data']['11419']['quote']['USD']['price']
        usd_price = round(float(ton) * usd, 2)

        return usd_price

    except Exception as e:
        print(f'[convert_ton_to_usd] CMC API error: {e}. Trying fallback...')
        return convert_ton_to_usd_old(ton)


def convert_ton_to_usd_old(ton):
    """Fallback: converte TON in USD usando ton.org."""
    try:
        response = requests.get(tonorg_price_url, timeout=10)
        usd = response.json()['the-open-network']['usd']
        usd_price = round(float(ton) * usd, 2)
        
        return usd_price

    except Exception as e:
        print(f'[convert_ton_to_usd_old] Error: {e}')
        return None
