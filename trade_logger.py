import os
import csv
import pandas as pd
from datetime import datetime
import threading
from pymongo import MongoClient, DESCENDING

# File fallback
LOG_FILE = "trade_history.csv"

# MongoDB Config
MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "binbot_db")
MONGO_COLLECTION = "trade_history"

_mongo_client = None
_db = None
_collection = None

def get_mongo_collection():
    global _mongo_client, _db, _collection, MONGO_URI
    
    if not MONGO_URI:
        MONGO_URI = os.getenv("MONGO_URI", "")
    
    if not MONGO_URI: return None

    if _collection is None:
        try:
            _mongo_client = MongoClient(MONGO_URI)
            _db = _mongo_client[MONGO_DB_NAME]
            _collection = _db[MONGO_COLLECTION]
        except Exception as e:
            print(f"MongoDB Connection Error: {e}")
            return None
    return _collection

def init_mongo_db():
    col = get_mongo_collection()
    # FIX: Explicit None check
    if col is not None:
        try:
            _mongo_client.admin.command('ping')
            print(f"✅ MongoDB Connected: {MONGO_DB_NAME}")
            col.create_index([("timestamp", DESCENDING)])
            return True
        except Exception as e:
            print(f"❌ MongoDB Init Failed: {e}")
            return False
    return False

def log_trade(mode, symbol, action, price, quantity, reason, pnl_pct, pnl_amount, balance, strategy_info):
    timestamp = datetime.now().isoformat()
    
    # 1. MongoDB Log
    mongo_col = get_mongo_collection()
    # FIX: Explicit None check
    if mongo_col is not None:
        try:
            doc = {
                "timestamp": timestamp,
                "mode": mode,
                "symbol": symbol,
                "action": action,
                "price": float(price),
                "quantity": float(quantity),
                "reason": reason,
                "pnl_pct": float(pnl_pct),
                "pnl_amount": float(pnl_amount),
                "balance": float(balance),
                "strategy_info": strategy_info
            }
            mongo_col.insert_one(doc)
            # print("Logged to Mongo")
        except Exception as e:
            print(f"Failed to log to MongoDB: {e}")

    # 2. CSV Log (File-based backup)
    file_exists = os.path.isfile(LOG_FILE)
    
    try:
        with open(LOG_FILE, mode='a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "timestamp", "mode", "symbol", "action", "price", "quantity", 
                    "reason", "pnl_pct", "pnl_amount", "balance", "strategy_info"
                ])
            
            writer.writerow([
                timestamp, mode, symbol, action, f"{price:.4f}", f"{quantity:.6f}", 
                reason, f"{pnl_pct:.4f}", f"{pnl_amount:.4f}", f"{balance:.2f}", strategy_info
            ])
    except Exception as e:
        print(f"Error writing to CSV log: {e}") 

def get_trade_history_df():
    mongo_col = get_mongo_collection()
    
    # FIX: Explicit None check
    if mongo_col is not None:
        try:
            trades = list(mongo_col.find({}, {'_id': 0})) 
            if trades:
                df = pd.DataFrame(trades)
                numeric_cols = ['price', 'quantity', 'pnl_pct', 'pnl_amount', 'balance']
                for col in numeric_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    
                return df
        except Exception as e:
            print(f"Error reading from MongoDB: {e}. Falling back to CSV.")
            
    if os.path.exists(LOG_FILE):
        try:
            return pd.read_csv(LOG_FILE)
        except:
            return pd.DataFrame()
            
    return pd.DataFrame()
