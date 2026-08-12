import ccxt
import pandas as pd
from datetime import datetime
import pytz

def get_dhaka_time():
    tz = pytz.timezone('Asia/Dhaka')
    return datetime.now(tz).strftime('%Y-%m-%d %I:%M:%S %p')

def fetch_data(symbol: str = "BTC/USDT", timeframe: str = "5m", limit: int = 100) -> pd.DataFrame:
    """Binance থেকে লাইভ Kline/Candlestick ডেটা ফেচ করে"""
    try:
        exchange = ccxt.binance({'enableRateLimit': True})
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        
        df = pd.DataFrame(ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame()
