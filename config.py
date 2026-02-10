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

# Royalty addresses to monitor
royalty_addresses = ['0:68F3A076D3451A18FD41E05C71B4C020545D46B2757064E65825DED0C49BF02C']

# NFT collections to track
collections_list = ['0:388b9f22b92f4351846d519f7bb19a399a791b898501a565d039eddd11409c3f']

# === MARKETPLACES ===
markets = {
    'EQBYTuYbLf8INxFtD8tQeNk5ZLy-nAX9ahQbG_yl1qQ-GEMS': 'Getgems',
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

# Aggiungi queste righe alla fine di config.py, PRIMA dell'ultima riga:

# CoinMarketCap headers
cmc_headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': ''  # Sarà popolata dinamicamente da secretData.cmc_token
}
