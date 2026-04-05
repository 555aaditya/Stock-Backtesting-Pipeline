import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from typing import List, Dict

# Try to use a nice style if available
try:
    plt.style.use('ggplot')
except:
    pass

def plot_equity_curve(portfolio: List[Dict], ticker: str, strategy: str, metrics: Dict[str, float], output_dir: str = "data"):
    """Plots the equity curve and saves it to a PNG."""
    os.makedirs(output_dir, exist_ok=True)
    
    dates = [datetime.strptime(row["date"], "%Y-%m-%d") for row in portfolio]
    values = [row["value"] for row in portfolio]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(dates, values, label="Portfolio Value", color="#1f77b4", linewidth=1.5)
    
    # Format x-axis for dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    
    title = (
        f"Equity Curve: {ticker} ({strategy})\n"
        f"Return: {metrics.get('Total Return', 0):.2f}% | "
        f"CAGR: {metrics.get('CAGR', 0):.2f}% | "
        f"Sharpe: {metrics.get('Sharpe Ratio', 0):.2f} | "
        f"Max DD: {metrics.get('Max Drawdown', 0):.2f}%"
    )
    
    ax.set_title(title, fontsize=12)
    ax.set_ylabel("Portfolio Value ($)")
    ax.set_xlabel("Date")
    ax.legend(loc="upper left")
    ax.grid(True, linestyle="--", alpha=0.6)
    
    plt.tight_layout()
    
    save_path = os.path.join(output_dir, f"{ticker}_{strategy}_equity.png")
    plt.savefig(save_path, dpi=300)
    plt.close(fig)

def plot_signals(portfolio: List[Dict], ticker: str, strategy: str, output_dir: str = "data"):
    """Plots the price with buy signals overlaid as green triangles."""
    os.makedirs(output_dir, exist_ok=True)
    
    dates = [datetime.strptime(row["date"], "%Y-%m-%d") for row in portfolio]
    prices = [row["price"] for row in portfolio]
    signals = [row["signal"] for row in portfolio]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(dates, prices, label="Close Price", color="#444444", linewidth=1.2, alpha=0.8)
    
    # Find points where signal flipped to 1 from 0 (meaning we bought)
    buy_dates = []
    buy_prices = []
    
    # Signal represents our CURRENT position over the day's close.
    # If previous signal was 0 and current is 1, a buy executed.
    prev_signal = 0
    for i in range(len(portfolio)):
        current_signal = signals[i]
        if current_signal == 1 and prev_signal == 0:
            buy_dates.append(dates[i])
            buy_prices.append(prices[i])
        prev_signal = current_signal
        
    # Overlay green triangles at buy points
    if buy_dates:
        ax.scatter(buy_dates, buy_prices, marker="^", color="#2ca02c", s=100, label="Buy Signal", zorder=3)
        
    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    
    ax.set_title(f"Price & Signals: {ticker} ({strategy})", fontsize=12)
    ax.set_ylabel("Price ($)")
    ax.set_xlabel("Date")
    ax.legend(loc="upper left")
    ax.grid(True, linestyle="--", alpha=0.6)
    
    plt.tight_layout()
    
    save_path = os.path.join(output_dir, f"{ticker}_{strategy}_signals.png")
    plt.savefig(save_path, dpi=300)
    plt.close(fig)
