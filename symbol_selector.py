"""
Dynamic Symbol Selector
=======================
Automatically selects which symbols to trade based on historical performance.
Excludes symbols with poor win rates or negative PnL.
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from trade_logger import get_mongo_collection
from utils_bot import logger

# Default symbols to consider (full universe - top coins by market cap and volume)
ALL_SYMBOLS = [
    # Top 10 by market cap
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "TRXUSDT", "LTCUSDT", "LINKUSDT",
    "AVAXUSDT",
    
    # Layer 2 & DeFi
    "MATICUSDT",  # Polygon
    "DOTUSDT",    # Polkadot
    "ATOMUSDT",   # Cosmos
    "NEARUSDT",   # Near Protocol
    "UNIUSDT",    # Uniswap
    "APTUSDT",    # Aptos
    "ARBUSDT",    # Arbitrum
    "OPUSDT",     # Optimism
    "SUIUSDT",    # Sui
    "INJUSDT",    # Injective
    
    # Gaming & Metaverse
    "SANDUSDT",   # The Sandbox
    "MANAUSDT",   # Decentraland
    
    # High volume memes
    "SHIBUSDT",   # Shiba Inu
]

# Minimum criteria for a symbol to be tradeable
MIN_WIN_RATE = 50.0        # Minimum win rate percentage
MIN_TRADES = 3             # Minimum trades needed for evaluation
MIN_PROFIT_PER_TRADE = -0.5  # Minimum average profit % per trade (allow small losses)
LOOKBACK_DAYS = 14         # Days of history to analyze


def analyze_symbol_performance(mode: str = "PAPER", lookback_days: int = LOOKBACK_DAYS) -> Dict[str, Dict]:
    """
    Analyze performance of each symbol from trade history.
    
    Returns:
        Dict mapping symbol to performance stats
    """
    col = get_mongo_collection()
    if col is None:
        logger.warning("MongoDB not available for symbol analysis")
        return {}
    
    try:
        # First try with date filter
        cutoff = datetime.now() - timedelta(days=lookback_days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        
        # Build query - also include BACKTEST mode for learning
        modes_to_check = [mode]
        if mode == "PAPER":
            modes_to_check.append("BACKTEST")  # Learn from backtest too
        
        # Try with date filter first
        trades = list(col.find({
            "mode": {"$in": modes_to_check},
            "timestamp": {"$regex": f"^{cutoff_str[:4]}"}  # Match year at least
        }).sort("timestamp", -1).limit(500))
        
        # If no trades found, try without date filter
        if not trades:
            trades = list(col.find({
                "mode": {"$in": modes_to_check}
            }).sort("timestamp", -1).limit(500))
        
        # Analyze by symbol
        symbol_stats = {}
        
        for trade in trades:
            sym = trade.get('symbol')
            if not sym:
                continue
                
            if sym not in symbol_stats:
                symbol_stats[sym] = {
                    'total_trades': 0,
                    'wins': 0,
                    'losses': 0,
                    'total_pnl': 0.0,
                    'total_pnl_pct': 0.0,
                    'entries': 0,
                    'exits': 0
                }
            
            reason = trade.get('reason', '')
            pnl_pct = trade.get('pnl_pct', 0) or 0
            pnl_amount = trade.get('pnl_amount', 0) or 0
            
            if reason == 'ENTRY':
                symbol_stats[sym]['entries'] += 1
            elif reason in ['STOP_LOSS', 'TAKE_PROFIT', 'MANUAL_EXIT', 'TREND_FLIP'] or pnl_amount != 0:
                symbol_stats[sym]['exits'] += 1
                symbol_stats[sym]['total_trades'] += 1
                symbol_stats[sym]['total_pnl'] += pnl_amount
                symbol_stats[sym]['total_pnl_pct'] += pnl_pct
                
                if pnl_pct > 0:
                    symbol_stats[sym]['wins'] += 1
                elif pnl_pct < 0:
                    symbol_stats[sym]['losses'] += 1
        
        # Calculate derived metrics
        for sym, stats in symbol_stats.items():
            total = stats['total_trades']
            if total > 0:
                stats['win_rate'] = (stats['wins'] / total) * 100
                stats['avg_pnl_pct'] = (stats['total_pnl_pct'] / total) * 100
            else:
                stats['win_rate'] = 0
                stats['avg_pnl_pct'] = 0
        
        return symbol_stats
        
    except Exception as e:
        logger.error(f"Error analyzing symbol performance: {e}")
        return {}


def get_tradeable_symbols(
    mode: str = "PAPER",
    min_win_rate: float = MIN_WIN_RATE,
    min_trades: int = MIN_TRADES,
    min_profit: float = MIN_PROFIT_PER_TRADE,
    lookback_days: int = LOOKBACK_DAYS,
    all_symbols: List[str] = None
) -> Tuple[List[str], Dict[str, str]]:
    """
    Get list of symbols that meet performance criteria.
    
    Returns:
        Tuple of (tradeable_symbols, exclusion_reasons)
    """
    if all_symbols is None:
        all_symbols = ALL_SYMBOLS
    
    stats = analyze_symbol_performance(mode, lookback_days)
    
    tradeable = []
    excluded = {}
    
    for sym in all_symbols:
        if sym not in stats:
            # No history - include by default (new symbol)
            tradeable.append(sym)
            continue
        
        sym_stats = stats[sym]
        total_trades = sym_stats['total_trades']
        win_rate = sym_stats['win_rate']
        avg_pnl = sym_stats['avg_pnl_pct']
        
        # Check if enough trades to evaluate
        if total_trades < min_trades:
            tradeable.append(sym)  # Include - not enough data yet
            continue
        
        # Check win rate
        if win_rate < min_win_rate:
            excluded[sym] = f"Win rate {win_rate:.1f}% < {min_win_rate}%"
            continue
        
        # Check profitability
        if avg_pnl < min_profit:
            excluded[sym] = f"Avg PnL {avg_pnl:.2f}% < {min_profit}%"
            continue
        
        # Symbol passes all checks
        tradeable.append(sym)
    
    return tradeable, excluded


def log_symbol_selection(mode: str = "PAPER"):
    """
    Log symbol selection results for debugging.
    """
    stats = analyze_symbol_performance(mode)
    tradeable, excluded = get_tradeable_symbols(mode)
    
    logger.info("=" * 50)
    logger.info("DYNAMIC SYMBOL SELECTION")
    logger.info("=" * 50)
    
    # Print stats for all symbols
    logger.info(f"{'Symbol':<10} | {'Trades':<6} | {'Win%':<6} | {'Avg PnL':<8} | {'Status'}")
    logger.info("-" * 50)
    
    for sym in ALL_SYMBOLS:
        if sym in stats:
            s = stats[sym]
            status = "✅ TRADE" if sym in tradeable else f"❌ {excluded.get(sym, 'EXCLUDED')}"
            logger.info(f"{sym:<10} | {s['total_trades']:<6} | {s['win_rate']:<6.1f} | {s['avg_pnl_pct']:<8.2f} | {status}")
        else:
            logger.info(f"{sym:<10} | {'N/A':<6} | {'N/A':<6} | {'N/A':<8} | ✅ NEW")
    
    logger.info("-" * 50)
    logger.info(f"Trading: {len(tradeable)} symbols: {', '.join(tradeable)}")
    logger.info(f"Excluded: {len(excluded)} symbols: {', '.join(excluded.keys())}")
    logger.info("=" * 50)
    
    return tradeable, excluded


def get_symbol_score(sym: str, stats: Dict) -> float:
    """
    Calculate a score for symbol ranking.
    Higher score = better performer.
    """
    if sym not in stats:
        return 0  # Unknown
    
    s = stats[sym]
    total_trades = s['total_trades']
    
    if total_trades < 2:
        return 0  # Not enough data
    
    # Score = Win Rate * (1 + Avg PnL) * log(trades + 1)
    # This balances win rate, profitability, and sample size
    import math
    win_rate = s['win_rate'] / 100  # 0-1
    avg_pnl = s['avg_pnl_pct'] / 100  # As decimal
    
    # Clamp avg_pnl to avoid negative scores
    pnl_factor = max(0.1, 1 + avg_pnl)
    
    # More trades = more confidence
    trade_factor = math.log(total_trades + 1)
    
    score = win_rate * pnl_factor * trade_factor
    return score


def get_ranked_symbols(mode: str = "PAPER", top_n: int = 6) -> List[str]:
    """
    Get the top N performing symbols.
    """
    stats = analyze_symbol_performance(mode)
    
    # Calculate scores
    scores = {}
    for sym in ALL_SYMBOLS:
        scores[sym] = get_symbol_score(sym, stats)
    
    # Sort by score descending
    ranked = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    
    # Return top N
    return ranked[:top_n]


# For testing
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("\n=== Testing Dynamic Symbol Selector ===\n")
    log_symbol_selection("PAPER")
    
    print("\n=== Top Ranked Symbols ===")
    ranked = get_ranked_symbols("PAPER", top_n=6)
    print(f"Top 6: {ranked}")
