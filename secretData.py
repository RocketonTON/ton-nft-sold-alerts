# secretData.py - VERSIONE PER RENDER
import os

# Leggi da environment variables di Render
bot_token = os.environ.get('BOT_TOKEN', '')
notify_chat = os.environ.get('NOTIFY_CHAT', '')
cmc_token = os.environ.get('CMC_TOKEN', '')  # Opzionale

# Log per debug
import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

if not bot_token:
    log.error("❌ BOT_TOKEN not set in environment variables!")
if not notify_chat:
    log.error("❌ NOTIFY_CHAT not set in environment variables!")
