# nftData.py - TON Center NFT Data fetching
import aiohttp
import asyncio
import json
import re
from typing import Optional, Tuple
from config import getgems_api_url, getgems_query
from secretData import toncenter_api_key

# TON Center API configuration
TONCENTER_API = "https://toncenter.com/api/v3"
TONCENTER_HEADERS = {
    "accept": "application/json",
    "Content-Type": "application/json"
}
if toncenter_api_key:
    TONCENTER_HEADERS["X-API-Key"] = toncenter_api_key

async def get_nft_data(nft_address: str) -> Optional[tuple]:
    """Get NFT data using TON Center API (async)"""
    try:
        async with aiohttp.ClientSession() as session:
            # Method 1: Try to get NFT info directly
            url = f"{TONCENTER_API}/nft/getItems"
            params = {
                "addresses": [nft_address]
            }
            
            async with session.post(url, headers=TONCENTER_HEADERS, 
                                  json=params, timeout=15) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('nft_items') and len(data['nft_items']) > 0:
                        nft_item = data['nft_items'][0]
                        
                        collection_address = nft_item.get('collection', {}).get('address', '')
                        owner_address = nft_item.get('owner', {}).get('address', '')
                        nft_name = nft_item.get('metadata', {}).get('name', 'Unknown NFT')
                        
                        # Get image from previews
                        nft_image = ''
                        previews = nft_item.get('previews', [])
                        if previews:
                            nft_image = previews[-1].get('url', '')
                        
                        return (True, collection_address, owner_address, 
                                nft_name, nft_image)
        
        # Method 2: Fallback to runGetMethod for get_nft_data
        return await get_nft_data_via_getmethod(nft_address)
        
    except Exception as e:
        print(f'[get_nft_data] Error for NFT {nft_address[-6:]}: {e}')
        return None

async def get_nft_data_via_getmethod(nft_address: str) -> Optional[tuple]:
    """Get NFT data via runGetMethod (fallback)"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{TONCENTER_API}/runGetMethod"
            params = {
                "address": nft_address,
                "method": "get_nft_data",
                "stack": []
            }
            
            async with session.post(url, headers=TONCENTER_HEADERS, 
                                  json=params, timeout=15) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('success', False):
                        stack = data.get('stack', [])
                        
                        # Parse the stack to extract NFT data
                        if len(stack) >= 5:
                            # Stack format: [init, index, collection_addr, owner_addr, content]
                            init = bool(int(stack[0].get('value', '0'), 16))
                            
                            # Get collection address from cell
                            collection_cell = stack[2]
                            collection_address = extract_address_from_cell(collection_cell)
                            
                            # Get owner address from cell
                            owner_cell = stack[3]
                            owner_address = extract_address_from_cell(owner_cell)
                            
                            # Try to get metadata from external source
                            nft_name, nft_image = await get_nft_metadata_external(nft_address)
                            
                            return (init, collection_address, owner_address, 
                                    nft_name or f"NFT {nft_address[-6:]}", nft_image or '')
        
        return None
        
    except Exception as e:
        print(f'[get_nft_data_via_getmethod] Error: {e}')
        return None

def extract_address_from_cell(cell_data) -> str:
    """Extract address from cell data (simplified)"""
    try:
        # This is a simplified version. In production, use ton library
        if isinstance(cell_data, dict) and cell_data.get('type') == 'cell':
            cell_hex = cell_data.get('cell', '')
            # Return placeholder - actual parsing requires ton library
            return f"addr_{cell_hex[:16]}"
        return ''
    except:
        return ''

async def get_nft_metadata_external(nft_address: str) -> Tuple[Optional[str], Optional[str]]:
    """Get NFT metadata from external APIs"""
    try:
        # Try Getgems GraphQL API
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
                            nft_name = metadata.get('name', f"NFT {nft_address[-6:]}")
                            
                            # Get image
                            nft_image = ''
                            content = nfts[0].get('content', {})
                            if content.get('image'):
                                nft_image = content['image'].get('sized', '')
                            
                            return nft_name, nft_image
                        except:
                            pass
        
        return None, None
        
    except Exception as e:
        print(f'[get_nft_metadata_external] Error: {e}')
        return None, None

async def get_collection_floor(col_address: str) -> Tuple[Optional[float], Optional[str]]:
    """Get collection floor price from Getgems (async)"""
    try:
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
                    
                    for item in edges:
                        node = item.get('node', {})
                        sale = node.get('sale', {})
                        
                        if 'fullPrice' in sale:
                            # Convert from nanoTON to TON
                            floor_price = int(sale['fullPrice']) / 1_000_000_000
                            floor_link = node.get('address', '')
                            return floor_price, floor_link
        
        return None, None
        
    except Exception as e:
        print(f'[get_collection_floor] Error for collection {col_address[-6:]}: {e}')
        return None, None