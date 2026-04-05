import argparse
import logging
import os
from config import WATCHLIST, DEFAULT_START_DATE, DEFAULT_END_DATE, INITIAL_CAPITAL
from src.fetcher import fetch_ohlcv
from src.storage import init_db, save_prices, load_prices
from src.strategy import sma_crossover_strategy, rsi_mean_reversion_strategy
from src.backtester import run_backtest
from src.charts import plot_equity_curve, plot_signals
from src.metrics import total_return, cagr, max_drawdown, sharpe_ratio

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

STRATEGIES = {
    "sma_crossover": sma_crossover_strategy,
    "rsi_mean_reversion": rsi_mean_reversion_strategy
}

def run_pipeline(args):
    # Ensure DB is created
    init_db()
    
    tickers = [args.ticker] if args.ticker else WATCHLIST
    strategies_to_run = [args.strategy] if args.strategy else list(STRATEGIES.keys())
    
    for ticker in tickers:
        logging.info(f"--- Processing {ticker} ---")
        
        # 1. Fetch
        try:
            logging.info(f"Fetching data for {ticker} from API ({args.start} to {args.end})...")
            rows = fetch_ohlcv(ticker, args.start, args.end)
        except Exception as e:
            logging.error(f"Failed to fetch data for {ticker}: {e}")
            continue
            
        if not rows:
            logging.warning(f"No data returned for {ticker}.")
            continue
            
        # 2. Save and Load
        try:
            save_prices(ticker, rows)
            data = load_prices(ticker, args.start, args.end)
        except Exception as e:
            logging.error(f"Database error for {ticker}: {e}")
            continue
            
        if args.fetch_only:
            logging.info(f"Fetch-only mode active. Skipping backtest for {ticker}.")
            continue
            
        # 3. Strategy & Backtest Loop
        for strat_name in strategies_to_run:
            logging.info(f"Running strategy: {strat_name}")
            strat_func = STRATEGIES[strat_name]
            
            try:
                # Generate signals
                signals = strat_func(data)
                if not signals:
                    logging.warning(f"No signals generated for {ticker} using {strat_name}.")
                    continue
                
                # Run Backtest
                portfolio = run_backtest(data, signals, initial_capital=args.capital)
                if not portfolio:
                    logging.warning(f"Portfolio empty for {ticker} using {strat_name}.")
                    continue
                
                # Calculate metrics
                values = [p["value"] for p in portfolio]
                metrics = {
                    "Total Return": total_return(values),
                    "CAGR": cagr(values),
                    "Max Drawdown": max_drawdown(values),
                    "Sharpe Ratio": sharpe_ratio(values)
                }
                
                # Print summary
                print(f"\n[{ticker} | {strat_name}] Performance:")
                for k, v in metrics.items():
                    print(f"  {k}: {v:.2f}" + ("" if k == "Sharpe Ratio" else "%"))
                print("-" * 40)
                
                # 4. Save charts
                plot_equity_curve(portfolio, ticker, strat_name, metrics)
                plot_signals(portfolio, ticker, strat_name)
                
            except Exception as e:
                logging.error(f"Backtest failed for {ticker} with {strat_name}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Stock Backtesting Pipeline")
    parser.add_argument("--ticker", type=str, help="Specific ticker to run (runs WATCHLIST if omitted)")
    parser.add_argument("--strategy", type=str, choices=STRATEGIES.keys(), help="Specific strategy to run")
    parser.add_argument("--start", type=str, default=DEFAULT_START_DATE, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=DEFAULT_END_DATE, help="End date YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=INITIAL_CAPITAL, help="Initial capital")
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch and store data, skip backtest")
    
    args = parser.parse_args()
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    try:
        run_pipeline(args)
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        
if __name__ == "__main__":
    main()
