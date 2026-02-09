# config.py - TON Center Configuration
import pathlib
import os

current_path = pathlib.Path(__file__).parent.resolve()

# === TON CENTER API CONFIG ===
TONCENTER_API_V3 = "https://toncenter.com/api/v3"
TONCENTER_API_V2 = "https://toncenter.com/api/v2"

# === BOT CONFIGURATION ===
trs_limit = 50

# Royalty addresses to monitor
royalty_addresses = ['EQBo86B200UaGP1B4FxxtMAgVF1GsnVwZOZYJd7QxJvwLHL0']

# NFT collections to track
collections_list = ['EQA4i58iuS9DUYRtUZ97sZo5mnkbiYUBpWXQOe3dEUCcP1W8']

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