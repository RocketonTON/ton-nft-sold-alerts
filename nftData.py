import requests
import json
import re

from config import getgems_api_url, getgems_query

# Rimuovi l'import di pytoniq_core
# from pytoniq_core import Address, Cell, begin_cell


async def get_nft_data(client, nft_address):
    """Ottiene i dati NFT usando TonAPI (non pytoniq)."""
    try:
        # Usa TonAPI invece di pytoniq
        url = f"https://tonapi.io/v2/nfts/{nft_address}"
        
        headers = {
            "Authorization": "Bearer AFNCCHEA2GXEAVQAAAAG6IP6JUAO5ZJORI5UJQFEV6OZVSP6XGSLRGQAGTFMTKGLWXD7AAI"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # Estrai i dati necessari
        collection_address = data.get("collection", {}).get("address")
        owner_address = data.get("owner", {}).get("address")
        nft_name = data.get("metadata", {}).get("name", "Unknown NFT")
        nft_image = data.get("previews", [{}])[0].get("url", "") if data.get("previews") else ""
        
        # TonAPI non ha campo "init", assumiamo True se abbiamo i dati
        init = bool(collection_address and owner_address)
        
        return init, collection_address, owner_address, nft_name, nft_image
    
    except Exception as e:
        print(f'[get_nft_data] Error for NFT {nft_address}: {e}')
        return None


# La funzione extract_content_from_cell non è più necessaria se non usi pytoniq
# Ma la manteniamo come fallback
def extract_content_from_cell(cell):
    """Funzione dummy - non usata con TonAPI."""
    return ""


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
