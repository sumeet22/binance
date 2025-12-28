import time
import sys
import threading
import json
import os
import signal
import pandas as pd  
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from config import SYMBOLS, RISK_PER_TRADE, CHECK_INTERVAL_SEC, SL_MULTIPLIER, TP_MULTIPLIER, MODE, CAPITAL, MAX_DAILY_LOSS, TRADING_FEE, MAX_OPEN_POSITIONS
from utils_bot import get_binance_client, fetch_klines, logger, fetch_exchange_info, round_step_size
from strategy import populate_indicators, analyze_trend_strength, get_entry_signal
from trade_logger import log_trade, init_mongo_db, get_mongo_collection

TREND_TIMEFRAMES = ['4h', '2h', '1h'] 
ENTRY_TIMEFRAMES = ['30m', '15m']

# Use /app/data for Docker (persistent volume), fallback to current dir for local dev
DATA_DIR = "/app/data" if os.path.exists("/app/data") else "."
STATE_FILE = os.path.join(DATA_DIR, "bot_state.json")

class DynamicBot:
    def __init__(self):
        self.client = get_binance_client()
        
        # Validate client connection
        if self.client is None:
            logger.error("❌ Failed to connect to Binance. Check API keys and network.")
            raise RuntimeError("Binance client initialization failed")
        
        self.active_trades = {sym: None for sym in SYMBOLS} 
        self.stop_signal = False
        
        logger.info("Initializing Database...")
        init_mongo_db() 
        
        logger.info("Fetching Exchange Filters (LOT_SIZE)...")
        self.precision_info = fetch_exchange_info(self.client)
        
        if not self.precision_info:
            logger.warning("⚠️ Could not fetch exchange info. Using defaults.")
        
        self.load_state()
        self.sync_with_mongo()
        
        self.daily_start_balance = CAPITAL 
        self.max_daily_loss_amount = CAPITAL * (MAX_DAILY_LOSS / 100.0)
        self.current_open_positions = 0
        
        logger.info(f"Dynamic Institutional Bot Initialized.")
        logger.info(f"Capital: ${CAPITAL} | Risk/Trade: ${RISK_PER_TRADE} | Max Daily Loss: -{MAX_DAILY_LOSS}%")

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    saved_trades = json.load(f)
                    for sym, data in saved_trades.items():
                        if sym in self.active_trades and data:
                            # SANITIZE: Ensure all critical fields exist
                            if data.get('sl') is None or data.get('tp') is None:
                                logger.warning(f"[{sym}] Corrupted state detected. Recalculating SL/TP...")
                                entry = data.get('entry', 0)
                                if entry == 0: continue
                                
                                risk = entry * 0.01
                                atr = risk / SL_MULTIPLIER if SL_MULTIPLIER > 0 else 0
                                
                                if data.get('type') == 'LONG':
                                    data['sl'] = entry - (SL_MULTIPLIER * atr)
                                    data['tp'] = entry + (TP_MULTIPLIER * atr)
                                else:
                                    data['sl'] = entry + (SL_MULTIPLIER * atr)
                                    data['tp'] = entry - (TP_MULTIPLIER * atr)
                                
                                data['risk'] = risk
                            
                            self.active_trades[sym] = data
                            logger.info(f"Restored active trade for {sym} (from local state)")
            except Exception as e:
                logger.error(f"Failed to load state: {e}")

    def sync_with_mongo(self):
        """Recover any open trades from MongoDB on container restart"""
        col = get_mongo_collection()
        if col is None: 
            logger.warning("MongoDB not available for trade recovery")
            return
        
        try:
            # Find all recent ENTRY trades for current mode
            entries = list(col.find({"reason": "ENTRY", "mode": MODE}).sort("timestamp", -1).limit(50))
            recovered_count = 0
            
            for entry in entries:
                sym = entry['symbol']
                # Skip if we already have this trade (from local state or previous iteration)
                if self.active_trades.get(sym): 
                    continue
                
                # Check if this trade has been closed (by looking for exit trades)
                exit_doc = col.find_one({
                    "symbol": sym,
                    "mode": MODE,
                    "timestamp": {"$gt": entry['timestamp']},
                    "$or": [
                        {"reason": {"$in": ["STOP_LOSS", "TAKE_PROFIT", "MANUAL_EXIT", "TREND_FLIP"]}},
                        {"pnl_amount": {"$ne": 0}}
                    ]
                })
                
                # If no exit found, trade is still open - recover it
                if not exit_doc:
                    logger.info(f"[{sym}] 🔄 Recovering OPEN trade from MongoDB...")
                    
                    price = float(entry['price'])
                    qty = float(entry['quantity'])
                    risk = price * 0.01 
                    atr = risk / SL_MULTIPLIER if SL_MULTIPLIER > 0 else 0
                    
                    if entry['action'] == 'BUY':
                        pos_type = 'LONG'
                        sl = price - (SL_MULTIPLIER * atr)
                        tp = price + (TP_MULTIPLIER * atr)
                    else:
                        pos_type = 'SHORT'
                        sl = price + (SL_MULTIPLIER * atr)
                        tp = price - (TP_MULTIPLIER * atr)
                    
                    self.active_trades[sym] = {
                        'type': pos_type,
                        'entry': price,
                        'qty': qty,
                        'sl': sl,
                        'tp': tp,
                        'highest_price': price,
                        'lowest_price': price,
                        'risk': risk,
                        'trend_tf': '4h', 
                        'entry_tf': '15m',
                        'entry_time': time.time()
                    }
                    recovered_count += 1
            
            if recovered_count > 0:
                self.save_state()
                logger.info(f"✅ Recovered {recovered_count} open trade(s) from MongoDB")
            else:
                logger.info("No open trades to recover from MongoDB")
                    
        except Exception as e:
            logger.error(f"Mongo Sync Error: {e}")

    def save_state(self):
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(self.active_trades, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def log_position_update(self, symbol, update_type):
        """
        Log position updates (SL/TP changes) to MongoDB for tracking.
        Frequency: Every time SL or TP is adjusted.
        """
        col = get_mongo_collection()
        if col is None: return
        
        pos = self.active_trades.get(symbol)
        if not pos: return
        
        try:
            doc = {
                "timestamp": pd.Timestamp.now().isoformat(),
                "mode": MODE,
                "symbol": symbol,
                "action": "UPDATE",
                "update_type": update_type,
                "sl": pos.get('sl'),
                "tp": pos.get('tp'),
                "highest": pos.get('highest_price'),
                "lowest": pos.get('lowest_price')
            }
            col.insert_one(doc)
        except Exception as e:
            logger.error(f"Failed to log position update: {e}")

    def run(self):
        # Only start command listener if running in interactive terminal
        if sys.stdin.isatty():
            t = threading.Thread(target=self.command_listener)
            t.daemon = True
            t.start()
            logger.info("Scanning Market... (Type 'status' or 'exit <symbol>' to manage)")
        else:
            logger.info("Running in non-interactive mode (Docker/background). Command listener disabled.")
            logger.info("Scanning Market...")
        
        while not self.stop_signal:
            start_scan = time.time()
            for symbol in SYMBOLS:
                if self.stop_signal: break
                try:
                    self.process_symbol(symbol)
                except Exception as e:
                    import traceback
                    logger.error(f"[{symbol}] Loop Error: {e}\n{traceback.format_exc()}")
            
            elapsed = time.time() - start_scan
            sleep_time = max(1.0, CHECK_INTERVAL_SEC - elapsed)
            time.sleep(sleep_time)

    def command_listener(self):
        """Interactive command listener - only works when stdin is a TTY"""
        while not self.stop_signal:
            try:
                cmd = input()
                args = cmd.split()
                if not args: continue
                command = args[0].lower()
                
                if command == 'status':
                    self.print_status()
                elif command == 'exit':
                    if len(args) > 1:
                        sym = args[1].upper()
                        self.force_exit(sym)
                    else:
                        print("Usage: exit <SYMBOL>")
                elif command == 'quit' or command == 'stop':
                    print("Stopping Bot...")
                    self.stop_signal = True
                    sys.exit(0)
            except EOFError:
                # stdin closed (Docker environment)
                logger.debug("stdin closed, command listener exiting")
                break
            except Exception:
                pass

    def print_status(self):
        print("\n--- ACTIVE TRADES ---")
        found = False
        for sym, pos in self.active_trades.items():
            if pos:
                found = True
                try:
                    ticker = self.client.get_symbol_ticker(symbol=sym)
                    curr = float(ticker['price'])
                    entry = pos['entry']
                    pnl = (curr - entry)/entry if pos['type']=='LONG' else (entry - curr)/entry
                    sl = pos.get('sl', 'N/A')
                    tp = pos.get('tp', 'N/A')
                    print(f"[{sym}] {pos['type']} | Entry: {entry:.4f} | Curr: {curr:.4f} | PnL: {pnl*100:.2f}% | SL: {sl} | TP: {tp}")
                except Exception as e:
                    print(f"[{sym}] {pos['type']} | Error: {e}")
        if not found:
            print("No active trades.")
        print("---------------------\n")

    def force_exit(self, symbol):
        if symbol in self.active_trades and self.active_trades[symbol]:
            print(f"Force exiting {symbol}...")
            try:
                ticker = self.client.get_symbol_ticker(symbol=symbol)
                curr = float(ticker['price'])
                self.close_trade(symbol, self.active_trades[symbol]['type'], "MANUAL_EXIT", curr, self.active_trades[symbol]['qty'])
            except Exception as e:
                print(f"Error forcing exit: {e}")
        else:
            print(f"No active trade found for {symbol}")

    def process_symbol(self, symbol):
        if self.active_trades[symbol]:
            self.manage_trade(symbol)
            return

        self.current_open_positions = sum(1 for v in self.active_trades.values() if v is not None)
        if self.current_open_positions >= MAX_OPEN_POSITIONS:
            return

        best_trend_tf = None
        best_bias = "NEUTRAL"
        max_adx = 0
        
        for tf in TREND_TIMEFRAMES:
            df = fetch_klines(self.client, symbol, tf, limit=100)
            if df.empty: continue
            df = populate_indicators(df)
            bias, adx = analyze_trend_strength(df)
            
            if pd.isna(adx): adx = 0
            
            if adx > 25 and bias != "NEUTRAL":
                if adx > max_adx:
                    max_adx = adx
                    best_trend_tf = tf
                    best_bias = bias
        
        if not best_trend_tf: return

        for entry_tf in ENTRY_TIMEFRAMES:
            if entry_tf == best_trend_tf: continue 
            
            df_entry = fetch_klines(self.client, symbol, entry_tf, limit=100)
            if df_entry.empty: continue
            df_entry = populate_indicators(df_entry)
            signal, reason = get_entry_signal(df_entry, best_bias)
            
            if signal != "HOLD":
                current_price = df_entry.iloc[-1]['close']
                atr = df_entry.iloc[-1]['atr']
                
                if pd.isna(atr) or atr <= 0:
                    atr = current_price * 0.01

                rationale = f"Trend:{best_trend_tf}({best_bias}) + Entry:{entry_tf}({reason})"
                if self.active_trades[symbol] is None:
                     logger.info(f"[{symbol}] *** ENTRY TRIGGERED *** {rationale}")
                     self.execute_trade(symbol, signal, current_price, atr, rationale, best_trend_tf, entry_tf)
                     break 

    def execute_trade(self, symbol, signal, price, atr, rationale, trend_tf, entry_tf):
        side = SIDE_BUY if signal == "BUY" else SIDE_SELL
        
        raw_qty = RISK_PER_TRADE / price
        step_size = self.precision_info.get(symbol, 0.00001) 
        qty = round_step_size(raw_qty, step_size)
        
        if (qty * price) < 5.1:
             return
        
        success, fill = self.place_order(symbol, side, qty)
        
        if success:
            fill = float(fill)
            atr = float(atr)
            
            if signal == "BUY":
                sl_price = fill - (SL_MULTIPLIER * atr)
                tp_price = fill + (TP_MULTIPLIER * atr)
                pos_type = 'LONG'
                risk_amt = fill - sl_price
            else:
                sl_price = fill + (SL_MULTIPLIER * atr)
                tp_price = fill - (TP_MULTIPLIER * atr)
                pos_type = 'SHORT'
                risk_amt = sl_price - fill
            
            if sl_price < 0: sl_price = 0.0001
                
            self.active_trades[symbol] = {
                'type': pos_type,
                'entry': fill,
                'sl': sl_price,
                'tp': tp_price,
                'qty': qty,
                'highest_price': fill,
                'lowest_price': fill,
                'entry_time': time.time(),
                'trend_tf': trend_tf, 
                'entry_tf': entry_tf,
                'risk': risk_amt
            }
            self.save_state() 
            log_trade(MODE, symbol, side, fill, qty, "ENTRY", 0, 0, 0, rationale)

    def manage_trade(self, symbol):
        pos = self.active_trades[symbol]
        
        try:
             ticker = self.client.get_symbol_ticker(symbol=symbol)
             curr_price = float(ticker['price'])
        except Exception:
             return 

        # COMPREHENSIVE VALIDATION - ensure all values are valid numbers
        # If entry is None, we can't manage this trade
        if pos.get('entry') is None:
            logger.error(f"[{symbol}] Invalid state: entry is None. Clearing trade.")
            self.active_trades[symbol] = None
            self.save_state()
            return
        
        entry = float(pos['entry'])
        
        # Ensure highest/lowest exist and are valid
        if pos.get('highest_price') is None:
            pos['highest_price'] = entry
        if pos.get('lowest_price') is None:
            pos['lowest_price'] = entry
        
        # Convert to floats to be safe
        pos['highest_price'] = float(pos['highest_price'])
        pos['lowest_price'] = float(pos['lowest_price'])

        if curr_price > pos['highest_price']: pos['highest_price'] = curr_price
        if curr_price < pos['lowest_price']: pos['lowest_price'] = curr_price
        
        exit_reason = None
        
        # SAFE ACCESS - explicitly handle None by converting to 0
        sl_raw = pos.get('sl')
        tp_raw = pos.get('tp')
        sl = float(sl_raw) if sl_raw is not None else 0.0
        tp = float(tp_raw) if tp_raw is not None else 0.0

        if pos['type'] == 'LONG':
            if sl > 0 and curr_price <= sl: exit_reason = "STOP_LOSS"
            elif tp > 0 and curr_price >= tp: exit_reason = "TAKE_PROFIT"
        else:
            if sl > 0 and curr_price >= sl: exit_reason = "STOP_LOSS"
            elif tp > 0 and curr_price <= tp: exit_reason = "TAKE_PROFIT"
            
        if exit_reason:
            self.close_trade(symbol, pos['type'], exit_reason, curr_price, pos['qty'])
            return

        # Ensure risk exists (sl is already guaranteed float from above)
        if 'risk' not in pos or not pos['risk']:
             if sl > 0:
                 risk = abs(pos['entry'] - sl)
                 if risk == 0: risk = pos['entry'] * 0.01
             else:
                 risk = pos['entry'] * 0.01 
             pos['risk'] = risk

        risk_r = pos['risk'] if pos['risk'] else pos['entry'] * 0.01
        atr = risk_r / SL_MULTIPLIER if SL_MULTIPLIER > 0 else 0
        
        updated = False

        if pos['type'] == 'LONG':
            profit_dist = pos['highest_price'] - pos['entry']
            if profit_dist > (1.5 * risk_r):
                new_sl = pos['entry'] + (0.1 * risk_r)
                if sl == 0 or new_sl > sl:
                    pos['sl'] = new_sl
                    updated = True
                    logger.info(f"[{symbol}] Defensive: SL moved to Breakeven {new_sl:.4f}")

            if profit_dist > (2.5 * risk_r):
                trail_sl = pos['highest_price'] - (2.0 * atr)
                if sl == 0 or trail_sl > sl:
                     pos['sl'] = trail_sl
                     updated = True
                     logger.info(f"[{symbol}] Trailing Profit: SL moved to {trail_sl:.4f}")

        elif pos['type'] == 'SHORT':
            profit_dist = pos['entry'] - pos['lowest_price']
            if profit_dist > (1.5 * risk_r):
                new_sl = pos['entry'] - (0.1 * risk_r)
                if sl == 0 or new_sl < sl:
                    pos['sl'] = new_sl
                    updated = True
                    logger.info(f"[{symbol}] Defensive: SL moved to Breakeven {new_sl:.4f}")
            if profit_dist > (2.5 * risk_r):
                trail_sl = pos['lowest_price'] + (2.0 * atr)
                if sl == 0 or trail_sl < sl:
                    pos['sl'] = trail_sl
                    updated = True
                    logger.info(f"[{symbol}] Trailing Profit: SL moved to {trail_sl:.4f}")

        if updated:
            self.save_state()
            self.log_position_update(symbol, "TRAILING_STOP")  # LOG TO MONGO

        trend_df = fetch_klines(self.client, symbol, pos['trend_tf'], limit=50)
        if not trend_df.empty:
            trend_df = populate_indicators(trend_df)
            bias, _ = analyze_trend_strength(trend_df)
            if (pos['type']=='LONG' and bias=='BEAR') or (pos['type']=='SHORT' and bias=='BULL'):
                 logger.info(f"[{symbol}] EXIT: Trend Flipped.")
                 self.close_trade(symbol, pos['type'], "TREND_FLIP", curr_price, pos['qty'])

    def close_trade(self, symbol, pos_type, reason, price, qty):
        side = SIDE_SELL if pos_type == 'LONG' else SIDE_BUY
        logger.info(f"[{symbol}] Closing Trade: {reason}")
        
        success, fill = self.place_order(symbol, side, qty)
        if success:
            entry = self.active_trades[symbol]['entry']
            pnl_raw = (fill - entry)/entry if pos_type == 'LONG' else (entry - fill)/entry
            pnl_net = pnl_raw - (TRADING_FEE * 2) 
            amt = pnl_net * (entry * qty)
            log_trade(MODE, symbol, side, fill, qty, reason, pnl_net, amt, 0, "")
            self.active_trades[symbol] = None
            self.save_state() 

    def place_order(self, symbol, side, qty):
        try:
            step_size = self.precision_info.get(symbol, 0.00001) 
            qty = round_step_size(qty, step_size)
            
            if MODE not in ["LIVE", "PAPER"]:
                 ticker = self.client.get_symbol_ticker(symbol=symbol)
                 return True, float(ticker['price'])

            order = self.client.create_order(symbol=symbol, side=side, type=ORDER_TYPE_MARKET, quantity=qty)
            if 'fills' in order: return True, float(order['fills'][0]['price'])
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return True, float(ticker['price'])
        except Exception as e:
            logger.error(f"[{symbol}] Execution Error: {e}")
            return False, 0.0

if __name__ == "__main__":
    print("=" * 60)
    print("INSTITUTIONAL TRADING BOT - Starting...")
    print("=" * 60)
    print(f"MODE: {MODE}")
    print(f"SYMBOLS: {', '.join(SYMBOLS)}")
    print(f"CAPITAL: ${CAPITAL}")
    print(f"RISK_PER_TRADE: ${RISK_PER_TRADE}")
    print(f"SL_MULTIPLIER: {SL_MULTIPLIER}x | TP_MULTIPLIER: {TP_MULTIPLIER}x")
    print("=" * 60)
    
    bot = None
    
    def graceful_shutdown(signum, frame):
        """Handle Docker/Coolify stop signals gracefully"""
        sig_name = signal.Signals(signum).name
        print(f"\n[SIGNAL] Received {sig_name} - Shutting down gracefully...")
        if bot:
            bot.stop_signal = True
            bot.save_state()
            print("[SHUTDOWN] State saved successfully.")
        sys.exit(0)
    
    # Register signal handlers for Docker/Coolify shutdown
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)
    
    try:
        bot = DynamicBot()
        bot.run()
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
        if bot:
            bot.save_state()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
