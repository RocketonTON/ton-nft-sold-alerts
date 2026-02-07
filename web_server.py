# web_server.py - REQUIRED FOR RENDER
import os
import asyncio
import logging
from threading import Thread
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
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    log.info(f"✅ Health server on port {PORT}")
    server.serve_forever()

async def main():
    # Start HTTP server in background (Render requirement)
    Thread(target=run_server, daemon=True).start()
    
    # Import and run the NFT bot
    from main import main as bot_main
    await bot_main()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot stopped")
    except Exception as e:
        log.error(f"Bot crashed: {e}")
        raise
