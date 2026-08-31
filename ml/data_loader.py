"""
data_loader.py
--------------
Two ways to get data:

1) KAGGLE CSV (recommended for reproducibility)
   Download one of these, unzip, and point CSV_PATH at it:
     - Stocks (daily, many tickers): https://www.kaggle.com/datasets/jacksoncrow/stock-market-dataset
     - Huge Stock Market Dataset:    https://www.kaggle.com/datasets/borismarjanovic/price-volume-data-for-all-us-stocks-etfs
     - Bitcoin (daily-2026, Binance):https://www.kaggle.com/datasets/novandraanugrah/bitcoin-historical-datasets-2018-2024
     - Bitcoin (1-min, since 2012):  https://www.kaggle.com/datasets/mczielinski/bitcoin-historical-data

   All of these give you standard OHLCV columns: Date/Timestamp, Open, High, Low, Close, Volume.

2) LIVE DOWNLOAD via yfinance (no Kaggle account needed, good for quick testing)
   Works for stocks, ETFs, and crypto (e.g. "BTC-USD") and forex pairs (e.g. "EURUSD=X").
"""

import pandas as pd
import yfinance as yf


def load_from_kaggle_csv(csv_path: str, date_col: str = "Date") -> pd.DataFrame:
    """Load a standard OHLCV CSV as downloaded from Kaggle."""
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().capitalize() for c in df.columns]
    df[date_col.capitalize()] = pd.to_datetime(df[date_col.capitalize()])
    df = df.sort_values(date_col.capitalize()).reset_index(drop=True)
    df = df.set_index(date_col.capitalize())
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return df[keep].dropna()


def load_live(ticker: str, start: str = "2015-01-01", end: str = None) -> pd.DataFrame:
    """
    Download real OHLCV data live. Examples of `ticker`:
      Stocks:  "AAPL", "TSLA", "MSFT"
      Crypto:  "BTC-USD", "ETH-USD"
      Forex:   "EURUSD=X", "GBPUSD=X"
    """
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}. Check the symbol/date range.")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


if __name__ == "__main__":
    # quick smoke test
    df = load_live("AAPL", start="2018-01-01")
    print(df.tail())
    print(f"\nRows: {len(df)}")
