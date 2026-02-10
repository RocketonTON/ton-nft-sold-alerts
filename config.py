# config.py - TON Center Configuration
import pathlib
import os

current_path = pathlib.Path(__file__).parent.resolve()

# === TON CENTER API CONFIG ===
TONCENTER_API_V3 = "https://toncenter.com/api/v3"
TONCENTER_API_V2 = "https://toncenter.com/api/v2"
TONCENTER_RATE_LIMIT = 1  # secondi tra le richieste


# === BOT CONFIGURATION ===
trs_limit = 25

# Royalty addresses to monitor - FORMATO RAW (0:...) MAIUSCOLO
royalty_addresses = [
    '0:68F3A076D3451A18FD41E05C71B4C020545D46B2757064E65825DED0C49BF02C',
    '0:A3935861F79DAF59A13D6D182E1640210C02F98E3DF18FDA74B8F5AB141ABF18'
]

# NFT collections to track - FORMATO RAW (0:...) MAIUSCOLO
collections_list = [
    '0:388B9F22B92F4351846D519F7BB19A399A791B898501A565D039EDDD11409C3F'
]

# === MARKETPLACES ===
# NOTA: I marketplace possono avere DUE formati:
# 1. Indirizzi EQ per link web (nelle markets_links)
# 2. Indirizzi RAW dei contratti di vendita per la logica interna (se necessario)
markets = {
    # Contratti marketplace in formato RAW (se usati per logica)
    '0:584EE61B2DFF0837116D0FCB5078D93964BCBE9C05FD6A141B1BFCA5D6A43E18': 'Getgems',
    '0:83CBEFE239C49E33F863BB4D6127E6E3056CBAA155D1F83CEF675B146D747F17': 'Getgems',  # Altro contratto Getgems
    '0:6F00F7A3618D3063DCF5E783CBC9DBD87D634161FBBE1B7A97F7D94BB3BD583C': 'Disintar',
    
    # Indirizzi EQ per compatibilità (usati principalmente per display)
    'EQCjc483caXMwWw2kwl2afFquAPO0LX1VyZbnZUs3toMYkk9': 'Getgems',
    'EQCgRvXbOJeFSRKnEg1D-i0SqDMlaNVGvpSSKCzDQU_wDAR4': 'Tonex',
    'EQDrLq-X6jKZNHAScgghh0h1iog3StK71zn8dcmrOj8jPWRA': 'Disintar',
    'EQAezbdnLVsLSq8tnVVzaHxxkKpoSYBNnn1673GXWsA-Lu_w': 'Diamonds',
}

markets_links = {
    'Getgems': 'https://getgems.io/nft/',
    'Tonex': 'https://tonex.app/nft/market/nfts/',
    'Disintar': 'https://beta.disintar.io/object/',
    'Diamonds': 'https://ton.diamonds/explorer/',
}

getgems_user_url = 'https://getgems.io/user/'

# === EXTERNAL APIs ===
tonorg_price_url = 'https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd'
cmc_url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
getgems_api_url = 'https://api.getgems.io/graphql'
getgems_query = """
query nftSearch($count: Int!, $cursor: String, $query: String, $sort: String) {
  alphaNftItemSearch(first: $count, after: $cursor, query: $query, sort: $sort) {
    edges {
      node {
        address
        sale {
          ... on NftSaleFixPrice {
            fullPrice
          }
        }
      }
    }
  }
}
"""

# GET methods to try
get_methods = ['get_sale_data', 'get_offer_data']

# CoinMarketCap headers (sarà popolata dinamicamente da secretData.cmc_token)
cmc_headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': ''  # Sarà popolata dinamicamente da secretData.cmc_token
}

# === DEBUG/UTILITY ===
def verify_addresses():
    """Verifica che tutti gli indirizzi siano nel formato corretto"""
    print("\n[CONFIG] Verifica indirizzi:")
    
    # Verifica royalty_addresses
    print(f"  Royalty addresses ({len(royalty_addresses)}):")
    for i, addr in enumerate(royalty_addresses):
        valid = (addr.startswith('0:') and len(addr) == 67 and 
                 addr[2:].isupper() and all(c in '0123456789ABCDEF' for c in addr[2:]))
        status = "✅" if valid else "❌"
        print(f"    [{i}] {status} {addr[:30]}...")
    
    # Verifica collections_list
    print(f"  Collections ({len(collections_list)}):")
    for i, addr in enumerate(collections_list):
        valid = (addr.startswith('0:') and len(addr) == 67 and 
                 addr[2:].isupper() and all(c in '0123456789ABCDEF' for c in addr[2:]))
        status = "✅" if valid else "❌"
        print(f"    [{i}] {status} {addr[:30]}...")
    
    return True

# Esegui verifica all'importazione
if __name__ != "__main__":
    verify_addresses()
