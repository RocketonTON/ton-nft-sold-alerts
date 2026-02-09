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
            # ✅ FORMATO CORRETTO per API v3 runGetMethod
            url = f"{TONCENTER_API}/runGetMethod"
            payload = {
                "address": nft_address,  # ✅ "address" è corretto per runGetMethod!
                "method": "get_nft_data",
                "stack": []
            }
            
            print(f"[nftData] runGetMethod payload: {json.dumps(payload, indent=2)[:200]}...")
            
            async with session.post(url, headers=TONCENTER_HEADERS, 
                                  json=payload, timeout=15) as response:
                
                status = response.status
                print(f"[nftData] runGetMethod status: {status}")
                
                if status == 200:
                    data = await response.json()
                    print(f"[nftData] runGetMethod response keys: {list(data.keys())}")
                    
                    # ✅ GESTISCE ENTRAMBI I FORMATI (v3 e legacy)
                    if "ok" in data:
                        # Formato v3: {"ok": true, "result": {"stack": [...]}}
                        if data.get("ok") and "result" in data:
                            stack = data["result"].get("stack", [])
                            print(f"[nftData] ✅ runGetMethod v3 format, stack size: {len(stack)}")
                        else:
                            print(f"[nftData] ❌ runGetMethod v3 format failed")
                            return None
                    elif "success" in data:
                        # Formato legacy v2
                        if data.get("success", False):
                            stack = data.get("stack", [])
                            print(f"[nftData] ✅ runGetMethod legacy format, stack size: {len(stack)}")
                        else:
                            print(f"[nftData] ❌ runGetMethod legacy format failed")
                            return None
                    elif "stack" in data:
                        stack = data.get("stack", [])
                        print(f"[nftData] ✅ runGetMethod direct stack, size: {len(stack)}")
                    else:
                        print(f"[nftData] ❌ Unknown runGetMethod format")
                        return None
                    
                    # DEBUG: mostra struttura stack
                    print(f"[nftData] Stack structure (first 5 items):")
                    for i, item in enumerate(stack[:5]):
                        print(f"  [{i}] type: {type(item)}, value: {str(item)[:80]}")
                    
                    # Parse dello stack
                    if len(stack) >= 5:
                        # Stack format: [init, index, collection_addr, owner_addr, content]
                        try:
                            init = bool(int(str(stack[0]), 16) if isinstance(stack[0], str) and stack[0].startswith('0x') else int(stack[0]))
                            
                            # Estrai indirizzi REALI dallo stack
                            collection_address = parse_real_address_from_stack_item(stack[2])
                            owner_address = parse_real_address_from_stack_item(stack[3])
                            
                            print(f"[nftData] Parsed from stack:")
                            print(f"  init: {init}")
                            print(f"  collection: {collection_address[-8:] if collection_address else 'None'}")
                            print(f"  owner: {owner_address[-8:] if owner_address else 'None'}")
                            
                            # Ottieni metadata esterni
                            nft_name, nft_image = await get_nft_metadata_external(nft_address)
                            
                            return (init, collection_address, owner_address, 
                                    nft_name or f"NFT {nft_address[-8:]}", nft_image or '')
                            
                        except Exception as parse_error:
                            print(f"[nftData] ❌ Error parsing stack: {parse_error}")
                            return None
                    
                    print(f"[nftData] ❌ Stack too small: {len(stack)} items")
                    return None
                
                else:
                    error_text = await response.text()
                    print(f'[nftData] runGetMethod error {status}: {error_text[:200]}')
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