# 🚀 Deployment Guide for Render

## Step-by-Step Deployment

### 1. Prepare Your Repository

Push all files to GitHub:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-github-repo-url>
git push -u origin main
```

### 2. Create Render Account

1. Go to [render.com](https://render.com)
2. Sign up with GitHub
3. Authorize Render to access your repository

### 3. Create New Web Service

1. Click "New +" → "Web Service"
2. Connect your repository
3. Configure:
   - **Name:** `ton-nft-sales-bot` (or your choice)
   - **Region:** Choose closest to you
   - **Branch:** `main`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`

### 4. Set Environment Variables

In Render Dashboard → Environment, add:

| Key | Value | Notes |
|-----|-------|-------|
| `BOT_TOKEN` | `123456:ABC...` | From @BotFather |
| `NOTIFY_CHAT` | `-1001234567890` | Your chat ID |
| `TONAPI_TOKEN` | `AFH3J5A...` | From tonapi.io |
| `CMC_TOKEN` | (optional) | From coinmarketcap.com |

#### How to Get Each Token:

**BOT_TOKEN:**
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot`
3. Follow instructions
4. Copy the token

**NOTIFY_CHAT:**
1. Add your bot to a channel/group
2. Send a message
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find `"chat":{"id":-1001234567890}`
5. Copy that ID

**TONAPI_TOKEN:**
1. Go to [tonapi.io](https://tonapi.io)
2. Sign up for free account
3. Generate API key
4. Copy the token

**CMC_TOKEN (Optional):**
1. Go to [coinmarketcap.com/api](https://coinmarketcap.com/api/)
2. Sign up for free account
3. Get API key
4. Copy the key

### 5. Deploy

1. Click "Create Web Service"
2. Wait for build to complete (~2-3 minutes)
3. Check logs for:
   ```
   [DEBUG] All imports successful!
   [MAIN] ✅ Web server started
   [SCHEDULER] Started (TonAPI Mode)
   ```

### 6. Verify It's Working

**Check Health Endpoint:**
```bash
curl https://your-app-name.onrender.com
# Should return: "OK - TON NFT Bot Alive"
```

**Check Logs:**
```
[CYCLE #1] 14:23:45
[royalty_trs] Fetching transactions for vwLHL0...
[royalty_trs] Found 15 transactions
[HEARTBEAT] 5s
[HEARTBEAT] 10s
[HEARTBEAT] 15s
```

### 7. Test Notifications

If you have recent sales in your collection, you should receive Telegram messages within 15 seconds of deployment.

## 🔧 Configuration on Render

### Auto-Deploy

Enable auto-deploy to update the bot whenever you push to GitHub:

1. Render Dashboard → Settings
2. Enable "Auto-Deploy"
3. Now `git push` triggers automatic redeployment

### Health Checks

Render automatically checks your health endpoint every 30 seconds:
- URL: `https://your-app.onrender.com/`
- Expected: HTTP 200 with "OK - TON NFT Bot Alive"

### Logs

View real-time logs:
1. Render Dashboard → Logs
2. Or use: `render logs -f`

### Restart

If the bot needs a restart:
1. Render Dashboard → Manual Deploy → "Clear build cache & deploy"

## ⚠️ Common Issues

### Issue 1: Bot Token Not Set

**Error:**
```
❌ BOT_TOKEN not set in environment variables!
```

**Fix:** Add `BOT_TOKEN` in Render → Environment

---

### Issue 2: Timeouts

**Error:**
```
[royalty_trs] ⏱️ TIMEOUT fetching transactions
```

**Fix:** This is normal occasionally. The bot auto-retries. If persistent, check TonAPI status.

---

### Issue 3: No Notifications

**Possible Causes:**
1. Collection address not in `collections_list`
2. Royalty address wrong
3. No recent sales

**Fix:** Verify addresses in `config.py`

---

### Issue 4: Build Fails

**Error:**
```
ERROR: Could not find a version that satisfies the requirement...
```

**Fix:** 
1. Check `requirements.txt` syntax
2. Ensure Python 3.10+ selected
3. Clear build cache and redeploy

## 📊 Monitoring

### Expected Log Pattern

Healthy bot shows:
```
[CYCLE #N] HH:MM:SS
[royalty_trs] Fetching transactions...
[royalty_trs] Found X transactions
[CYCLE #N] Sleeping 15s...
[HEARTBEAT] 5s
[HEARTBEAT] 10s
[HEARTBEAT] 15s
```

### Unhealthy Patterns

❌ **Stuck at heartbeat:**
```
[HEARTBEAT] 5s
[HEARTBEAT] 10s
[HEARTBEAT] 15s
(no next cycle starts)
```
→ Restart the service

❌ **Constant timeouts:**
```
⏱️ TIMEOUT fetching transactions
⏱️ TIMEOUT fetching transactions
⏱️ TIMEOUT fetching transactions
```
→ Check TonAPI status or rate limits

❌ **Import errors:**
```
[DEBUG] ❌ config import failed
```
→ Missing environment variable or syntax error in config

## 🎯 Performance Tips

### Optimize for Free Tier

Render's free tier suspends inactive services after 15 minutes of no HTTP requests. Our health check prevents this, but you can also:

1. Use [UptimeRobot](https://uptimerobot.com) to ping your service every 5 minutes
2. Set up a cron job to curl your health endpoint

### Reduce Log Verbosity

If logs are too verbose, reduce debug output:

In `main.py`, change:
```python
print(f"[DEBUG] ...", flush=True)  # Remove these
```

## 🔐 Security Best Practices

1. ✅ **Never commit `.env` file** - Use `.gitignore`
2. ✅ **Rotate tokens periodically** - Especially if leaked
3. ✅ **Use environment variables** - Don't hardcode
4. ✅ **Monitor logs** - Check for unauthorized access
5. ✅ **Limit bot permissions** - Only grant necessary permissions

## 🆘 Getting Help

If you encounter issues:

1. **Check Render logs** - Most issues show here
2. **Verify environment variables** - Typos are common
3. **Test locally first** - Run `python main.py` locally
4. **Check API status** - tonapi.io, coinmarketcap.com
5. **Open GitHub issue** - Provide logs and error messages

## 📝 Updating the Bot

To update after code changes:

```bash
git add .
git commit -m "Update: description of changes"
git push
```

If auto-deploy is enabled, Render will automatically redeploy.

---

**You're all set! 🎉**

Your bot should now be monitoring NFT sales 24/7 and sending notifications to your Telegram.
