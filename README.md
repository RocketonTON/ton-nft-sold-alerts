# 🤖 TON NFT Sales Bot

Real-time monitoring bot for NFT sales on the TON blockchain. Sends instant Telegram notifications when NFTs from specified collections are sold.

## ✨ Features

- 🔔 **Real-time Notifications** - Instant Telegram alerts for NFT sales
- 💰 **Price Tracking** - Shows sale price in TON and USD
- 📊 **Floor Price Comparison** - Compares sale price with collection floor
- 🏪 **Multi-Marketplace Support** - Getgems, Tonex, Disintar, Diamonds
- 🎯 **Smart Tagging** - Auto-tags whale purchases and bargain deals
- ⚡ **Async Architecture** - Non-blocking HTTP calls for maximum uptime
- 🛡️ **Auto-Recovery** - Built-in timeout handling and error recovery

## 📋 Prerequisites

- Python 3.10+
- Telegram Bot Token ([get one from @BotFather](https://t.me/botfather))
- TonAPI Token ([free from tonapi.io](https://tonapi.io))
- CoinMarketCap API Key (optional, for USD pricing)

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone <your-repo>
cd ton-nft-bot
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file or set these in your hosting platform:

```bash
BOT_TOKEN=your_telegram_bot_token
NOTIFY_CHAT=your_telegram_chat_id
TONAPI_TOKEN=your_tonapi_token
CMC_TOKEN=your_coinmarketcap_token  # Optional
```

### 3. Configure Collections

Edit `config.py`:

```python
# Royalty addresses to monitor
royalty_addresses = ['EQBo86B200UaGP1B4FxxtMAgVF1GsnVwZOZYJd7QxJvwLHL0']

# NFT collections to track
collections_list = ['EQA4i58iuS9DUYRtUZ97sZo5mnkbiYUBpWXQOe3dEUCcP1W8']
```

### 4. Run

```bash
python main.py
```

## 🌐 Deploy to Render

### Environment Variables

Set these in Render Dashboard → Environment:

| Variable | Description | Required |
|----------|-------------|----------|
| `BOT_TOKEN` | Telegram bot token from @BotFather | ✅ Yes |
| `NOTIFY_CHAT` | Your Telegram chat ID | ✅ Yes |
| `TONAPI_TOKEN` | API token from tonapi.io | ✅ Yes |
| `CMC_TOKEN` | CoinMarketCap API key | ❌ Optional |

### Build & Start Commands

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python main.py`

### Health Check

The bot exposes a health endpoint on port `$PORT` (default 8000):

```
GET / → "OK - TON NFT Bot Alive"
```

## 📁 Project Structure

```
ton-nft-bot/
├── main.py              # Main bot logic
├── config.py            # Configuration (addresses, markets)
├── secretData.py        # Environment variables loader
├── functions.py         # Stack parsing & price conversion
├── nftData.py           # NFT data fetching
├── tgMessage.py         # Telegram message formatting
├── web_server.py        # Health check HTTP server
├── requirements.txt     # Python dependencies
├── lastUtime.txt        # Last processed transaction timestamp
└── README.md            # This file
```

## 🔧 Configuration

### Monitored Collections

Edit `collections_list` in `config.py`:

```python
collections_list = [
    'EQA4i58iuS9DUYRtUZ97sZo5mnkbiYUBpWXQOe3dEUCcP1W8',  # Your collection
    'EQXXX...',  # Add more
]
```

### Royalty Addresses

Edit `royalty_addresses` in `config.py`:

```python
royalty_addresses = [
    'EQBo86B200UaGP1B4FxxtMAgVF1GsnVwZOZYJd7QxJvwLHL0',  # Your royalty address
    'EQYYY...',  # Add more
]
```

### Marketplace Support

Current supported marketplaces:

- ✅ Getgems
- ✅ Tonex
- ✅ Disintar
- ✅ Diamonds

Add more in `config.py` → `markets` dictionary.

## 📊 Notification Format

Example Telegram message:

```
🔥 Cool NFT #1234

Sold for 25.5 TON ($150.50) on Getgems

Current floor: 20.0 TON ($118.00)

EQ...abc → EQ...xyz

#Market #WhaleHere
```

### Auto-Tags

- 🍣 `#SushiLover` - Price ≤ 1.2x floor (bargain!)
- 🔥 `#WhaleHere` - Price ≥ 2x floor (whale purchase!)
- `#Market` - Regular fixed-price sale
- `#Auction` - Auction sale
- `#Offer` - Offer accepted

## 🐛 Troubleshooting

### Bot Not Starting

Check environment variables:
```bash
echo $BOT_TOKEN
echo $NOTIFY_CHAT
echo $TONAPI_TOKEN
```

### No Notifications

1. Verify `collections_list` contains your collection address
2. Check `royalty_addresses` are correct
3. Look for errors in logs

### Timeout Errors

The bot has built-in timeout handling:
- Transaction fetch: 20s
- NFT data fetch: 15s
- Collection floor: 15s
- Telegram send: 10s

If timeouts persist, check your network/API rate limits.

## 📝 Logs

The bot provides detailed logging:

```
[CYCLE #1] 14:23:45
[royalty_trs] Fetching transactions for vwLHL0...
[royalty_trs] Found 15 transactions
[royalty_trs] ✅ Sale processed successfully
[CYCLE #1] ✅ Updated lastUtime: 1738234567
[CYCLE #1] Sleeping 15s...
[HEARTBEAT] 5s
[HEARTBEAT] 10s
[HEARTBEAT] 15s
```

## 🔐 Security

- ✅ All sensitive data in environment variables
- ✅ No hardcoded tokens
- ✅ `.gitignore` included for secrets
- ✅ HTTPS for all API calls

## 🛠️ Tech Stack

- **Language:** Python 3.10+
- **Async:** asyncio with non-blocking I/O
- **Blockchain:** TonAPI REST API
- **Bot Framework:** telepot
- **HTTP:** requests library
- **Hosting:** Render-ready with health checks

## 📈 Performance

- **Cycle Time:** 15 seconds
- **Concurrent Requests:** Yes (async)
- **Timeout Protection:** All HTTP calls
- **Auto-Recovery:** Yes
- **Memory:** ~50MB
- **CPU:** Minimal

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

MIT License - feel free to use and modify

## 🆘 Support

- **Issues:** Open a GitHub issue
- **Questions:** Check existing issues first
- **Updates:** Watch the repository

## 🎯 Roadmap

- [ ] Multi-chain support
- [ ] Discord notifications
- [ ] Price alerts
- [ ] Analytics dashboard
- [ ] Email notifications

---

Made with ❤️ for the TON NFT community
