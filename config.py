import os

# === PERCORSO ===
current_path = os.path.dirname(os.path.abspath(__file__))

# === TOKEN E CREDENZIALI (da variabili d'ambiente) ===
# Telegram
bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# TonAPI
tonapi_token = os.environ.get("TONAPI_TOKEN", "")

# CoinMarketCap (opzionale)
cmc_token = os.environ.get("CMC_TOKEN", "")

# === LISTE DINAMICHE (da variabili d'ambiente) ===
royalty_addresses_str = os.environ.get("ROYALTY_ADDRESSES", "")
collections_list_str = os.environ.get("MONITORED_COLLECTIONS", "")

# Converti stringhe in liste
royalty_addresses = [addr.strip() for addr in royalty_addresses_str.split(",") if addr.strip()] if royalty_addresses_str else []
collections_list = [addr.strip() for addr in collections_list_str.split(",") if addr.strip()] if collections_list_str else []

# === CONFIGURAZIONI FISSE ===
trs_limit = 50
ton_config_url = 'https://ton.org/global-config.json'
tonorg_price_url = 'https://ton.org/getpriceg/'
tonapi_url = 'https://tonapi.io/v1/'
getgems_api_url = 'https://api.getgems.io/graphql'
getgems_user_url = 'https://getgems.io/user/'
cmc_url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'

get_methods = ['get_sale_data', 'get_offer_data']

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

getgems_query = """query nftSearch($count: Int!, $cursor: String, $query: String, $sort: String) {
  alphaNftItemSearch(first: $count, after: $cursor, query: $query, sort: $sort) {
    edges {
      node {
        ...nftPreview
        __typename
      }
      cursor
      __typename
    }
    info {
      hasNextPage
      __typename
    }
    __typename
  }
}

fragment nftPreview on NftItem {
  name
  previewImage: content {
    ... on NftContentImage {
      image {
        sized(width: 500, height: 500)
        __typename
      }
      __typename
    }
    ... on NftContentLottie {
      lottie
      fallbackImage: image {
        sized(width: 500, height: 500)
        __typename
      }
      __typename
    }
    __typename
  }
  address
  collection {
    name
    address
    __typename
  }
  sale {
    ... on NftSaleFixPrice {
      fullPrice
      __typename
    }
    __typename
  }
  __typename
}"""

cmc_params = {'slug': 'toncoin', 'convert': 'USD'}
cmc_headers = {'Accepts': 'application/json', 'X-CMC_PRO_API_KEY': cmc_token}

# === DEBUG: Verifica caricamento variabili ===
print(f"[CONFIG] Royalty addresses loaded: {len(royalty_addresses)}")
print(f"[CONFIG] Collections loaded: {len(collections_list)}")
print(f"[CONFIG] Telegram bot token: {'✅ Presente' if bot_token else '❌ Assente'}")
print(f"[CONFIG] TonAPI token: {'✅ Presente' if tonapi_token else '❌ Assente'}")
