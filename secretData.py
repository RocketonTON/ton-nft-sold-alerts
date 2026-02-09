# secretData.py (versione compatibile con Render)
import os

# Leggi tutto dalle variabili d'ambiente
bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
cmc_token = os.environ.get("CMC_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
