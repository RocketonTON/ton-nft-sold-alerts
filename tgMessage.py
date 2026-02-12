# tgMessage.py - Async Telegram notifications with python-telegram-bot
import asyncio
from telegram import Bot
from telegram.constants import ParseMode
from functions import convert_ton_to_usd
from config import markets, markets_links, getgems_user_url
from secretData import bot_token, notify_chat

class TelegramNotifier:
    def __init__(self):
        self.bot = Bot(token=bot_token) if bot_token else None
    
    async def send_message(self, action, market_address, nft_address, prew_owner, 
                          real_owner, price_ton, nft_name, nft_preview, 
                          floor_ton, floor_link):
        """Send NFT sale notification to Telegram (async)"""
        
        if not self.bot:
            print("❌ Telegram bot not initialized")
            return
        
        try:
            emoji = ''
            tag = ''
            market_name = markets.get(market_address, 'Unknown')
            market_link = markets_links.get(market_name, '')
            
            # Price in USD
            price_usd = await convert_ton_to_usd(price_ton)
            price_usd_text = f' (${price_usd:.2f})' if price_usd else ''
            
            # Floor price
            floor_text = ''
            if floor_ton is not None:
                floor_usd = await convert_ton_to_usd(floor_ton)
                floor_usd_text = f' (${floor_usd:.2f})' if floor_usd else ''
                
                floor_link_part = f'<a href="{market_link}{floor_link}">floor</a>' if floor_link else 'floor'
                floor_text = f'<b>Current {floor_link_part}:</b> {floor_ton} TON{floor_usd_text}\n\n'
                
                if price_ton <= float(floor_ton) * 1.2:
                    emoji = '🍣'
                    tag = '#SushiLover'
                elif price_ton >= float(floor_ton) * 2:
                    emoji = '🔥'
                    tag = '#WhaleHere'
            
            # Action type
            if action == 'SaleFixPrice':
                action_message = f'{emoji} Sold for {price_ton} TON{price_usd_text} on {market_name}\n\n'
                action_tag = '#Market'
            elif action == 'SaleAuction':
                action_message = f'{emoji} Sold on auction for {price_ton} TON{price_usd_text} on {market_name}\n\n'
                action_tag = '#Auction'
            elif action == 'SaleOffer':
                action_message = f'{emoji} Sold through offer for {price_ton} TON{price_usd_text} on {market_name}\n\n'
                action_tag = '#Offer'
            else:
                action_message = ''
                action_tag = ''
            
            # Seller info
            seller_text = ''
            if real_owner is not None and prew_owner is not None:
                seller_text = (f'<b><a href="{getgems_user_url}{prew_owner}">EQ...{prew_owner[-4:]}</a> ➡️ '
                             f'<a href="{getgems_user_url}{real_owner}">EQ...{real_owner[-4:]}</a></b>\n\n')
            
            # Build message
            message_text = (f'<b><a href="{market_link}{nft_address}">{nft_name}</a></b>\n\n'
                          f'{action_message}'
                          f'{floor_text}'
                          f'{seller_text}'
                          f'<b><i>{action_tag} {tag}</i></b>')
            
            # ✅ INVIA CON send_telegram_message (UNICO PUNTO DI INVIO!)
            await send_telegram_message(
                text=message_text,
                photo=nft_preview,
                parse_mode='HTML',
                disable_web_page_preview=not bool(nft_preview)
            )
            
            print(f"✅ Telegram notification sent: {nft_name}")
            
        except Exception as e:
            print(f"❌ Telegram send error: {e}")
            # Fallback: try text-only
            try:
                if nft_preview:
                    simple_text = f"{nft_name} sold for {price_ton} TON"
                    await send_telegram_message(
                        text=simple_text,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
            except Exception as e2:
                print(f"❌ Fallback also failed: {e2}")

# Global instance
tg_notifier = TelegramNotifier()

# Async wrapper function
async def tg_message_async(action, market_address, nft_address, prew_owner, 
                          real_owner, price_ton, nft_name, nft_preview, 
                          floor_ton, floor_link):
    """Async wrapper for tg_message"""
    await tg_notifier.send_message(
        action, market_address, nft_address, prew_owner,
        real_owner, price_ton, nft_name, nft_preview,
        floor_ton, floor_link
    )

# Sync compatibility wrapper
def tg_message(action, market_address, nft_address, prew_owner, 
              real_owner, price_ton, nft_name, nft_preview, 
              floor_ton, floor_link):
    """Sync wrapper for backward compatibility"""
    asyncio.run(tg_message_async(
        action, market_address, nft_address, prew_owner,
        real_owner, price_ton, nft_name, nft_preview,
        floor_ton, floor_link
    ))

async def send_telegram_message(text: str, chat_id: str = None, photo=None, 
                               parse_mode: str = "HTML", disable_web_page_preview: bool = False,
                               reply_to_message_id: str = None):
    """UNICA funzione che invia messaggi a Telegram"""
    try:
        if not tg_notifier.bot:
            print("❌ Telegram bot not initialized")
            return False
        
        if not chat_id:
            chat_id = notify_chat
        
        if photo:
            await tg_notifier.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=text,
                parse_mode=parse_mode,
                reply_to_message_id=reply_to_message_id
            )
        else:
            await tg_notifier.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_to_message_id=reply_to_message_id,
                disable_web_page_preview=disable_web_page_preview
            )
        print(f"✅ Telegram message sent to {chat_id}")
        return True
    except Exception as e:
        print(f"❌ Error sending telegram message: {e}")
        return False
