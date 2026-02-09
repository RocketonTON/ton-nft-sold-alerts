"""
Secret Data Configuration - TON Center Version
"""
import os
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Telegram Bot Configuration
bot_token = os.environ.get('BOT_TOKEN', '')
notify_chat = os.environ.get('NOTIFY_CHAT', '')

# TON Center API Configuration
toncenter_api_key = os.environ.get('TONCENTER_API_KEY', '')

# API Tokens (opzionali)
cmc_token = os.environ.get('CMC_TOKEN', '')  # CoinMarketCap API (optional)

# Validate required variables
if not bot_token:
    log.error("❌ BOT_TOKEN not set in environment variables!")
if not notify_chat:
    log.error("❌ NOTIFY_CHAT not set in environment variables!")
if not toncenter_api_key:
    log.warning("⚠️ TONCENTER_API_KEY not set. Using public endpoint with rate limits.")