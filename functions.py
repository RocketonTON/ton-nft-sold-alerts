# functions.py - TON Center compatible functions
import aiohttp
import asyncio
import base64
import json
from typing import Optional, Dict, Any, Tuple
from secretData import cmc_token
from config import tonorg_price_url, cmc_url, cmc_headers

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
                        usd = data['data']['11419']['quote']['USD']['price']
                        return round(float(ton) * usd, 2)
        
        # Final fallback: fixed approximate value
        return round(float(ton) * 7.5, 2)
        
    except Exception as e:
        print(f'[convert_ton_to_usd] Error: {e}')
        return None

def parse_sale_stack(stack: list) -> Optional[tuple]:
    """
    Parse sale stack - TON Center compatible
    Stack format from TON Center API v3
    """
    try:
        if not stack or len(stack) < 7:
            return None
        
        # Helper to extract values from stack items
        def get_value(item, index=1):
            if isinstance(item, list) and len(item) > index:
                return item[index]
            elif isinstance(item, dict):
                return item.get('value', item.get('num', '0'))
            return '0'
        
        # Check sale type
        sale_type_hex = get_value(stack[0])
        
        if '0x415543' in str(sale_type_hex) or 'AUC' in str(sale_type_hex):
            return parse_auction_stack(stack)
        elif '0x4f46464552' in str(sale_type_hex) or 'OFFER' in str(sale_type_hex):
            return parse_offer_stack(stack)
        
        # Default: SaleFixPrice
        return parse_fixprice_stack(stack)
        
    except Exception as e:
        print(f'[parse_sale_stack] Error: {e}')
        return None

def parse_fixprice_stack(stack: list) -> tuple:
    """Parse fixprice sale stack"""
    try:
        action = 'SaleFixPrice'
        
        def hex_to_int(hex_str):
            if isinstance(hex_str, str) and hex_str.startswith('0x'):
                return int(hex_str, 16)
            return int(str(hex_str), 16) if str(hex_str) else 0
        
        is_complete = bool(hex_to_int(stack[1][1] if isinstance(stack[1], list) else stack[1]))
        created_at = hex_to_int(stack[2][1] if isinstance(stack[2], list) else stack[2])
        
        # Address parsing from cells
        marketplace_address = parse_address_from_cell(stack[3])
        nft_address = parse_address_from_cell(stack[4])
        
        try:
            nft_owner_address = parse_address_from_cell(stack[5])
        except:
            nft_owner_address = None
        
        # Price from nanoTON to TON
        price_hex = stack[6][1] if isinstance(stack[6], list) else stack[6]
        full_price = hex_to_int(price_hex) / 1_000_000_000

        return (action, is_complete, created_at, marketplace_address, 
                nft_address, nft_owner_address, full_price)
        
    except Exception as e:
        print(f'[parse_fixprice_stack] Error: {e}')
        return None

def parse_auction_stack(stack: list) -> tuple:
    """Parse auction sale stack"""
    try:
        action = 'SaleAuction'
        
        def hex_to_int(hex_str):
            if isinstance(hex_str, str) and hex_str.startswith('0x'):
                return int(hex_str, 16)
            return int(str(hex_str), 16) if str(hex_str) else 0
        
        is_end = bool(hex_to_int(stack[1][1] if isinstance(stack[1], list) else stack[1]))
        created_at = hex_to_int(stack[17][1] if isinstance(stack[17], list) else stack[17])
        
        marketplace_address = parse_address_from_cell(stack[3])
        nft_address = parse_address_from_cell(stack[4])
        nft_owner_address = parse_address_from_cell(stack[5])
        
        min_bid = hex_to_int(stack[16][1] if isinstance(stack[16], list) else stack[16]) / 1_000_000_000
        max_bid = hex_to_int(stack[15][1] if isinstance(stack[15], list) else stack[15]) / 1_000_000_000
        min_step = hex_to_int(stack[8][1] if isinstance(stack[8], list) else stack[8]) / 1_000_000_000
        last_bid_at = hex_to_int(stack[18][1] if isinstance(stack[18], list) else stack[18])
        
        try:
            last_member = parse_address_from_cell(stack[7])
        except:
            last_member = None
        
        last_bid = hex_to_int(stack[6][1] if isinstance(stack[6], list) else stack[6]) / 1_000_000_000
        is_canceled = bool(hex_to_int(stack[19][1] if isinstance(stack[19], list) else stack[19]))
        end_time = hex_to_int(stack[2][1] if isinstance(stack[2], list) else stack[2])

        return (action, is_end, created_at, marketplace_address, nft_address, 
                nft_owner_address, min_bid, max_bid, min_step, last_bid_at, 
                last_member, last_bid, is_canceled, end_time)
        
    except Exception as e:
        print(f'[parse_auction_stack] Error: {e}')
        return None

def parse_offer_stack(stack: list) -> tuple:
    """Parse offer sale stack"""
    try:
        action = 'SaleOffer'
        
        def hex_to_int(hex_str):
            if isinstance(hex_str, str) and hex_str.startswith('0x'):
                return int(hex_str, 16)
            return int(str(hex_str), 16) if str(hex_str) else 0
        
        is_complete = bool(hex_to_int(stack[1][1] if isinstance(stack[1], list) else stack[1]))
        created_at = hex_to_int(stack[2][1] if isinstance(stack[2], list) else stack[2])
        
        marketplace_address = parse_address_from_cell(stack[4])
        nft_address = parse_address_from_cell(stack[5])
        offer_owner_address = parse_address_from_cell(stack[6])
        
        price_hex = stack[7][1] if isinstance(stack[7], list) else stack[7]
        full_price = hex_to_int(price_hex) / 1_000_000_000

        return (action, is_complete, created_at, marketplace_address, 
                nft_address, offer_owner_address, full_price)
        
    except Exception as e:
        print(f'[parse_offer_stack] Error: {e}')
        return None

def parse_address_from_cell(stack_item) -> Optional[str]:
    """
    Extract address from cell - TON Center compatible
    Simplified version - returns raw cell data for now
    """
    try:
        if isinstance(stack_item, list) and len(stack_item) > 1:
            # TON Center v2 format: ["tvm.Cell", {"bytes": "base64boc"}]
            if stack_item[0] == 'tvm.Cell' and isinstance(stack_item[1], dict):
                cell_data = stack_item[1].get('bytes', '')
                if cell_data:
                    # For now, return placeholder. In production, parse with ton library
                    return f"cell_{cell_data[:20]}"
        
        # TON Center v3 format: {"type": "cell", "cell": "boc_hex"}
        elif isinstance(stack_item, dict) and stack_item.get('type') == 'cell':
            cell_data = stack_item.get('cell', '')
            if cell_data:
                return f"cell_{cell_data[:20]}"
        
        # Legacy format or unknown
        return None
        
    except Exception as e:
        print(f'[parse_address_from_cell] Error: {e}')
        return None