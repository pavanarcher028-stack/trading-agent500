import sys
import os
import time
import threading
import random
from api import start_api
from strategy_store import save_strategy, load_strategy
from data import get_top5_ohlcv, get_market_summary
from backtest import run_backtest, is_strategy_good, get_metric_statistics
from trader import execute_strategy
from monitor import needs_regeneration, bump_strategy_version, get_performance_summary
from ai_improver import batch_improve_and_validate_strategies, generate_html_report

print("TRADING AGENT STARTED", flush=True)

active_strategy = None
active_good_coins = []
lock = threading.Lock()
trade_count = 0
revalidate_every = random.randint(10, 20)

STRATEGIES = [
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 2.0
    TP_PCT = 4.0
    close = df['close']
    rolling_mean = close.rolling(30).mean()
    rolling_std = close.rolling(30).std()
    zscore = (close - rolling_mean) / rolling_std
    signals = pd.Series(0, index=df.index)
    signals[zscore < -1.5] = 1
    signals[zscore > 1.5] = -1
    return signals
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 2.5
    TP_PCT = 5.0
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    upper = close.rolling(20).mean() + 1.5 * atr
    lower = close.rolling(20).mean() - 1.5 * atr
    vol_avg = volume.rolling(20).mean()
    signals = pd.Series(0, index=df.index)
    signals[(close > upper) & (volume > vol_avg)] = 1
    signals[(close < lower) & (volume > vol_avg)] = -1
    return signals
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 2.0
    TP_PCT = 4.0
    close = df['close']
    returns = close.pct_change()
    mom_mean = returns.rolling(20).mean()
    mom_std = returns.rolling(20).std()
    mom_zscore = (returns - mom_mean) / mom_std
    signals = pd.Series(0, index=df.index)
    signals[mom_zscore > 1.5] = 1
    signals[mom_zscore < -1.5] = -1
    return signals
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 2.0
    TP_PCT = 4.0
    close = df['close']
    mu = close.rolling(50).mean()
    sigma = close.rolling(50).std()
    deviation = (close - mu) / sigma
    signals = pd.Series(0, index=df.index)
    signals[deviation < -1.5] = 1
    signals[deviation > 1.5] = -1
    return signals
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 2.0
    TP_PCT = 4.0
    close = df['close']
    volume = df['volume']
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(9).mean()
    loss = -delta.where(delta < 0, 0.0).rolling(9).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    vol_avg = volume.rolling(20).mean()
    signals = pd.Series(0, index=df.index)
    signals[(rsi < 30) & (volume > vol_avg)] = 1
    signals[(rsi > 70) & (volume > vol_avg)] = -1
    return signals
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 2.0
    TP_PCT = 4.0
    close = df['close']
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = sma20 + 2 * std20
    lower = sma20 - 2 * std20
    bandwidth = (upper - lower) / sma20
    signals = pd.Series(0, index=df.index)
    signals[(close < lower) & (bandwidth > 0.02)] = 1
    signals[(close > upper) & (bandwidth > 0.02)] = -1
    return signals
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 2.0
    TP_PCT = 4.0
    close = df['close']
    fast = close.ewm(span=12).mean()
    slow = close.ewm(span=26).mean()
    macd = fast - slow
    signal = macd.ewm(span=9).mean()
    hist = macd - signal
    zscore = (hist - hist.rolling(30).mean()) / hist.rolling(30).std()
    signals = pd.Series(0, index=df.index)
    signals[zscore > 1.0] = 1
    signals[zscore < -1.0] = -1
    return signals
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 2.0
    TP_PCT = 4.0
    close = df['close']
    high = df['high']
    low = df['low']
    lowest = low.rolling(14).min()
    highest = high.rolling(14).max()
    stoch = 100 * (close - lowest) / (highest - lowest)
    stoch_ma = stoch.rolling(3).mean()
    signals = pd.Series(0, index=df.index)
    signals[(stoch_ma < 20) & (stoch_ma.shift(1) < 20)] = 1
    signals[(stoch_ma > 80) & (stoch_ma.shift(1) > 80)] = -1
    return signals
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 2.0
    TP_PCT = 4.0
    close = df['close']
    volume = df['volume']
    returns = close.pct_change()
    vol = returns.rolling(20).std()
    norm_returns = returns / vol
    vol_avg = volume.rolling(20).mean()
    signals = pd.Series(0, index=df.index)
    signals[(norm_returns > 1.0) & (volume > vol_avg)] = 1
    signals[(norm_returns < -1.0) & (volume > vol_avg)] = -1
    return signals
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.5
    TP_PCT = 3.0
    close = df['close']
    ema100 = close.ewm(span=100).mean()
    mu = close.rolling(20).mean()
    sigma = close.rolling(20).std()
    zscore = (close - mu) / sigma
    signals = pd.Series(0, index=df.index)
    signals[(zscore < -1.0) & (close > ema100)] = 1
    signals[(zscore > 1.0) & (close > ema100)] = -1
    return signals
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 2.5
    TP_PCT = 5.0
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(10).mean()
    mid = close.rolling(10).mean()
    upper = mid + atr
    lower = mid - atr
    vol_avg = volume.rolling(10).mean()
    ema50 = close.ewm(span=50).mean()
    signals = pd.Series(0, index=df.index)
    signals[(close < lower) & (volume > vol_avg) & (close > ema50)] = 1
    signals[(close > upper) & (volume > vol_avg)] = -1
    return signals
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 2.0
    TP_PCT = 4.0
    close = df['close']
    volume = df['volume']
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(7).mean()
    loss = -delta.where(delta < 0, 0.0).rolling(7).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    vol_avg = volume.rolling(14).mean()
    ema50 = close.ewm(span=50).mean()
    signals = pd.Series(0, index=df.index)
    signals[(rsi < 35) & (volume > vol_avg * 1.2) & (close > ema50)] = 1
    signals[(rsi > 65) & (volume > vol_avg * 1.2)] = -1
    return signals
"""
]


def search_strategy(all_data, coins):
    global active_strategy, active_good_coins
    print("[SEARCH] Testing " + str(len(STRATEGIES)) + " strategies for: " + str(coins), flush=True)
    for idx, strat in enumerate(STRATEGIES):
        try:
            subset_data = {c: all_data[c] for c in coins if c in all_data}
            results = run_backtest(strat, subset_data)
            good_coins, partial_fails = is_strategy_good(results)
            if good_coins:
                for coin in good_coins:
                    with lock:
                        if coin not in active_good_coins:
                            active_good_coins.append(coin)
                            active_strategy = strat
                            save_strategy(strat, active_good_coins)
                            print("[SEARCH] Strategy " + str(idx + 1) + " approved " + coin, flush=True)
                coins = [c for c in coins if c not in active_good_coins]
                if not coins:
                    print("[SEARCH] All coins approved", flush=True)
                    break
            if partial_fails:
                improved = batch_improve_and_validate_strategies(partial_fails, strat)
                if improved:
                    for coin, new_code in improved.items():
                        subset = {coin: all_data[coin]}
                        new_results = run_backtest(new_code, subset)
                        new_good, _ = is_strategy_good(new_results)
                        if coin in new_good:
                            with lock:
                                if coin not in active_good_coins:
                                    active_good_coins.append(coin)
                                    active_strategy = new_code
                                    save_strategy(new_code, active_good_coins)
                                    print("[SEARCH] AI improved strategy approved " + coin, flush=True)
                            coins = [c for c in coins if c not in active_good_coins]
        except Exception as e:
            print("[SEARCH] Strategy " + str(idx + 1) + " error: " + str(e), flush=True)
        time.sleep(2)
    remaining = [c for c in coins if c not in active_good_coins]
    if remaining:
        print("[SEARCH] No passing strategy for: " + str(remaining), flush=True)
    print("[SEARCH] Done. Active: " + str(active_good_coins), flush=True)


def revalidate(all_data):
    global active_strategy, active_good_coins, trade_count, revalidate_every
    print("[REVALIDATE] Re-testing strategy...", flush=True)
    with lock:
        strat = active_strategy
        coins = list(active_good_coins)
    if not strat or not coins:
        return
    subset_data = {c: all_data[c] for c in coins if c in all_data}
    results = run_backtest(strat, subset_data)
    still_good, partial_fails = is_strategy_good(results)
    failed_coins = [c for c in coins if c not in still_good]
    if failed_coins:
        print("[REVALIDATE] " + str(failed_coins) + " failed searching new strategy", flush=True)
        with lock:
            for c in failed_coins:
                if c in active_good_coins:
                    active_good_coins.remove(c)
            save_strategy(active_strategy, active_good_coins)
        threading.Thread(
            target=search_strategy,
            args=(all_data, failed_coins),
            daemon=True
        ).start()
    else:
        print("[REVALIDATE] All coins still passing", flush=True)
    trade_count = 0
    revalidate_every = random.randint(10, 20)
    print("[REVALIDATE] Next check in " + str(revalidate_every) + " trades", flush=True)


def trading_loop(all_data):
    global trade_count
    while True:
        try:
            with lock:
                strat = active_strategy
                coins = list(active_good_coins)
            if strat and coins:
                print("[TRADER] Trading: " + str(coins), flush=True)
                execute_strategy(strat, all_data, coins)
                trade_count += 1
                get_performance_summary()
                print("[TRADER] Trade " + str(trade_count) + " done. Revalidate at " + str(revalidate_every), flush=True)
                if trade_count >= revalidate_every:
                    revalidate(all_data)
                time.sleep(3600)
            else:
                print("[TRADER] Waiting for approved coins...", flush=True)
                time.sleep(300)
        except Exception as e:
            print("[TRADER] Error: " + str(e), flush=True)
            time.sleep(300)


def run_agent():
    global active_strategy, active_good_coins
    if not os.environ.get("COINDCX_API_KEY"):
        print("[ERROR] COINDCX_API_KEY missing", flush=True)
        sys.exit(1)
    if not os.environ.get("COINDCX_SECRET"):
        print("[ERROR] COINDCX_SECRET missing", flush=True)
        sys.exit(1)
    print("[AGENT] All keys found", flush=True)
    print("[AGENT] AI Providers: Google Gemini (Code Gen) + NVIDIA NIM (Validation)", flush=True)
    threading.Thread(target=start_api, daemon=True).start()
    loop_count = 0
    while True:
        try:
            loop_count += 1
            print("[AGENT] Loop " + str(loop_count), flush=True)
            all_data = get_top5_ohlcv()
            if not all_data:
                print("[AGENT] No data, waiting 10 mins", flush=True)
                time.sleep(600)
                continue
            get_metric_statistics()
            saved_code, saved_coins = load_strategy()
            if saved_code and saved_coins:
                with lock:
                    active_strategy = saved_code
                    active_good_coins = saved_coins
                print("[AGENT] Resuming saved strategy for: " + str(saved_coins), flush=True)
                remaining = [c for c in ["BTC", "ETH", "BNB", "SOL", "XRP"] if c not in saved_coins]
                if remaining:
                    search_thread = threading.Thread(
                        target=search_strategy,
                        args=(all_data, remaining),
                        daemon=True
                    )
                    search_thread.start()
                else:
                    search_thread = None
            else:
                bump_strategy_version()
                active_good_coins = []
                active_strategy = None
                search_thread = threading.Thread(
                    target=search_strategy,
                    args=(all_data, ["BTC", "ETH", "BNB", "SOL", "XRP"]),
                    daemon=True
                )
                search_thread.start()
            threading.Thread(
                target=trading_loop,
                args=(all_data,),
                daemon=True
            ).start()
            if search_thread:
                search_thread.join()
            print("[AGENT] Search done. Sleeping 5 mins", flush=True)
            time.sleep(300)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("[AGENT] Error: " + str(e), flush=True)
            time.sleep(900)


if __name__ == "__main__":
    run_agent()
