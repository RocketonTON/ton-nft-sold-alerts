# render_runner.py - REQUIRED FOR RENDER
import os
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", 8000))
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - TON NFT Bot Alive")
    
    def log_message(self, *args):
        pass

def run_server():
    """Funzione che avvia il server HTTP (usata dal thread)"""
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    log.info(f"✅ Health server running on port {PORT}")
    server.serve_forever()

def run_in_background():
    """Funzione che main.py importa da 'web_server'"""
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    log.info("✅ HTTP server started in background")

if __name__ == "__main__":
    # 1. Avvia il server HTTP in background
    run_in_background()
    
    # 2. Importa e avvia il bot TON NFT originale
    # Il tuo main.py originale ha: async def scheduler()
    from main import scheduler
    
    try:
        log.info("🚀 Starting TON NFT Bot...")
        asyncio.run(scheduler())
    except KeyboardInterrupt:
        log.info("Bot stopped by user")
    except Exception as e:
        log.error(f"❌ Bot crashed: {e}")
        raise
