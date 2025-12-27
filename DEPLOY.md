# 🚀 Deployment Guide - Coolify

Your trading bot is fully containerized and ready for Coolify deployment!

## Quick Deploy to Coolify

### Step 1: Push to Git

```bash
git add .
git commit -m "Ready for production deployment"
git push origin main
```

### Step 2: Create Application in Coolify

1. Go to your **Coolify Dashboard**
2. Click **"Add New Resource"** → **"Application"**
3. Select **"Git Repository"** as source
4. Choose your repository and branch (`main`)
5. Coolify will auto-detect the **Dockerfile**

### Step 3: Configure Environment Variables

In Coolify, go to **"Environment Variables"** tab and add:

| Variable | Value | Required |
|----------|-------|----------|
| `MODE` | `PAPER` or `LIVE` | ✅ |
| `BINANCE_API_KEY` | Your API key | ✅ |
| `BINANCE_API_SECRET` | Your API secret | ✅ |
| `CAPITAL` | `240.0` | ✅ |
| `RISK_PER_TRADE` | `20.0` | ✅ |
| `MAX_DAILY_LOSS` | `5.0` | ✅ |
| `MONGO_URI` | `mongodb+srv://...` | ✅ |
| `MONGO_DB_NAME` | `binbot_db` | Optional |
| `SYMBOLS` | `BTCUSDT,ETHUSDT,...` | Optional |
| `SL_MULTIPLIER` | `2.5` | Optional |
| `TP_MULTIPLIER` | `3.0` | Optional |

> ⚠️ **IMPORTANT**: For Paper Trading, use Binance Testnet keys!
> Get them at: https://testnet.binance.vision/

### Step 4: Configure Persistent Storage

In Coolify **"Storage"** settings:

1. Add a **Persistent Volume**
2. Mount path: `/app/data`
3. This preserves your trade history and bot state across deployments

### Step 5: Deploy!

Click **"Deploy"** and watch the logs. You should see:
```
✅ MongoDB Connected: binbot_db
Dynamic Institutional Bot Initialized.
Capital: $240.0 | Risk/Trade: $20.0
Scanning Market...
```

---

## Monitoring

### View Logs in Coolify
- Go to your application → **"Logs"** tab
- You'll see real-time trade signals and executions

### Check Trade History
- Connect to your MongoDB (e.g., MongoDB Compass)
- Database: `binbot_db`
- Collection: `trade_history`

---

## Local Development with Docker

```bash
# Build and run locally
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

---

## Switching to Live Trading

1. In Coolify Environment Variables, change:
   - `MODE` → `LIVE`
   - Replace Testnet API keys with **REAL** Binance API keys

2. **Start small!** Reduce `CAPITAL` and `RISK_PER_TRADE` initially

3. Monitor the first few trades carefully

---

## Troubleshooting

### Bot not starting?
- Check logs for errors
- Verify all required environment variables are set
- Ensure MongoDB URI is correct

### No trades being executed?
- Check if market conditions match strategy criteria (ADX > 25)
- Verify API keys have trading permissions
- For Testnet: Ensure you're using Testnet keys

### Connection errors?
- Verify your server has outbound internet access
- Check if Binance is accessible from your region
