# functions.py - TON Center API v3 compatible functions
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
                        # Extract TON price from CMC response
                        ton_data = data.get('data', {})
                        if ton_data:
                            # TON's ID is 11419 in CMC
                            quote = ton_data.get('11419', {}).get('quote', {}).get('USD', {})
                            usd = quote.get('price', 0)
                            return round(float(ton) * usd, 2)
        
        # Final fallback: fixed approximate value
        return round(float(ton) * 7.5, 2)
        
    except Exception as e:
        print(f'[convert_ton_to_usd] Error: {e}')
        return None

def parse_sale_stack(stack: list) -> Optional[tuple]:
    """
    Parse sale stack - TON Center API v3 COMPATIBLE
    Updated to handle v3 stack format
    """
    try:
        if not stack or len(stack) < 7:
            print(f"[parse_sale_stack] Stack too small: {len(stack)} items")
            return None
        
        # DEBUG: Show stack structure
        print(f"[parse_sale_stack] Stack has {len(stack)} items")
        for i, item in enumerate(stack[:10]):  # Show first 10 items
            print(f"  [{i}] type: {type(item)}, value: {str(item)[:80]}")
        
        # Helper to extract values from stack items (v3 compatible)
        def get_value(item, default='0'):
            if isinstance(item, dict):
                # API v3 format: {"type": "num", "value": "0x..."}
                if 'value' in item:
                    return item['value']
                elif 'num' in item:
                    return item['num']
            elif isinstance(item, list) and len(item) > 1:
                # Legacy format: ["tvm.num", "0x..."]
                return item[1]
            elif isinstance(item, str):
                return item
            return default
        
        # Check sale type from first stack item
        sale_type_value = get_value(stack[0])
        print(f"[parse_sale_stack] Sale type raw value: {sale_type_value}")
        
        # Determine sale type
        sale_type = None
        if '0x415543' in str(sale_type_value) or 'AUC' in str(sale_type_value).upper():
            sale_type = 'SaleAuction'
        elif '0x4f46464552' in str(sale_type_value) or 'OFFER' in str(sale_type_value).upper():
            sale_type = 'SaleOffer'
        else:
            # Default to SaleFixPrice if not auction or offer
            sale_type = 'SaleFixPrice'
        
        print(f"[parse_sale_stack] Detected sale type: {sale_type}")
        
        # Call appropriate parser
        if sale_type == 'SaleAuction':
            return parse_auction_stack(stack)
        elif sale_type == 'SaleOffer':
            return parse_offer_stack(stack)
        else:
            return parse_fixprice_stack(stack)
        
    except Exception as e:
        print(f'[parse_sale_stack] Error: {e}')
        import traceback
        traceback.print_exc()
        return None

def parse_fixprice_stack(stack: list) -> tuple:
    """Parse fixprice sale stack - API v3 COMPATIBLE"""
    try:
        print(f"[parse_fixprice_stack] Starting parse...")
        
        action = 'SaleFixPrice'
        
        def hex_to_int(hex_str):
            """Convert hex string to integer, handling various formats"""
            if not hex_str:
                return 0
            
            try:
                # Handle API v3 format: {"type": "num", "value": "0x..."}
                if isinstance(hex_str, dict) and 'value' in hex_str:
                    hex_str = hex_str['value']
                elif isinstance(hex_str, dict) and 'num' in hex_str:
                    hex_str = hex_str['num']
                
                # Clean hex string
                hex_str = str(hex_str).strip()
                if hex_str.startswith('0x'):
                    return int(hex_str, 16)
                elif hex_str.isdigit() or (hex_str[1:].isdigit() and hex_str[0] == '-'):
                    return int(hex_str)
                else:
                    # Try to parse as hex even without 0x prefix
                    try:
                        return int(hex_str, 16)
                    except:
                        return 0
            except Exception as e:
                print(f"[hex_to_int] Error parsing '{hex_str}': {e}")
                return 0
        
        # Parse stack items with v3 compatibility
        is_complete = False
        created_at = 0
        marketplace_address = None
        nft_address = None
        nft_owner_address = None
        full_price = 0
        
        # Stack indices for SaleFixPrice (v3 format may vary)
        if len(stack) >= 7:
            is_complete = bool(hex_to_int(stack[1]))
            created_at = hex_to_int(stack[2])
            
            # Parse addresses from cells
            marketplace_address = parse_address_from_cell_v3(stack[3])
            nft_address = parse_address_from_cell_v3(stack[4])
            
            if len(stack) > 5:
                nft_owner_address = parse_address_from_cell_v3(stack[5])
            
            if len(stack) > 6:
                price_value = stack[6]
                full_price = hex_to_int(price_value) / 1_000_000_000  # nanoTON to TON
        
        print(f"[parse_fixprice_stack] Parsed:")
        print(f"  is_complete: {is_complete}")
        print(f"  created_at: {created_at}")
        print(f"  marketplace: {marketplace_address[-8:] if marketplace_address else 'None'}")
        print(f"  nft_address: {nft_address[-8:] if nft_address else 'None'}")
        print(f"  owner: {nft_owner_address[-8:] if nft_owner_address else 'None'}")
        print(f"  price: {full_price} TON")
        
        return (action, is_complete, created_at, marketplace_address, 
                nft_address, nft_owner_address, full_price)
        
    except Exception as e:
        print(f'[parse_fixprice_stack] Error: {e}')
        import traceback
        traceback.print_exc()
        return None

def parse_auction_stack(stack: list) -> tuple:
    """Parse auction sale stack - API v3 COMPATIBLE"""
    try:
        print(f"[parse_auction_stack] Starting parse...")
        
        action = 'SaleAuction'
        
        def hex_to_int(hex_str):
            """Convert hex string to integer"""
            if not hex_str:
                return 0
            
            try:
                if isinstance(hex_str, dict) and 'value' in hex_str:
                    hex_str = hex_str['value']
                elif isinstance(hex_str, dict) and 'num' in hex_str:
                    hex_str = hex_str['num']
                
                hex_str = str(hex_str).strip()
                if hex_str.startswith('0x'):
                    return int(hex_str, 16)
                else:
                    try:
                        return int(hex_str, 16)
                    except:
                        return int(hex_str) if hex_str.isdigit() else 0
            except:
                return 0
        
        # Default values
        is_end = False
        created_at = 0
        marketplace_address = None
        nft_address = None
        nft_owner_address = None
        min_bid = 0
        max_bid = 0
        min_step = 0
        last_bid_at = 0
        last_member = None
        last_bid = 0
        is_canceled = False
        end_time = 0
        
        # Parse based on stack size
        if len(stack) >= 20:
            # Full auction stack
            is_end = bool(hex_to_int(stack[1]))
            end_time = hex_to_int(stack[2])
            marketplace_address = parse_address_from_cell_v3(stack[3])
            nft_address = parse_address_from_cell_v3(stack[4])
            nft_owner_address = parse_address_from_cell_v3(stack[5])
            last_bid = hex_to_int(stack[6]) / 1_000_000_000
            last_member = parse_address_from_cell_v3(stack[7])
            min_step = hex_to_int(stack[8]) / 1_000_000_000
            # ... more fields as needed
            min_bid = hex_to_int(stack[16]) / 1_000_000_000
            max_bid = hex_to_int(stack[15]) / 1_000_000_000
            created_at = hex_to_int(stack[17])
            last_bid_at = hex_to_int(stack[18])
            is_canceled = bool(hex_to_int(stack[19]))
        elif len(stack) >= 12:
            # Simplified auction format
            is_end = bool(hex_to_int(stack[1]))
            marketplace_address = parse_address_from_cell_v3(stack[2])
            nft_address = parse_address_from_cell_v3(stack[3])
            nft_owner_address = parse_address_from_cell_v3(stack[4])
            min_bid = hex_to_int(stack[5]) / 1_000_000_000
            max_bid = hex_to_int(stack[6]) / 1_000_000_000
        
        print(f"[parse_auction_stack] Parsed auction:")
        print(f"  is_end: {is_end}")
        print(f"  nft: {nft_address[-8:] if nft_address else 'None'}")
        print(f"  min_bid: {min_bid} TON")
        print(f"  max_bid: {max_bid} TON")
        
        return (action, is_end, created_at, marketplace_address, nft_address, 
                nft_owner_address, min_bid, max_bid, min_step, last_bid_at, 
                last_member, last_bid, is_canceled, end_time)
        
    except Exception as e:
        print(f'[parse_auction_stack] Error: {e}')
        import traceback
        traceback.print_exc()
        return None

def parse_offer_stack(stack: list) -> tuple:
    """Parse offer sale stack - API v3 COMPATIBLE"""
    try:
        print(f"[parse_offer_stack] Starting parse...")
        
        action = 'SaleOffer'
        
        def hex_to_int(hex_str):
            """Convert hex string to integer"""
            if not hex_str:
                return 0
            
            try:
                if isinstance(hex_str, dict) and 'value' in hex_str:
                    hex_str = hex_str['value']
                elif isinstance(hex_str, dict) and 'num' in hex_str:
                    hex_str = hex_str['num']
                
                hex_str = str(hex_str).strip()
                if hex_str.startswith('0x'):
                    return int(hex_str, 16)
                else:
                    try:
                        return int(hex_str, 16)
                    except:
                        return int(hex_str) if hex_str.isdigit() else 0
            except:
                return 0
        
        # Default values
        is_complete = False
        created_at = 0
        marketplace_address = None
        nft_address = None
        offer_owner_address = None
        full_price = 0
        
        if len(stack) >= 8:
            is_complete = bool(hex_to_int(stack[1]))
            created_at = hex_to_int(stack[2])
            marketplace_address = parse_address_from_cell_v3(stack[4])
            nft_address = parse_address_from_cell_v3(stack[5])
            offer_owner_address = parse_address_from_cell_v3(stack[6])
            full_price = hex_to_int(stack[7]) / 1_000_000_000
        
        print(f"[parse_offer_stack] Parsed offer:")
        print(f"  is_complete: {is_complete}")
        print(f"  nft: {nft_address[-8:] if nft_address else 'None'}")
        print(f"  price: {full_price} TON")
        
        return (action, is_complete, created_at, marketplace_address, 
                nft_address, offer_owner_address, full_price)
        
    except Exception as e:
        print(f'[parse_offer_stack] Error: {e}')
        import traceback
        traceback.print_exc()
        return None

def parse_address_from_cell_v3(stack_item) -> Optional[str]:
    """
    Extract address from cell - TON Center API v3 COMPATIBLE
    This function is aligned with the one in nftData.py
    """
    try:
        print(f"[parse_address_from_cell_v3] Parsing: type={type(stack_item)}")
        
        # Try to use the function from nftData if available
        try:
            from nftData import parse_real_address_from_stack_item
            address = parse_real_address_from_stack_item(stack_item)
            if address:
                print(f"[parse_address_from_cell_v3] ✅ Parsed via nftData: {address[-8:]}")
                return address
        except ImportError:
            print("[parse_address_from_cell_v3] ⚠️ Could not import from nftData")
        
        # CASO 1: Formato API v3 - {"type": "cell", "cell": "boc_hex_string"}
        if isinstance(stack_item, dict):
            if stack_item.get('type') == 'cell':
                cell_boc = stack_item.get('cell', '')
                if cell_boc:
                    print(f"[parse_address_from_cell_v3] Found v3 cell: {cell_boc[:30]}...")
                    # Try to parse with ton library
                    try:
                        from ton.utils import read_address_from_cell
                        from ton.boc import Cell
                        
                        cell = Cell.one_from_boc(cell_boc)
                        address = read_address_from_cell(cell)
                        if address and address != 'addr_none':
                            print(f"[parse_address_from_cell_v3] ✅ Parsed with ton lib: {address[-8:]}")
                            return address
                    except ImportError:
                        print("[parse_address_from_cell_v3] ❌ 'ton' library not installed")
                    except Exception as e:
                        print(f"[parse_address_from_cell_v3] ❌ Error parsing: {e}")
                
                return None
            
            # Direct address in dict
            elif 'address' in stack_item:
                address = stack_item['address']
                print(f"[parse_address_from_cell_v3] ✅ Direct address: {address[-8:]}")
                return address
        
        # CASO 2: Formato API v2 legacy - ["tvm.Cell", {"bytes": "base64"}]
        elif isinstance(stack_item, list) and len(stack_item) == 2:
            if stack_item[0] == 'tvm.Cell' and isinstance(stack_item[1], dict):
                cell_b64 = stack_item[1].get('bytes', '')
                if cell_b64:
                    print(f"[parse_address_from_cell_v3] Found legacy cell")
                    try:
                        import base64
                        from ton.utils import read_address_from_cell
                        from ton.boc import Cell
                        
                        cell_bytes = base64.b64decode(cell_b64)
                        cell = Cell.one_from_boc(cell_bytes)
                        address = read_address_from_cell(cell)
                        if address and address != 'addr_none':
                            print(f"[parse_address_from_cell_v3] ✅ Parsed legacy: {address[-8:]}")
                            return address
                    except Exception as e:
                        print(f"[parse_address_from_cell_v3] ❌ Error parsing legacy: {e}")
        
        # CASO 3: Stringa diretta che sembra un indirizzo TON
        elif isinstance(stack_item, str):
            # Check if it looks like a TON address
            clean_str = stack_item.strip()
            if clean_str.startswith(('EQ', 'UQ', '0:EQ', '0:UQ')):
                address = clean_str.replace('0:', '')
                print(f"[parse_address_from_cell_v3] ✅ Direct string address: {address[-8:]}")
                return address
            
            # Might be a hex representation
            elif clean_str.startswith('0x') or len(clean_str) > 40:
                print(f"[parse_address_from_cell_v3] ⚠️ Hex string, needs parsing: {clean_str[:30]}...")
                # Could be a BOC in hex, need ton library to parse
                return None
        
        # CASO 4: Lista con indirizzo diretto
        elif isinstance(stack_item, list) and len(stack_item) > 0:
            # Check first element if it looks like an address
            first_item = stack_item[0]
            if isinstance(first_item, str) and first_item.startswith(('EQ', 'UQ')):
                print(f"[parse_address_from_cell_v3] ✅ Address in list: {first_item[-8:]}")
                return first_item
        
        print(f"[parse_address_from_cell_v3] ❌ Could not parse: {type(stack_item)}")
        return None
        
    except Exception as e:
        print(f"[parse_address_from_cell_v3] Exception: {e}")
        import traceback
        traceback.print_exc()
        return None

# Alias for backward compatibility
parse_address_from_cell = parse_address_from_cell_v3

# Helper function for hex conversion
def decode_hex_to_int(hex_value):
    """Helper to decode hex values from various formats"""
    try:
        if isinstance(hex_value, dict):
            if 'value' in hex_value:
                hex_str = hex_value['value']
            elif 'num' in hex_value:
                hex_str = hex_value['num']
            else:
                return 0
        elif isinstance(hex_value, list) and len(hex_value) > 1:
            hex_str = hex_value[1]
        else:
            hex_str = str(hex_value)
        
        hex_str = hex_str.strip()
        if hex_str.startswith('0x'):
            return int(hex_str, 16)
        elif hex_str:
            # Try hex without prefix
            try:
                return int(hex_str, 16)
            except:
                # Try decimal
                try:
                    return int(hex_str)
                except:
                    return 0
        return 0
    except Exception as e:
        print(f"[decode_hex_to_int] Error: {e}")
        return 0