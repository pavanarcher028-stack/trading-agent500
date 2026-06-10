import requests
import pandas as pd
import time

COINS = {
    "BTC": "B-BTC_USDT",
    "ETH": "B-ETH_USDT",
    "BNB": "B-BNB_USDT",
    "SOL": "B-SOL_USDT",
    "XRP": "B-XRP_USDT"
}

INTERVALS = ["5m", "15m", "30m", "1h"]

def get_ohlcv(pair, interval):
    try:
        url = "https://public.coindcx.com/market_data/candles"
        limit = 200 if interval in ("5m", "15m") else 500 if interval == "30m" else 1000
        params = {"pair": pair, "interval": interval, "limit": limit}
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        if not data or len(data) == 0:
            print("[DATA] Empty response for " + pair + " " + interval, flush=True)
            return None
        if isinstance(data, dict):
            print("[DATA] Error for " + pair + " " + interval + ": " + str(data), flush=True)
            return None
        df = pd.DataFrame(data)
        if "time" in df.columns:
            df = df.rename(columns={"time": "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.sort_values("timestamp")
        df.set_index("timestamp", inplace=True)
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        print("[DATA] OK " + pair + " " + interval + " — " + str(len(df)) + " candles", flush=True)
        return df
    except Exception as e:
        print("[DATA] Failed " + pair + " " + interval + ": " + str(e), flush=True)
        return None

_data_cache = {}

def get_interval_data(interval):
    global _data_cache
    result = {}
    for symbol, pair in COINS.items():
        cache_key = symbol + "_" + interval
        if cache_key in _data_cache:
            result[symbol] = {interval: _data_cache[cache_key]}
            continue
        df = get_ohlcv(pair, interval)
        if df is not None:
            _data_cache[cache_key] = df
            result[symbol] = {interval: df}
        time.sleep(0.5)
    print("[DATA] Interval " + interval + " done — " + str(len(result)) + "/5 coins", flush=True)
    return result

def get_top5_multi_tf():
    global _data_cache
    all_data = {}
    for symbol, pair in COINS.items():
        all_data[symbol] = {}
        for interval in INTERVALS:
            cache_key = symbol + "_" + interval
            if cache_key in _data_cache:
                all_data[symbol][interval] = _data_cache[cache_key]
                continue
            df = get_ohlcv(pair, interval)
            if df is not None:
                _data_cache[cache_key] = df
                all_data[symbol][interval] = df
            time.sleep(0.5)
    print("[DATA] Multi-TF done — " + str(len(all_data)) + "/5 coins", flush=True)
    return all_data

def get_top5_ohlcv():
    data = get_top5_multi_tf()
    flat = {}
    for coin, tfs in data.items():
        if "1h" in tfs:
            flat[coin] = tfs["1h"]
    return flat

def get_market_summary(all_data):
    summary = []
    for coin in all_data:
        data = all_data[coin]
        if isinstance(data, dict):
            df = data.get("1h") or next(iter(data.values()))
        else:
            df = data
        if df is None or len(df) < 2:
            continue
        last_close = round(df["close"].iloc[-1], 4)
        change = round(((df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]) * 100, 2)
        summary.append(coin + ": price=" + str(last_close) + ", change=" + str(change) + "%")
    result = "\n".join(summary)
    print("[DATA] Summary:\n" + result, flush=True)
    return result

def get_usd_to_inr():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url, timeout=10)
        data = response.json()
        rate = float(data["rates"]["INR"])
        print("[DATA] Live USD/INR rate: " + str(rate), flush=True)
        return rate
    except:
        print("[DATA] Rate fetch failed, using 84.0", flush=True)
        return 84.0
