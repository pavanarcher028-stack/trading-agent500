import sys
import os
import time
import threading
import random
import log_capture; log_capture.install()
from api import start_api
from strategy_store import save_strategy, load_strategy
from data import get_top5_ohlcv, get_market_summary
from backtest import run_backtest, is_strategy_good
from trader import execute_strategy
from monitor import bump_strategy_version, get_performance_summary
# AI improver no longer used - fallback strategies only
from data import get_market_summary

print("TRADING AGENT STARTED", flush=True)

active_strategy = None
active_good_coins = []
lock = threading.Lock()
trade_count = 0
revalidate_every = random.randint(10, 20)

FALLBACK_STRATEGIES = [
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.5
    TP_PCT = 3.0
    close = df['close']
    volume = df['volume']
    ema5 = close.ewm(span=5).mean()
    ema13 = close.ewm(span=13).mean()
    ema50 = close.ewm(span=50).mean()
    vol_avg = volume.rolling(14).mean()
    raw = pd.Series(0, index=df.index)
    raw[(ema5 > ema13) & (close > ema5) & (close > ema50) & (volume > vol_avg)] = 1
    raw[(ema5 < ema13) & (close < ema5) & (close < ema50) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.5
    TP_PCT = 3.0
    close = df['close']
    volume = df['volume']
    returns = close.pct_change()
    vol = returns.rolling(14).std()
    norm_ret = returns / vol
    norm_z = (norm_ret - norm_ret.rolling(14).mean()) / norm_ret.rolling(14).std()
    ema50 = close.ewm(span=50).mean()
    ema100 = close.ewm(span=100).mean()
    vol_avg = volume.rolling(14).mean()
    raw = pd.Series(0, index=df.index)
    raw[(norm_z > 0.4) & (close > ema50) & (close > ema100) & (volume > vol_avg)] = 1
    raw[(norm_z < -0.4) & (close < ema50) & (close < ema100) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.8
    TP_PCT = 3.5
    close = df['close']
    volume = df['volume']
    high = df['high']
    low = df['low']
    donchian_high = high.rolling(14).max()
    donchian_low = low.rolling(14).min()
    mid = (donchian_high + donchian_low) / 2
    vol_avg = volume.rolling(14).mean()
    ema50 = close.ewm(span=50).mean()
    raw = pd.Series(0, index=df.index)
    raw[(close > donchian_high.shift(1)) & (close > ema50) & (volume > vol_avg)] = 1
    raw[(close < donchian_low.shift(1)) & (close < ema50) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.8
    TP_PCT = 3.5
    close = df['close']
    volume = df['volume']
    ema10 = close.ewm(span=10).mean()
    ema30 = close.ewm(span=30).mean()
    ema100 = close.ewm(span=100).mean()
    vol_avg = volume.rolling(14).mean()
    raw = pd.Series(0, index=df.index)
    raw[(ema10 > ema30) & (close > ema10) & (close > ema100) & (volume > vol_avg)] = 1
    raw[(ema10 < ema30) & (close < ema10) & (close < ema100) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.5
    TP_PCT = 3.0
    close = df['close']
    volume = df['volume']
    sma = close.rolling(10).mean()
    std = close.rolling(10).std()
    zscore = (close - sma) / std
    vol_avg = volume.rolling(14).mean()
    ema50 = close.ewm(span=50).mean()
    raw = pd.Series(0, index=df.index)
    raw[(zscore < -0.8) & (close > ema50) & (volume > vol_avg)] = 1
    raw[(zscore > 0.8) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.8
    TP_PCT = 3.5
    close = df['close']
    volume = df['volume']
    high = df['high']
    low = df['low']
    tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(10).mean()
    mid = close.rolling(10).mean()
    upper = mid + atr
    lower = mid - atr
    ema50 = close.ewm(span=50).mean()
    vol_avg = volume.rolling(10).mean()
    raw = pd.Series(0, index=df.index)
    raw[(close > upper) & (close > ema50) & (volume > vol_avg)] = 1
    raw[(close < lower) & (close < ema50) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
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
    sma = close.rolling(10).mean()
    std = close.rolling(10).std()
    zscore = (close - sma) / std
    vol_avg = volume.rolling(14).mean()
    ema50 = close.ewm(span=50).mean()
    raw = pd.Series(0, index=df.index)
    raw[(rsi < 40) & (zscore < -0.6) & (close > ema50) & (volume > vol_avg)] = 1
    raw[(rsi > 60) & (zscore > 0.6) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.5
    TP_PCT = 3.0
    close = df['close']
    volume = df['volume']
    ema5 = close.ewm(span=5).mean()
    ema13 = close.ewm(span=13).mean()
    ema50 = close.ewm(span=50).mean()
    ema100 = close.ewm(span=100).mean()
    vol_avg = volume.rolling(10).mean()
    raw = pd.Series(0, index=df.index)
    raw[(ema5 > ema13) & (close > ema5) & (close > ema50) & (close > ema100) & (volume > vol_avg)] = 1
    raw[(ema5 < ema13) & (close < ema5) & (close < ema50) & (close < ema100) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(10).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.0
    TP_PCT = 2.0
    close = df['close']
    volume = df['volume']
    high = df['high']
    low = df['low']
    donchian_high = high.rolling(10).max()
    donchian_low = low.rolling(10).min()
    ema100 = close.ewm(span=100).mean()
    vol_avg = volume.rolling(10).mean()
    raw = pd.Series(0, index=df.index)
    raw[(close > donchian_high.shift(1)) & (close > ema100) & (volume > vol_avg)] = 1
    raw[(close < donchian_low.shift(1)) & (close < ema100) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(10).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.0
    TP_PCT = 3.0
    close = df['close']
    volume = df['volume']
    sma = close.rolling(5).mean()
    std = close.rolling(5).std()
    zscore = (close - sma) / std
    ema100 = close.ewm(span=100).mean()
    vol_avg = volume.rolling(10).mean()
    raw = pd.Series(0, index=df.index)
    raw[(zscore < -1.0) & (close > ema100) & (volume > vol_avg)] = 1
    raw[(zscore > 1.0) & (close < ema100) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(20).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.5
    TP_PCT = 3.0
    close = df['close']
    volume = df['volume']
    high = df['high']
    low = df['low']
    tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    mid = close.rolling(14).mean()
    upper = mid + 1.5 * atr
    lower = mid - 1.5 * atr
    ema100 = close.ewm(span=100).mean()
    vol_avg = volume.rolling(14).mean()
    raw = pd.Series(0, index=df.index)
    raw[(close > upper) & (close > ema100) & (volume > vol_avg)] = 1
    raw[(close < lower) & (close < ema100) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(20).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 0.9
    TP_PCT = 2.5
    close = df['close']
    volume = df['volume']
    ema10 = close.ewm(span=10).mean()
    ema30 = close.ewm(span=30).mean()
    ema100 = close.ewm(span=100).mean()
    vol_avg = volume.rolling(14).mean()
    raw = pd.Series(0, index=df.index)
    raw[(ema10 > ema30) & (close > ema10) & (close > ema100) & (volume > vol_avg)] = 1
    raw[(ema10 < ema30) & (close < ema10) & (close < ema100) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 0.8
    TP_PCT = 2.5
    close = df['close']
    volume = df['volume']
    vol_avg = volume.rolling(14).mean()
    ema100 = close.ewm(span=100).mean()
    up = (close > close.shift(1)).astype(int)
    down = (close < close.shift(1)).astype(int)
    cons_up = up.rolling(4).sum()
    cons_down = down.rolling(4).sum()
    raw = pd.Series(0, index=df.index)
    raw[(cons_down >= 4) & (close > ema100) & (volume > vol_avg)] = 1
    raw[(cons_up >= 4) & (close < ema100) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.5
    TP_PCT = 3.0
    close = df['close']
    volume = df['volume']
    vol_avg = volume.rolling(14).mean()
    ema50 = close.ewm(span=50).mean()
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    rsi_period = 14
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(rsi_period).mean()
    loss = -delta.where(delta < 0, 0.0).rolling(rsi_period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    raw = pd.Series(0, index=df.index)
    raw[(macd > signal) & (rsi > 50) & (close > ema50) & (volume > vol_avg)] = 1
    raw[(macd < signal) & (rsi < 50) & (close < ema50) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.5
    TP_PCT = 3.0
    close = df['close']
    volume = df['volume']
    vol_avg = volume.rolling(14).mean()
    ema50 = close.ewm(span=50).mean()
    sma = close.rolling(20).mean()
    std = close.rolling(20).std()
    upper = sma + 2 * std
    lower = sma - 2 * std
    bb_width = (upper - lower) / sma
    squeeze = bb_width < bb_width.rolling(50).quantile(0.2)
    raw = pd.Series(0, index=df.index)
    raw[(close > upper) & squeeze.shift(1) & (close > ema50) & (volume > vol_avg)] = 1
    raw[(close < lower) & squeeze.shift(1) & (close < ema50) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.5
    TP_PCT = 3.0
    close = df['close']
    volume = df['volume']
    vol_avg = volume.rolling(14).mean()
    ema50 = close.ewm(span=50).mean()
    rsi_period = 14
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(rsi_period).mean()
    loss = -delta.where(delta < 0, 0.0).rolling(rsi_period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    price_lower = close < close.rolling(5).min().shift(1)
    rsi_higher = rsi > rsi.rolling(5).min().shift(1)
    price_higher = close > close.rolling(5).max().shift(1)
    rsi_lower = rsi < rsi.rolling(5).max().shift(1)
    raw = pd.Series(0, index=df.index)
    raw[price_lower & rsi_higher & (close > ema50) & (volume > vol_avg)] = 1
    raw[price_higher & rsi_lower & (close < ema50) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.5
    TP_PCT = 3.0
    close = df['close']
    volume = df['volume']
    vol_avg = volume.rolling(14).mean()
    ema5 = close.ewm(span=5).mean()
    ema10 = close.ewm(span=10).mean()
    ema20 = close.ewm(span=20).mean()
    ema50 = close.ewm(span=50).mean()
    ema100 = close.ewm(span=100).mean()
    bullish = (ema5 > ema10) & (ema10 > ema20) & (ema20 > ema50) & (ema50 > ema100)
    bearish = (ema5 < ema10) & (ema10 < ema20) & (ema20 < ema50) & (ema50 < ema100)
    raw = pd.Series(0, index=df.index)
    raw[bullish & (close > ema5) & (volume > vol_avg)] = 1
    raw[bearish & (close < ema5) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 2.0
    TP_PCT = 4.0
    close = df['close']
    volume = df['volume']
    high = df['high']
    low = df['low']
    vol_avg = volume.rolling(10).mean()
    ema50 = close.ewm(span=50).mean()
    tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(10).mean()
    mult = 2.0
    upper = close.rolling(10).mean() + mult * atr
    lower = close.rolling(10).mean() - mult * atr
    trend = pd.Series(1, index=df.index)
    trend[(close < lower) | ((close < upper) & (trend.shift(1) == 1))] = -1
    trend[(close > upper) | ((close > lower) & (trend.shift(1) == -1))] = 1
    raw = pd.Series(0, index=df.index)
    raw[(trend == 1) & (trend.shift(1) == -1) & (close > ema50) & (volume > vol_avg)] = 1
    raw[(trend == -1) & (trend.shift(1) == 1) & (close < ema50) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.5
    TP_PCT = 3.0
    close = df['close']
    volume = df['volume']
    high = df['high']
    low = df['low']
    vol_avg = volume.rolling(14).mean()
    ema50 = close.ewm(span=50).mean()
    tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(10).mean()
    ema = close.ewm(span=20).mean()
    keltner_upper = ema + 2 * atr
    keltner_lower = ema - 2 * atr
    raw = pd.Series(0, index=df.index)
    raw[(close > keltner_upper) & (close > ema50) & (volume > vol_avg)] = 1
    raw[(close < keltner_lower) & (close < ema50) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
""",
"""
def get_signals(df):
    import pandas as pd
    import numpy as np
    SL_PCT = 1.5
    TP_PCT = 3.0
    close = df['close']
    volume = df['volume']
    high = df['high']
    low = df['low']
    vol_avg = volume.rolling(14).mean()
    ema50 = close.ewm(span=50).mean()
    tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    psar = close.copy()
    trend = pd.Series(1, index=df.index)
    af = 0.02
    max_af = 0.2
    ep = close.iloc[0]
    for i in range(1, len(close)):
        if trend.iloc[i-1] == 1:
            psar.iloc[i] = psar.iloc[i-1] + af * (ep - psar.iloc[i-1])
            if close.iloc[i] < psar.iloc[i]:
                trend.iloc[i] = -1
                psar.iloc[i] = ep
                ep = close.iloc[i]
                af = 0.02
            else:
                trend.iloc[i] = 1
                if close.iloc[i] > ep:
                    ep = close.iloc[i]
                    af = min(af + 0.02, max_af)
        else:
            psar.iloc[i] = psar.iloc[i-1] + af * (ep - psar.iloc[i-1])
            if close.iloc[i] > psar.iloc[i]:
                trend.iloc[i] = 1
                psar.iloc[i] = ep
                ep = close.iloc[i]
                af = 0.02
            else:
                trend.iloc[i] = -1
                if close.iloc[i] < ep:
                    ep = close.iloc[i]
                    af = min(af + 0.02, max_af)
    adx_period = 14
    up_move = high.diff()
    down_move = low.diff()
    plus_dm = ((up_move > down_move) & (up_move > 0)).astype(float) * up_move
    minus_dm = ((down_move > up_move) & (down_move > 0)).astype(float) * down_move
    tr_series = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    atr_adx = tr_series.rolling(adx_period).mean()
    plus_di = 100 * plus_dm.rolling(adx_period).mean() / atr_adx
    minus_di = 100 * minus_dm.rolling(adx_period).mean() / atr_adx
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
    adx = dx.rolling(adx_period).mean()
    sar_flip = trend != trend.shift(1)
    raw = pd.Series(0, index=df.index)
    raw[sar_flip & (trend == 1) & (adx > 25) & (close > ema50) & (volume > vol_avg)] = 1
    raw[sar_flip & (trend == -1) & (adx > 25) & (close < ema50) & (volume > vol_avg)] = -1
    signals = raw / close.rolling(14).std()
    return signals.fillna(0)
"""
]


def is_strategy_good_relaxed(results):
    good_coins = []
    for coin, score in results.items():
        sharpe = score.get("sharpe", 0)
        win_rate = score.get("win_rate", 0)
        max_drawdown = score.get("max_drawdown", 100)
        trades = score.get("trades", 0)
        passed = sharpe >= 0.3 and win_rate >= 45.0 and max_drawdown <= 20.0 and trades >= 3
        if passed:
            good_coins.append(coin)
    return good_coins


def try_fallback_strategies(coin, all_data):
    print("[FALLBACK] Trying indicator-based strategies for " + coin, flush=True)
    subset = {coin: all_data[coin]} if coin in all_data else {}
    if not subset:
        return None
    results_list = []
    for idx, strat in enumerate(FALLBACK_STRATEGIES):
        try:
            results = run_backtest(strat, subset)
            results_list.append((idx, strat, results))
        except Exception as e:
            print("[FALLBACK] Strategy " + str(idx + 1) + " error: " + str(e), flush=True)
    for idx, strat, results in results_list:
        good_coins, _ = is_strategy_good(results)
        if coin in good_coins:
            print("[FALLBACK] Strategy " + str(idx + 1) + " passed (strict) for " + coin, flush=True)
            return strat
    print("[FALLBACK] No strict pass for " + coin + " - trying relaxed thresholds...", flush=True)
    for idx, strat, results in results_list:
        if coin in is_strategy_good_relaxed(results):
            print("[FALLBACK] Strategy " + str(idx + 1) + " passed (relaxed) for " + coin, flush=True)
            return strat
    return None


def search_strategy(all_data, coins):
    global active_strategy, active_good_coins
    market_summary = get_market_summary(all_data)
    print("[SEARCH] Finding strategies for: " + str(coins), flush=True)
    for coin in coins:
        try:
            if coin in active_good_coins:
                continue
            print("[SEARCH] Searching strategy for " + coin + "...", flush=True)
            code = try_fallback_strategies(coin, all_data)
            if not code:
                print("[SEARCH] No strategy passed for " + coin + " - skipping", flush=True)
                continue
            subset = {coin: all_data[coin]} if coin in all_data else {}
            if not subset:
                continue
            with lock:
                active_good_coins.append(coin)
                active_strategy = code
                save_strategy(code, active_good_coins)
            print("[SEARCH] Strategy approved for " + coin, flush=True)
        except Exception as e:
            print("[SEARCH] Error for " + coin + ": " + str(e), flush=True)
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
    relaxed_good = is_strategy_good_relaxed(results)
    failed_coins = [c for c in coins if c not in still_good and c not in relaxed_good]
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
    threading.Thread(target=start_api, daemon=True).start()
    if not os.environ.get("COINDCX_API_KEY") or not os.environ.get("COINDCX_SECRET"):
        print("[AGENT] CoinDCX API keys not set - website mode only. Trading disabled.", flush=True)
        while True:
            time.sleep(3600)
        return
    print("[AGENT] All keys found", flush=True)
    print("[AGENT] Strategy source: 20 built-in fallback strategies (no AI)", flush=True)
    trading_thread_started = False
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
            saved_code, saved_coins = load_strategy()
            if saved_code and saved_coins:
                with lock:
                    active_strategy = saved_code
                    active_good_coins = saved_coins
                print("[AGENT] Resuming saved strategy for: " + str(saved_coins), flush=True)
                if active_strategy and active_good_coins:
                    proof = run_backtest(active_strategy, {c: all_data[c] for c in active_good_coins if c in all_data})
                    for c, s in proof.items():
                        status = "PASS" if s["passed"] else "FAIL"
                        print("[PROOF] " + c + " [" + status + "] Sharpe: " + str(s["sharpe"]) + " Win: " + str(s["win_rate"]) + "% DD: " + str(s["max_drawdown"]) + "% Trades: " + str(s["trades"]), flush=True)
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
            if not trading_thread_started:
                threading.Thread(
                    target=trading_loop,
                    args=(all_data,),
                    daemon=True
                ).start()
                trading_thread_started = True
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
