import os
import sys
from dotenv import load_dotenv

load_dotenv()

MODE = os.getenv("MODE", "BACKTEST")  # BACKTEST | PAPER | LIVE

# Parse Lists
SYMBOLS = os.getenv("SYMBOLS", "BTCUSDT").split(",")
INTERVALS = os.getenv("INTERVALS", "1h").split(",")
SYMBOLS = [s.strip() for s in SYMBOLS if s.strip()]
INTERVALS = [i.strip() for i in INTERVALS if i.strip()]

# Capital & Logic
CAPITAL = float(os.getenv("CAPITAL", "240.0"))
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "20.0"))
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "5.0")) # Percentage
TRADING_FEE = float(os.getenv("TRADING_FEE", "0.001"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "3"))

QUANTITY = float(os.getenv("QUANTITY", "0.001")) # Fallback if fixed logic used

# Strategy Risk
SL_MULTIPLIER = float(os.getenv("SL_MULTIPLIER", "2.5"))
TP_MULTIPLIER = float(os.getenv("TP_MULTIPLIER", "3.0"))

API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Validate API Keys for PAPER/LIVE modes
if MODE in ["PAPER", "LIVE"]:
    if not API_KEY or not API_SECRET or API_KEY == "your_api_key_here":
        print("=" * 60)
        print("ERROR: BINANCE_API_KEY and BINANCE_API_SECRET are required!")
        print("Set them as environment variables in Coolify or .env file.")
        print("=" * 60)
        sys.exit(1)

if MODE == "PAPER":
    BASE_URL = "https://testnet.binance.vision"
    TESTNET = True
elif MODE == "LIVE":
    BASE_URL = "https://api.binance.com"
    TESTNET = False
else:
    BASE_URL = None
    TESTNET = False

CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL_SEC", "60"))
