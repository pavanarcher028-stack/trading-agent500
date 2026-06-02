import sys
import requests
import pandas as pd

sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1)

print("[DATA] Starting data module...", flush=True)

COINS = ['BTC', 'ETH', 'XRP', 'DOGE', 'MATIC']

COINGECKO_IDS = {
    'BTC':   'bitcoin',
    'ETH':   'ethereum',
    'XRP':   'ripple',
    'DOGE':  'dogecoin',
    'MATIC': 'matic-network'
}

def get_ohlcv_for_coin(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params = {
            'vs_currency': 'usd',
            'days': '14'
        }
        response = requests.get(url, params=params, timeout=15)
        data = response.json()

        if not data or isinstance(data, dict):
            print(f"[DATA] Bad response for {coin_id}: {data}", flush=True)
            return None

        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df['volume'] = 1000000
        print(f"[DATA] OK {coin_id} — {len(df)} candles — last close: {df['close'].iloc[-1]}", flush=True)
        return df

    except Exception as e:
        print(f"[DATA] Failed {coin_id}: {e}", flush=True)
        return None

def get_top5_ohlcv():
    all_data = {}
    for symbol in COINS:
        coin_id = COINGECKO_IDS[symbol]
        print(f"[DATA] Fetching {symbol}...", flush=True)
        df = get_ohlcv_for_coin(coin_id)
        if df is not None:
            all_data[symbol] = df
        # wait between requests to respect rate limit
        import time
        time.sleep(2)

    print(f"[DATA] Done — fetched {len(all_data)}/5 coins", flush=True)
    return all_data

def get_market_summary(all_data):
    summary = []
    for coin, df in all_data.items():
        last_close = round(df['close'].iloc[-1], 4)
        if len(df) >= 2:
            change = round(
                ((df['close'].iloc[-1] - df['close'].iloc[-2])
                / df['close'].iloc[-2]) * 100, 2
            )
        else:
            change = 0
        summary.append(
            f"{coin}: price={last_close} USD, change={change}%"
        )
    result = "\n".join(summary)
    print(f"[DATA] Market summary:\n{result}", flush=True)
    return result
