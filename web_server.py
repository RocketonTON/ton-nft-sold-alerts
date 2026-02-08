# web_server.py - REQUIRED FOR RENDER
import os
import asyncio
import logging
import threading
import time
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", 8000))
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
log = logging.getLogger(__name__)

# Global variables for uptime tracking
start_time = time.time()
bot_status = "Starting..."
last_ping_time = time.time()
ping_count = 0

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global ping_count, last_ping_time
        
        if self.path == '/':
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            
            # Calculate uptime
            uptime_seconds = int(time.time() - start_time)
            uptime_str = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"
            
            # Time since last ping
            time_since_last_ping = int(time.time() - last_ping_time)
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>TON NFT Bot</title>
                <meta http-equiv="refresh" content="30">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                    .status {{ color: green; font-weight: bold; }}
                    .info {{ background: #f5f5f5; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                    .container {{ max-width: 800px; margin: 0 auto; }}
                    .ping-status {{ 
                        padding: 10px; 
                        border-radius: 5px;
                        background: {'#d4edda' if time_since_last_ping < 400 else '#f8d7da'};
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>✅ TON NFT Sales Bot</h1>
                    
                    <div class="info">
                        <h2>Bot Status</h2>
                        <p><strong>Status:</strong> <span class="status">{bot_status}</span></p>
                        <p><strong>Port:</strong> {PORT}</p>
                        <p><strong>Current Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p><strong>Uptime:</strong> {uptime_str}</p>
                        <p><strong>Environment:</strong> {os.environ.get('RENDER', 'Local Development')}</p>
                    </div>
                    
                    <div class="info">
                        <h2>Self-Ping System</h2>
                        <div class="ping-status">
                            <p><strong>Self-ping:</strong> ACTIVE (every 5 minutes)</p>
                            <p><strong>Total pings:</strong> {ping_count}</p>
                            <p><strong>Last ping:</strong> {time_since_last_ping} seconds ago</p>
                            <p><strong>Next ping in:</strong> {max(0, 300 - time_since_last_ping)} seconds</p>
                        </div>
                        <p><em>Prevents Render.com from sleeping the app</em></p>
                    </div>
                    
                    <div class="info">
                        <h2>Endpoints</h2>
                        <ul>
                            <li><a href="/health">/health</a> - Health check for Render</li>
                            <li><a href="/ping">/ping</a> - Simple ping endpoint</li>
                            <li><a href="/status">/status</a> - Detailed status (coming soon)</li>
                        </ul>
                    </div>
                    
                    <p><small>Page auto-refreshes every 30 seconds</small></p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
            
        elif self.path in ['/health', '/ping']:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK - TON NFT Bot Alive")
        
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
    
    def log_message(self, format, *args):
        # Log only errors
        if "404" in args or "500" in args:
            log.warning(f"HTTP {args}")

def run_server():
    """Function that starts the HTTP server (used by thread)"""
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    log.info(f"✅ Health server running on port {PORT}")
    server.serve_forever()

def start_self_pinger():
    """Auto-ping to keep the app active on Render"""
    def pinger():
        global ping_count, last_ping_time, bot_status
        
        # Wait 30 seconds before first ping
        log.info("[SELF-PING] Waiting 30 seconds before first ping...")
        time.sleep(30)
        
        bot_status = "Running"
        
        while True:
            try:
                # Ping every 5 minutes (less than Render's 15-minute inactivity limit)
                log.info(f"[SELF-PING] Next ping in 5 minutes...")
                time.sleep(300)  # 5 minutes
                
                ping_count += 1
                last_ping_time = time.time()
                
                # Determine URL based on environment
                if os.environ.get('RENDER'):
                    # On Render, try to use external URL if available
                    render_service_url = os.environ.get('RENDER_EXTERNAL_URL', '')
                    if render_service_url:
                        ping_url = f"{render_service_url}/ping"
                        log.info(f"[SELF-PING] Pinging Render external URL: {ping_url}")
                    else:
                        # Fallback: local ping
                        ping_url = f"http://localhost:{PORT}/ping"
                        log.info(f"[SELF-PING] Pinging localhost on port {PORT}")
                else:
                    # Local development
                    ping_url = f"http://localhost:{PORT}/ping"
                    log.info(f"[SELF-PING] Pinging localhost (development)")
                
                # Shorter timeout to avoid blocking
                response = requests.get(ping_url, timeout=15)
                
                if response.status_code == 200:
                    log.info(f"[SELF-PING] ✅ Ping #{ping_count} successful")
                else:
                    log.warning(f"[SELF-PING] ⚠️ Ping #{ping_count} returned {response.status_code}")
                    
            except requests.exceptions.Timeout:
                log.error(f"[SELF-PING] ❌ Ping #{ping_count} timeout after 15s")
            except requests.exceptions.RequestException as e:
                log.error(f"[SELF-PING] ❌ Ping #{ping_count} failed: {e}")
            except Exception as e:
                log.error(f"[SELF-PING] ❌ Ping #{ping_count} unexpected error: {e}")
                
            # Continue even if ping fails
    
    # Start pinger in background
    thread = threading.Thread(target=pinger, daemon=True)
    thread.start()
    log.info("✅ Self-pinger started (will ping every 5 minutes)")

def run_in_background():
    """Function that main.py imports from 'web_server'"""
    global bot_status
    
    # 1. Start self-pinger
    start_self_pinger()
    
    # 2. Start HTTP server
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    
    log.info("✅ HTTP server started in background")
    bot_status = "Web server started"

# ===== FUNCTION FOR MAIN BOT =====
def run_bot():
    """Function to start the NFT bot (used by main.py)"""
    try:
        log.info("🤖 Importing and starting TON NFT Bot...")
        
        # Import main bot
        from main import scheduler
        
        # Update global status
        global bot_status
        bot_status = "Bot scheduler starting"
        
        # Start the bot
        asyncio.run(scheduler())
        
    except KeyboardInterrupt:
        bot_status = "Stopped by user"
        log.info("🛑 Bot stopped by user")
    except Exception as e:
        bot_status = f"Error: {str(e)[:50]}..."
        log.error(f"💥 Bot crashed: {e}")
        raise

if __name__ == "__main__":
    log.info("=" * 60)
    log.info("🚀 Starting TON NFT Bot for Render.com")
    log.info(f"📡 Port: {PORT}")
    log.info(f"🌍 Environment: {os.environ.get('RENDER', 'Local')}")
    log.info(f"📊 Self-ping: ACTIVE (every 5 minutes)")
    log.info("=" * 60)
    
    # 1. Start HTTP server with self-ping
    run_in_background()
    
    # 2. Start main bot
    run_bot()