from functions import convert_ton_to_usd
from config import markets, markets_links, getgems_user_url

# Application sarà impostata da main.py
application = None

async def tg_message(action, market_address, nft_address, prew_owner, real_owner, price_ton, nft_name, nft_preview, floor_ton, floor_link):
    if application is None:
        print("[TG_MESSAGE] ❌ Application non inizializzata")
        return

    emoji = ''
    tag = ''
    market_name = markets.get(market_address, 'Unknown')
    market_link = markets_links.get(market_name, '')

    price_usd = convert_ton_to_usd(price_ton)
    price_usd_text = f' (${price_usd})' if price_usd is not None else ''

    if floor_ton is not None:
        floor_usd = convert_ton_to_usd(floor_ton)
        floor_usd_text = f' (${floor_usd})' if floor_usd is not None else ''
        floor_text = f'<b>Current <a href="{market_link}{floor_link}">floor</a>:</b> {floor_ton} TON{floor_usd_text}'
        
        if price_ton <= float(floor_ton) * 1.2:
            emoji = '🍣'
            tag = '#SushiLover'
        elif price_ton >= float(floor_ton) * 2:
            emoji = '🔥'
            tag = '#WhaleHere'
    else:
        floor_text = ''

    if action == 'SaleFixPrice':
        action_message = f'{emoji} Venduto per {price_ton} TON{price_usd_text} su {market_name}\n\n'
        action_tag = '#Market'
    elif action == 'SaleAuction':
        action_message = f'{emoji} Venduto all\'asta per {price_ton} TON{price_usd_text} su {market_name}\n\n'
        action_tag = '#Auction'
    elif action == 'SaleOffer':
        action_message = f'{emoji} Venduto tramite offerta per {price_ton} TON{price_usd_text} su {market_name}\n\n'
        action_tag = '#Offer'
    else:
        action_message = ''
        action_tag = ''

    if real_owner is not None:
        seller_text = f'<b><a href="{getgems_user_url}{prew_owner}">EQ...{prew_owner[-4:]}</a> ➡️ <a href="{getgems_user_url}{real_owner}">EQ...{real_owner[-4:]}</a></b>\n\n'
    else:
        seller_text = ''

    message_text = f'<b><a href="{market_link}{nft_address}">{nft_name}</a></b>\n\n{action_message}{floor_text}\n\n{seller_text}<b><i>{action_tag} {tag}</i></b>'

    try:
        await application.bot.send_photo(
            chat_id=TELEGRAM_CHAT_ID,
            photo=nft_preview,
            caption=message_text,
            parse_mode='HTML'
        )
    except Exception as e:
        print(f'[TG_MESSAGE] ❌ Invio foto fallito per {nft_address}: {e}')
        try:
            await application.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message_text,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f'[TG_MESSAGE] ❌ Invio messaggio fallito per {nft_address}: {e}')
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

    if real_owner is not None:
        seller_text = f'<b><a href="{getgems_user_url}{prew_owner}">EQ...{prew_owner[-4:]}</a> ➡️ ' \
                      f'<a href="{getgems_user_url}{real_owner}">EQ...{real_owner[-4:]}</a></b>\n\n'
    else:
        seller_text = ''

    message_text = f'<b><a href="{market_link}{nft_address}">{nft_name}</a></b>\n\n' \
                   f'{action_message}' \
                   f'{floor_text}\n\n' \
                   f'{seller_text}' \
                   f'<b><i>{action_tag} {tag}</i></b>'

    try:
        # CAMBIA QUESTA RIGA: bot.sendPhoto(...) -> await application.bot.send_photo(...)
        await application.bot.send_photo(
            chat_id=notify_chat,
            photo=nft_preview,
            caption=message_text,
            parse_mode='HTML'
        )
    except Exception as e:
        print(f'Photo Send ({notify_chat}) - ({nft_address}) Failed: {e}')
        try:
            # CAMBIA QUESTA RIGA: bot.sendMessage(...) -> await application.bot.send_message(...)
            await application.bot.send_message(
                chat_id=notify_chat,
                text=message_text,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f'Message Send ({notify_chat}) - ({nft_address}) Failed: {e}')
