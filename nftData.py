import requests
import json
import re
from pytoniq_core import Address, Cell, begin_cell

from config import getgems_api_url, getgems_query


async def get_nft_data(client, nft_address):
    """Ottiene i dati NFT usando pytoniq."""
    try:
        # Esegui get_nft_data method
        response = await client.run_get_method(
            address=nft_address,
            method='get_nft_data',
            stack=[]
        )
        
        if not response or len(response) < 5:
            print(f"[get_nft_data] Risposta invalida per {nft_address}")
            return None
        
        # Parsing dello stack (formato pytoniq)
        init = bool(response[0])  # int -> bool
        index = int(response[1])  # int
        
        # response[2] è una Cell o Slice con l'indirizzo della collezione
        collection_cell = response[2]
        if hasattr(collection_cell, 'to_cell'):
            collection_cell = collection_cell.to_cell()
        collection_address = collection_cell.begin_parse().load_address().to_str(1, 1, 1)
        
        # response[3] è l'owner address
        owner_cell = response[3]
        if hasattr(owner_cell, 'to_cell'):
            owner_cell = owner_cell.to_cell()
        owner_address = owner_cell.begin_parse().load_address().to_str(1, 1, 1)
        
        # response[4] è il content (Cell)
        content_cell = response[4]
        if hasattr(content_cell, 'to_cell'):
            content_cell = content_cell.to_cell()
        
        # Estrai il content come stringa
        nft_content = extract_content_from_cell(content_cell)
        
        # Se il content è vuoto, prova a leggere dai refs
        if nft_content == '':
            try:
                ref_cell = content_cell.refs[0] if content_cell.refs else None
                if ref_cell:
                    nft_content = extract_content_from_cell(ref_cell)
            except:
                pass
        
        # Chiama get_nft_content sulla collection
        try:
            # Prepara lo stack per get_nft_content: [index, individual_content]
            stack = [index, content_cell]
            
            content_response = await client.run_get_method(
                address=collection_address,
                method='get_nft_content',
                stack=stack
            )
            
            if content_response and len(content_response) > 0:
                full_content_cell = content_response[0]
                if hasattr(full_content_cell, 'to_cell'):
                    full_content_cell = full_content_cell.to_cell()
                
                base_content = extract_content_from_cell(full_content_cell)
                content = base_content + nft_content
                
                # Scarica i metadata
                if re.match(r'^ipfs', content):
                    metadata_url = f'https://ipfs.io/ipfs/{content.split("ipfs://")[-1]}'
                else:
                    metadata_url = content
                
                metadata = requests.get(metadata_url, timeout=10).json()
                
                nft_name = metadata.get('name', 'Unknown')
                nft_image = metadata.get('image', '')
                
                return init, collection_address, owner_address, nft_name, nft_image
        
        except Exception as e:
            print(f'[get_nft_data] Error getting NFT content for collection {collection_address}: {e}')
            return None
    
    except Exception as e:
        print(f'[get_nft_data] Error for NFT {nft_address}: {e}')
        return None


def extract_content_from_cell(cell):
    """Estrae il contenuto testuale da una Cell."""
    try:
        slice = cell.begin_parse()
        
        # Salta il primo byte (di solito 0x01 o simili)
        if slice.remaining_bits >= 8:
            slice.load_uint(8)
        
        # Leggi il resto come stringa
        bits = slice.remaining_bits
        if bits > 0:
            # Carica i bits rimanenti come bytes
            bytes_data = slice.load_bytes(bits // 8)
            return bytes_data.decode('utf-8', errors='ignore')
        
        return ''
    
    except Exception as e:
        return ''


def get_collection_floor(col_address):
    """Ottiene il floor price di una collezione da Getgems."""
    try:
        json_data = {
            'operationName': 'nftSearch',
            'query': getgems_query,
            'variables': {
                'count': 30,
                'query': '{"$and":[{"collectionAddress":"' + col_address + '"}]}',
                'sort': '[{"isOnSale":{"order":"desc"}},{"price":{"order":"asc"}},{"index":{"order":"asc"}}]'
            }
        }

        response = requests.post(getgems_api_url, json=json_data, timeout=10)
        data = response.json()['data']['alphaNftItemSearch']['edges']

        for item in data:
            if 'fullPrice' not in item['node']['sale']:
                continue

            # Converti da nanoTON a TON
            floor_price = int(item['node']['sale']['fullPrice']) / 1_000_000_000
            floor_link = item['node']['address']

            return floor_price, floor_link
        
        return None, None

    except Exception as e:
        print(f'[get_collection_floor] Error for collection {col_address}: {e}')
        return None, None
