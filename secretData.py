"""
Secret Data Configuration
All sensitive tokens and credentials are loaded from environment variables
"""
import os
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Telegram Bot Configuration
bot_token = os.environ.get('BOT_TOKEN', '')
notify_chat = os.environ.get('NOTIFY_CHAT', '')

# API Tokens
cmc_token = os.environ.get('CMC_TOKEN', '')  # CoinMarketCap API (optional)
tonapi_token = os.environ.get('TONAPI_TOKEN', '')  # TonAPI token

# Validate required variables
if not bot_token:
    log.error("❌ BOT_TOKEN not set in environment variables!")
if not notify_chat:
    log.error("❌ NOTIFY_CHAT not set in environment variables!")
if not tonapi_token:
    log.error("❌ TONAPI_TOKEN not set in environment variables!")
