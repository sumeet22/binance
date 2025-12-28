import os
import sys
import time
from tabulate import tabulate
from colorama import init, Fore, Style
import importlib

# Initialize Colorama
init(autoreset=True)

# Import Modules
from config import SYMBOLS, INTERVALS, SL_MULTIPLIER, TP_MULTIPLIER, MODE
import utils_bot
import backtest
import optimize
import scanner
import analytics
import live_bot
from trade_logger import LOG_FILE

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    clear_screen()
    print(Fore.CYAN + "=" * 60)
    print(Fore.CYAN + Style.BRIGHT + "          INSTITUTIONAL TRADING BOT DASHBOARD")
    print(Fore.CYAN + "=" * 60)
    print(f"Active Profile: {Fore.YELLOW}{len(SYMBOLS)} Pairs{Fore.RESET} | Intervals: {Fore.YELLOW}{','.join(INTERVALS)}{Fore.RESET}")
    print(f"Risk Settings : SL {Fore.RED}{SL_MULTIPLIER}x{Fore.RESET} | TP {Fore.GREEN}{TP_MULTIPLIER}x{Fore.RESET}")
    current_mode = os.environ.get("MODE", MODE)
    print(f"Current Mode  : {Fore.MAGENTA}{current_mode}{Fore.RESET}")
    print("-" * 60)

def main_menu():
    while True:
        print_header()
        
        # 1. Market Opportunities
        print(Fore.WHITE + "1. " + Fore.GREEN + "Scan Current Market Opportunities")
        
        # 2. Backtest (Duration)
        print(Fore.WHITE + "2. " + Fore.YELLOW + "Run Backtest (Strategy Validation)")
        
        # 3. Analytics (Renamed)
        print(Fore.WHITE + "3. " + Fore.BLUE + "View Trade History & Performance Analytics")
        
        # 4. Optimization (Renamed)
        print(Fore.WHITE + "4. " + Fore.MAGENTA + "Find Best Settings (AI Optimization)")
        
        # 5. Live Bot (Prompt)
        print(Fore.WHITE + "5. " + Fore.RED + "Start Trading Bot (Paper/Live)")
        
        # 6. Config
        print(Fore.WHITE + "6. " + Fore.WHITE + "View Configuration (.env)")
        
        # 0. Exit
        print(Fore.WHITE + "0. " + Fore.WHITE + "Exit")
        print("-" * 60)
        
        choice = input(Fore.CYAN + "Select an Option [0-6]: " + Style.RESET_ALL)
        
        if choice == '1':
            scan_market_ui()
        elif choice == '2':
            run_backtest_ui()
        elif choice == '3':
            analyze_performance_ui()
        elif choice == '4':
            run_optimization_ui()
        elif choice == '5':
            start_live_bot_ui()
        elif choice == '6':
            view_config_ui()
        elif choice == '0':
            print("Exiting...")
            sys.exit(0)
        else:
            input("Invalid selection. Press Enter to try again...")

def scan_market_ui():
    print_header()
    print(Fore.GREEN + ">>> MARKET SCANNER <<<")
    try:
        scanner.scan_market()
    except Exception as e:
        print(Fore.RED + f"Scanner Error: {e}")
    input(Fore.CYAN + "\nPress Enter to return...")

def run_backtest_ui():
    print_header()
    print(Fore.YELLOW + ">>> BACKTEST ENGINE <<<")
    
    days_input = input("Enter duration in days (Default: 7): ")
    days = int(days_input) if days_input.strip() else 7
    
    print(f"\nRunning simulation for the last {days} days on configured pairs...")
    try:
        # Reload backtest to pick up any changes
        importlib.reload(backtest)
        backtest.run_backtest(days=days)
    except TypeError:
        # Fallback if function signature isn't updated yet
        backtest.run_backtest()
    except Exception as e:
        print(Fore.RED + f"Backtest Error: {e}")
    input(Fore.CYAN + "\nPress Enter to return...")

def analyze_performance_ui():
    print_header()
    print(Fore.BLUE + ">>> PERFORMANCE ANALYTICS <<<")
    print("This tool reads your 'trade_history.csv' log file and calculates:")
    print("- Win Rate")
    print("- Total Net Profit")
    print("- Drawdown (Max loss from peak)")
    print("-" * 30)
    
    print("1. All History")
    print("2. Backtest Only")
    print("3. Paper Trading Only")
    print("4. Live Only")
    
    sub = input("Select Filter [1-4] (Default 1): ")
    mode_filter = None
    if sub == '2': mode_filter = "BACKTEST"
    elif sub == '3': mode_filter = "PAPER"
    elif sub == '4': mode_filter = "LIVE"
    
    try:
        analytics.analyze_performance(mode_filter)
    except Exception as e:
        print(Fore.RED + f"Analytics Error: {e}")
    input(Fore.CYAN + "\nPress Enter to return...")

def run_optimization_ui():
    print_header()
    print(Fore.MAGENTA + ">>> AI HYPERPARAMETER OPTIMIZATION <<<")
    print("This tool will re-run the strategy over the last 7 days using DIFFERENT settings")
    print("(e.g., tighter stops, loose stops, different timeframes) to find the MATHEMATICALLY BEST configuration.")
    print("-" * 30)
    
    confirm = input("Start Optimization? (y/n): ")
    if confirm.lower() == 'y':
        try:
            optimize.run_optimization()
        except Exception as e:
            print(Fore.RED + f"Optimization Error: {e}")
    input(Fore.CYAN + "\nPress Enter to return...")

def start_live_bot_ui():
    print_header()
    print(Fore.RED + Style.BRIGHT + ">>> LIVE TRADING BOT <<<")
    
    print("Choose Mode:")
    print("1. PAPER TRADING (Fake Money, Real Data)")
    print("2. LIVE TRADING (Real Money)")
    
    mode_sel = input("Select Mode [1-2]: ")
    
    if mode_sel == '1':
        os.environ['MODE'] = 'PAPER'
        # Update config module variable too if needed, but env usually enough if reloaded
    elif mode_sel == '2':
        confirm = input(Fore.RED + "WARNING: Real Money will be used. Type 'CONFIRM' to proceed: ")
        if confirm == 'CONFIRM':
            os.environ['MODE'] = 'LIVE'
        else:
            print("Aborted.")
            return
    else:
        print("Invalid selection.")
        return

    print(f"\nStarting Bot in {Fore.MAGENTA}{os.environ['MODE']}{Fore.RESET} mode...")
    print(Fore.YELLOW + "Press Ctrl+C to stop the bot and return to safety.")
    print("-" * 60)
    
    try:
        # Reload live_bot to pick up env change
        importlib.reload(live_bot)
        # Re-init bot
        live_bot.MODE = os.environ['MODE'] # Force update
        bot_instance = live_bot.DynamicBot()
        bot_instance.run()
    except KeyboardInterrupt:
        print(Fore.GREEN + "\nBot stopped manually.")
    except Exception as e:
        print(Fore.RED + f"Bot Crashed: {e}")
    
    input(Fore.CYAN + "\nPress Enter to return...")

def view_config_ui():
    print_header()
    print(Fore.WHITE + ">>> CONFIGURATION <<<")
    
    data = [
        ["SYMBOLS", ", ".join(SYMBOLS)],
        ["INTERVALS", ", ".join(INTERVALS)],
        ["SL_MULTIPLIER", SL_MULTIPLIER],
        ["TP_MULTIPLIER", TP_MULTIPLIER],
        ["MODE", os.environ.get("MODE", MODE)]
    ]
    
    print(tabulate(data, headers=["Param", "Value"], tablefmt="fancy_grid"))
    print("\nTo edit these values, modify the .env file.")
    input(Fore.CYAN + "\nPress Enter to return...")

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
