import ccxt
import pandas as pd

exchange = ccxt.binance()

COINS = [
    'BTC/USDT',
    'ETH/USDT',
    'XRP/USDT',
    'SOL/USDT',
    'DOGE/USDT'
]

def get_top5_ohlcv():
    all_data = {}
    for coin in COINS:
        try:
            ohlcv = exchange.fetch_ohlcv(coin, timeframe='1h', limit=200)
            df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            all_data[coin] = df
            print(f"Fetched {coin}")
        except Exception as e:
            print(f"Failed {coin}: {e}")
    return all_data

def get_market_summary(all_data):
    summary = []
    for coin, df in all_data.items():
        last_close = round(df['close'].iloc[-1], 2)
        change = round(((df['close'].iloc[-1] - df['close'].iloc[-24]) / df['close'].iloc[-24]) * 100, 2)
        summary.append(f"{coin}: price={last_close} USDT, 24h change={change}%")
    return "\n".join(summary)
