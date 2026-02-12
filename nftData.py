# nftData.py - TON Center NFT Data fetching (API v3 COMPATIBLE)
import aiohttp
import asyncio
import json
import re
from typing import Optional, Tuple
from config import getgems_api_url, getgems_query
from secretData import toncenter_api_key

# TON Center API configuration - CONSISTENTE CON main.py
TONCENTER_API = "https://toncenter.com/api/v3"
TONCENTER_HEADERS = {
    "accept": "application/json",
    "Content-Type": "application/json"
}
if toncenter_api_key:
    TONCENTER_HEADERS["X-API-Key"] = toncenter_api_key

async def get_nft_data(nft_address: str) -> Optional[tuple]:
    """Get NFT data using TON Center API v3 (async) - PRIMA PRIORITÀ"""
    try:
        print(f"[nftData] Fetching NFT data for {nft_address[-8:]}")
        
        async with aiohttp.ClientSession() as session:
            # METHOD 1: Usa l'endpoint dedicato /nft/getItems (API v3)
            url = f"{TONCENTER_API}/nft/getItems"
            
            # ✅ FORMATO CORRETTO per API v3
            payload = {
                "addresses": [nft_address]
            }
            
            print(f"[nftData] Calling /nft/getItems for {nft_address[-8:]}")
            
            async with session.post(url, headers=TONCENTER_HEADERS, 
                                  json=payload, timeout=15) as response:
                
                status = response.status
                print(f"[nftData] /nft/getItems status: {status}")
                
                if status == 200:
                    data = await response.json()
                    print(f"[nftData] Response keys: {list(data.keys())}")
                    
                    if data.get('nft_items') and len(data['nft_items']) > 0:
                        nft_item = data['nft_items'][0]
                        
                        # Estrai dati correttamente
                        collection_address = nft_item.get('collection', {}).get('address', '')
                        owner_address = nft_item.get('owner', {}).get('address', '')
                        nft_name = nft_item.get('metadata', {}).get('name', f'NFT {nft_address[-8:]}')
                        
                        # Get image from previews (API v3 format)
                        nft_image = ''
                        previews = nft_item.get('previews', [])
                        if previews:
                            # Prendi l'immagine più grande disponibile
                            nft_image = previews[-1].get('url', '')
                        
                        print(f"[nftData] ✅ Got NFT data via /nft/getItems:")
                        print(f"  Name: {nft_name}")
                        print(f"  Collection: {collection_address[-8:] if collection_address else 'None'}")
                        print(f"  Owner: {owner_address[-8:] if owner_address else 'None'}")
                        print(f"  Has image: {'Yes' if nft_image else 'No'}")
                        
                        return (True, collection_address, owner_address, 
                                nft_name, nft_image)
                    else:
                        print(f"[nftData] ⚠️ No nft_items in response")
                else:
                    error_text = await response.text()
                    print(f"[nftData] ❌ /nft/getItems error: {error_text[:200]}")
        
        # METHOD 2: Fallback to runGetMethod
        print(f"[nftData] Falling back to runGetMethod for {nft_address[-8:]}")
        return await get_nft_data_via_getmethod(nft_address)
        
    except Exception as e:
        print(f'[nftData] Error for NFT {nft_address[-8:]}: {e}')
        traceback.print_exc()
        return None

async def get_nft_data_via_getmethod(nft_address: str) -> Optional[tuple]:
    """Get NFT data via runGetMethod (fallback) - API v3 COMPATIBLE"""
    try:
        print(f"[nftData] Trying runGetMethod for {nft_address[-8:]}")
        
        async with aiohttp.ClientSession() as session:
            url = f"{TONCENTER_API}/runGetMethod"
            payload = {
                "address": nft_address,
                "method": "get_nft_data",
                "stack": []
            }
            
            async with session.post(url, headers=TONCENTER_HEADERS, 
                                  json=payload, timeout=15) as response:
                
                if response.status != 200:
                    return None
                
                data = await response.json()
                
                # ✅ GESTIONE FORMATI API v3
                stack = None
                if "ok" in data and data.get("ok") and "result" in data:
                    stack = data["result"].get("stack", [])
                elif "success" in data and data.get("success"):
                    stack = data.get("stack", [])
                elif "stack" in data:
                    stack = data.get("stack", [])
                else:
                    return None
                
                if not stack or len(stack) < 5:
                    return None
                
                # ✅ FUNZIONE PER CONVERTIRE DICT IN INT
                def get_int_from_stack_item(item):
                    """Estrae intero da stack item (dict, list, string)"""
                    try:
                        # CASO 1: Dict API v3
                        if isinstance(item, dict):
                            if 'value' in item:
                                val = item['value']
                            elif 'num' in item:
                                val = item['num']
                            else:
                                return 0
                        # CASO 2: List pytonlib
                        elif isinstance(item, list) and len(item) > 1:
                            val = item[1]
                        # CASO 3: Stringa
                        elif isinstance(item, str):
                            val = item
                        else:
                            return 0
                        
                        # Converti in intero
                        val = str(val).strip()
                        if val.startswith('0x'):
                            return int(val, 16)
                        elif val.isdigit():
                            return int(val)
                        else:
                            try:
                                return int(val, 16)
                            except:
                                return 0
                    except:
                        return 0
                
                # ✅ FUNZIONE PER PARSARE INDIRIZZI
                def get_address_from_stack_item(item):
                    """Estrae indirizzo da stack item"""
                    try:
                        # Usa la funzione esistente da functions.py
                        from functions import parse_address_from_cell
                        return parse_address_from_cell(item)
                    except:
                        # Fallback
                        if isinstance(item, dict) and 'cell' in item:
                            return f"0:{item['cell'][:64]}"
                        return None
                
                # Estrai init (bool)
                init_val = get_int_from_stack_item(stack[0])
                init = bool(init_val)
                
                # Estrai collection address (indice 2)
                collection_address = get_address_from_stack_item(stack[2])
                
                # Estrai owner address (indice 3)
                owner_address = get_address_from_stack_item(stack[3])
                
                # Ottieni metadata esterni
                nft_name, nft_image = await get_nft_metadata_external(nft_address)
                
                return (init, collection_address, owner_address, 
                        nft_name or f"NFT {nft_address[-8:]}", nft_image or '')
        
        return None
        
    except Exception as e:
        print(f'[nftData] Error in get_nft_data_via_getmethod: {e}')
        traceback.print_exc()
        return None

def parse_real_address_from_stack_item(stack_item) -> Optional[str]:
    """
    Parse REAL TON address from stack item - FIXED VERSION
    Supporta formati API v2 e v3
    """
    try:
        print(f"[parse_real_address] Parsing stack item: type={type(stack_item)}, value={str(stack_item)[:50]}")
        
        # CASO 1: Formato API v3 - {"type": "cell", "cell": "boc_hex_string"}
        if isinstance(stack_item, dict):
            if stack_item.get('type') == 'cell':
                cell_boc = stack_item.get('cell', '')
                if cell_boc:
                    # Usa la libreria 'ton' per parsare il BOC e estrarre l'indirizzo
                    try:
                        # Importa dinamicamente per non bloccare se non installato
                        from ton.utils import read_address_from_cell
                        from ton.boc import Cell
                        
                        # Decodifica il BOC hex
                        cell = Cell.one_from_boc(cell_boc)
                        address = read_address_from_cell(cell)
                        
                        if address and address != 'addr_none':
                            print(f"[parse_real_address] ✅ Parsed address: {address[-8:]}")
                            return address
                    except ImportError:
                        print("[parse_real_address] ⚠️ 'ton' library not installed, using fallback")
                    except Exception as e:
                        print(f"[parse_real_address] ❌ Error parsing cell: {e}")
                
                # Fallback: restituisci None se non possiamo parsare
                return None
            
            # CASO 2: Indirizzo diretto in dict
            elif 'address' in stack_item:
                return stack_item['address']
        
        # CASO 3: Formato API v2 legacy - ["tvm.Cell", {"bytes": "base64"}]
        elif isinstance(stack_item, list) and len(stack_item) == 2:
            if stack_item[0] == 'tvm.Cell' and isinstance(stack_item[1], dict):
                cell_b64 = stack_item[1].get('bytes', '')
                if cell_b64:
                    try:
                        import base64
                        from ton.utils import read_address_from_cell
                        from ton.boc import Cell
                        
                        # Decodifica base64
                        cell_bytes = base64.b64decode(cell_b64)
                        cell = Cell.one_from_boc(cell_bytes)
                        address = read_address_from_cell(cell)
                        
                        if address and address != 'addr_none':
                            print(f"[parse_real_address] ✅ Parsed legacy address: {address[-8:]}")
                            return address
                    except Exception as e:
                        print(f"[parse_real_address] ❌ Error parsing legacy cell: {e}")
        
        # CASO 4: Stringa hex che potrebbe essere un indirizzo
        elif isinstance(stack_item, str):
            # Se sembra un indirizzo TON (inizia con EQ o UQ)
            if stack_item.startswith(('EQ', 'UQ', '0:EQ', '0:UQ')):
                # Pulisci l'indirizzo
                address = stack_item.replace('0:', '')
                print(f"[parse_real_address] ✅ Direct address string: {address[-8:]}")
                return address
            
            # Se è hex, potrebbe essere un BOC codificato
            elif stack_item.startswith('0x') or (len(stack_item) > 40 and all(c in '0123456789abcdefABCDEF' for c in stack_item)):
                print(f"[parse_real_address] ⚠️ Hex string, might need parsing: {stack_item[:20]}...")
                return None  # Non possiamo parsare senza libreria
        
        print(f"[parse_real_address] ❌ Could not parse address from: {type(stack_item)}")
        return None
        
    except Exception as e:
        print(f"[parse_real_address] Exception: {e}")
        return None

async def get_nft_metadata_external(nft_address: str) -> Tuple[Optional[str], Optional[str]]:
    """Get NFT metadata from external APIs (Getgems)"""
    try:
        print(f"[metadata] Fetching external metadata for {nft_address[-8:]}")
        
        # Query GraphQL per Getgems
        query = '''
        query($address: String!) {
          nfts(where: {address: {_eq: $address}}) {
            metadata
            content {
              ... on NftContentImage {
                image {
                  sized(width: 500, height: 500)
                }
              }
            }
          }
        }
        '''
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                getgems_api_url,
                json={"query": query, "variables": {"address": nft_address}},
                timeout=10
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    nfts = data.get('data', {}).get('nfts', [])
                    
                    if nfts:
                        metadata_str = nfts[0].get('metadata', '{}')
                        try:
                            metadata = json.loads(metadata_str)
                            nft_name = metadata.get('name', f"NFT {nft_address[-8:]}")
                            
                            # Get image
                            nft_image = ''
                            content = nfts[0].get('content', {})
                            if content.get('image'):
                                nft_image = content['image'].get('sized', '')
                            
                            print(f"[metadata] ✅ Got external metadata: {nft_name}")
                            return nft_name, nft_image
                        except json.JSONDecodeError:
                            print(f"[metadata] ❌ Invalid JSON in metadata")
                    else:
                        print(f"[metadata] ⚠️ No NFT found in external API")
                else:
                    print(f"[metadata] ❌ External API error: {response.status}")
        
        return f"NFT {nft_address[-8:]}", None
        
    except Exception as e:
        print(f'[metadata] Error: {e}')
        return f"NFT {nft_address[-8:]}", None

async def get_collection_floor(col_address: str) -> Tuple[Optional[float], Optional[str]]:
    """Get collection floor price from Getgems (async)"""
    try:
        print(f"[floor] Fetching floor for collection {col_address[-8:]}")
        
        json_data = {
            'operationName': 'nftSearch',
            'query': getgems_query,
            'variables': {
                'count': 30,
                'query': f'{{"$and":[{{"collectionAddress":"{col_address}"}}]}}',
                'sort': '[{"isOnSale":{"order":"desc"}},{"price":{"order":"asc"}},{"index":{"order":"asc"}}]'
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                getgems_api_url, 
                json=json_data, 
                timeout=15
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    edges = data.get('data', {}).get('alphaNftItemSearch', {}).get('edges', [])
                    
                    print(f"[floor] Found {len(edges)} items on sale")
                    
                    for item in edges:
                        node = item.get('node', {})
                        sale = node.get('sale', {})
                        
                        if 'fullPrice' in sale:
                            # Convert from nanoTON to TON
                            floor_price = int(sale['fullPrice']) / 1_000_000_000
                            floor_link = node.get('address', '')
                            
                            print(f"[floor] ✅ Floor price: {floor_price} TON")
                            return floor_price, floor_link
                    
                    print(f"[floor] ⚠️ No items on sale found")
                    return None, None
        
        return None, None
        
    except Exception as e:
        print(f'[floor] Error for collection {col_address[-8:]}: {e}')
        return None, None
