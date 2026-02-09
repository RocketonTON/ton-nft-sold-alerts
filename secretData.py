# secretData.py (versione per variabili d'ambiente)
import os

# Leggi dalle variabili d'ambiente, con fallback per testing locale
tonapi_token = os.environ.get("TONAPI_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
