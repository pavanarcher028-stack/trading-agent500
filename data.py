import sys
import requests
import pandas as pd
import time

sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1)

print("[DATA] Starting...", flush=True)

COINS = {
    'BTC': 'BTCINR',
    'ETH': 'ETHINR',
    'BNB': 'BNBINR',
    'SOL': 'SOLUSDT',
    'XRP': 'XRPINR'
}

def get_ohlcv(symbol, pair):
    try:
        url = "https://public.coindcx.com/market_data/candles"
        params = {
            'pair': pair,
            'interval': '1h',
            'limit': 200
        }
        response = requests.get(url, params=params, timeout=15)
        print(f"[DATA] {pair} status code: {response.status_code}", flush=True)

        data = response.json()

        if not data:
            print(f"[DATA] Empty response for {pair}", flush=True)
            return None

        if isinstance(data, dict) and 'error' in data:
            print(f"[DATA] API error for {pair}: {data}", flush=True)
            return None

        df = pd.DataFrame(data)
        print(f"[DATA] {pair} columns: {list(df.columns)}", flush=True)

        # rename time column
        if 'time' in df.columns:
            df = df.rename(columns={'time': 'timestamp'})
        elif 'open_time' in df.columns:
            df = df.rename(columns={'open_time': 'timestamp'})

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.sort_values('timestamp')
        df.set_index('timestamp', inplace=True)
        df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

        print(f"[DATA] OK {pair} — {len(df)} candles — last close: {df['close'].iloc[-1]}", flush=True)
        return df

    except Exception as e:
        print(f"[DATA] Failed {pair}: {e}", flush=True)
        return None

def get_top5_ohlcv():
    all_data = {}
    for symbol, pair in COINS.items():
        print(f"[DATA] Fetching {symbol} ({pair})...", flush=True)
        df = get_ohlcv(symbol, pair)
        if df is not None:
            all_data[symbol] = df
        time.sleep(1)
    print(f"[DATA] Done — {len(all_data)}/5 coins fetched", flush=True)
    return all_data

def get_market_summary(all_data):
    summary = []
    for coin, df in all_data.items():
        last_close = round(df['close'].iloc[-1], 2)
        change = round(
            ((df['close'].iloc[-1] - df['close'].iloc[-2])
            / df['close'].iloc[-2]) * 100, 2
        )
        summary.append(f"{coin}: price={last_close}, change={change}%")
    result = "\n".join(summary)
    print(f"[DATA] Summary:\n{result}", flush=True)
    return result
