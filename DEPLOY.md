# 🚀 Deployment Guide - Coolify

Your trading bot is fully containerized and optimized for Coolify deployment!

## 📋 Prerequisites

- **Coolify** installed and running on your server
- **Git repository** (GitHub, GitLab, or self-hosted)
- **MongoDB** database (MongoDB Atlas recommended for cloud)
- **Binance API keys** (Testnet for paper trading)

---

## 🚀 Quick Deploy to Coolify

### Step 1: Prepare Your Repository

```bash
# Ensure all files are committed
git add .
git commit -m "Production-ready deployment"
git push origin main
```

### Step 2: Create Application in Coolify

1. Go to your **Coolify Dashboard**
2. Click **"+ Add"** → **"Application"**
3. Select **"Docker Based"** → **"Dockerfile"**
4. Choose your **Git repository** and branch (`main`)
5. Coolify will auto-detect the **Dockerfile**

### Step 3: Configure Build Settings

In the **Build** tab:
| Setting | Value |
|---------|-------|
| Build Pack | Dockerfile |
| Dockerfile Location | `./Dockerfile` |
| Docker Build Target | `production` |

### Step 4: Configure Environment Variables

Go to **"Environment Variables"** tab and add these **required** variables:

#### 🔴 Required Variables

| Variable | Example Value | Description |
|----------|---------------|-------------|
| `MODE` | `PAPER` | Trading mode: `PAPER` or `LIVE` |
| `BINANCE_API_KEY` | `abc123...` | Binance API Key |
| `BINANCE_API_SECRET` | `xyz789...` | Binance API Secret |
| `CAPITAL` | `240.0` | Total capital in USD |
| `RISK_PER_TRADE` | `20.0` | Risk per trade in USD |
| `MAX_DAILY_LOSS` | `5.0` | Max daily loss percentage |
| `MONGO_URI` | `mongodb+srv://...` | MongoDB connection string |

#### 🟡 Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_DB_NAME` | `binbot_db` | MongoDB database name |
| `SYMBOLS` | `BTCUSDT,ETHUSDT,...` | Trading pairs (comma-separated) |
| `INTERVALS` | `15m` | Timeframe intervals |
| `SL_MULTIPLIER` | `2.5` | Stop-loss ATR multiplier |
| `TP_MULTIPLIER` | `3.0` | Take-profit ATR multiplier |
| `CHECK_INTERVAL_SEC` | `60` | Market check interval |
| `MAX_OPEN_POSITIONS` | `3` | Maximum simultaneous positions |
| `TRADING_FEE` | `0.001` | Trading fee (0.1%) |
| `TZ` | `UTC` | Timezone |

> ⚠️ **IMPORTANT**: For Paper Trading, use Binance **Testnet** keys!
> Get them at: https://testnet.binance.vision/

### Step 5: Configure Persistent Storage

In **"Storages"** tab:

1. Click **"+ Add"**
2. Configure:
   - **Source Path**: Leave empty (named volume)
   - **Destination Path**: `/app/data`
   - **Name**: `trading_bot_data`

This preserves your trade history and bot state across deployments.

### Step 6: Configure Health Checks

In **"Health Checks"** tab (if available):

| Setting | Value |
|---------|-------|
| Health Check Command | `pgrep -f "python.*live_bot.py"` |
| Interval | 30 seconds |
| Timeout | 10 seconds |
| Start Period | 60 seconds |
| Retries | 3 |

### Step 7: Deploy! 🎉

1. Click **"Deploy"**
2. Monitor the build logs
3. Once deployed, check application logs

You should see:
```
✅ MongoDB Connected: binbot_db
Dynamic Institutional Bot Initialized.
Capital: $240.0 | Risk/Trade: $20.0
Scanning Market...
```

---

## 📊 Monitoring

### View Logs in Coolify
- Go to your application → **"Logs"** tab
- Real-time trade signals and executions are displayed

### Check Trade History
- Connect to your MongoDB (e.g., MongoDB Compass)
- Database: `binbot_db`
- Collection: `trade_history`

### Health Status
- Coolify shows green status when bot is healthy
- Red status indicates the bot process has crashed

---

## 🐳 Local Development with Docker

```bash
# Build and run (requires .env file)
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f trading-bot

# Stop and remove
docker-compose down

# Stop and remove volumes (clears data!)
docker-compose down -v
```

---

## 🔄 Switching to Live Trading

> ⚠️ **WARNING**: Real money is at risk!

1. **In Coolify Environment Variables**, update:
   - `MODE` → `LIVE`
   - Replace Testnet API keys with **REAL** Binance API keys

2. **Start conservative**:
   - `CAPITAL` → Start with minimum (e.g., `100.0`)
   - `RISK_PER_TRADE` → Lower value (e.g., `10.0`)
   - `MAX_OPEN_POSITIONS` → `1` initially

3. **Enable IP restrictions** on Binance for your server's IP

4. **Monitor closely** for the first few days

---

## 🔧 Updating the Bot

1. Push changes to your Git repository:
   ```bash
   git add .
   git commit -m "Update bot logic"
   git push origin main
   ```

2. In Coolify:
   - Go to your application
   - Click **"Redeploy"**
   - Or enable **Auto Deploy** for automatic updates on push

---

## 🛠️ Troubleshooting

### Bot not starting?
- ✅ Check logs for Python errors
- ✅ Verify all **required** environment variables are set
- ✅ Ensure MongoDB URI is correct and accessible
- ✅ Check if Binance API keys are valid

### No trades being executed?
- ✅ Check if market conditions match strategy criteria
- ✅ Verify API keys have trading permissions enabled
- ✅ For Testnet: Ensure you're using Testnet keys (not mainnet)
- ✅ Check `MAX_OPEN_POSITIONS` isn't already reached

### Connection errors?
- ✅ Verify server has outbound internet access
- ✅ Check if Binance is accessible from your server's region
- ✅ Verify MongoDB allows connections from your server's IP

### Container keeps restarting?
- ✅ Check for Python runtime errors in logs
- ✅ Verify memory limits aren't too low (min 256MB recommended)
- ✅ Check if MongoDB connection is timing out

### Health check failing?
- ✅ Ensure the `live_bot.py` process is actually running
- ✅ Increase `start_period` if bot takes longer to initialize
- ✅ Check if there are fatal errors during startup

---

## 📁 File Structure

```
binance/
├── Dockerfile           # Multi-stage production build
├── docker-compose.yml   # Local development & testing
├── coolify.json         # Coolify configuration
├── .dockerignore        # Files excluded from Docker build
├── .env.example         # Environment variable template
├── requirements.txt     # Python dependencies
├── live_bot.py          # Main trading bot
├── strategy.py          # Trading strategy logic
├── analytics.py         # Performance analytics
├── dashboard.py         # CLI dashboard
└── trade_logger.py      # Trade history logging
```

---

## 🔐 Security Best Practices

1. **Never commit `.env`** - It's in `.gitignore`
2. **Use Coolify's encrypted environment variables**
3. **Restrict Binance API key permissions** - Only enable trading
4. **Set IP restrictions** on Binance API for your server
5. **Use MongoDB Atlas with IP whitelist**
6. **Run as non-root user** (already configured in Dockerfile)

---

## 📞 Support

If you encounter issues:
1. Check the logs in Coolify
2. Review environment variables
3. Test MongoDB connection separately
4. Verify Binance API permissions
