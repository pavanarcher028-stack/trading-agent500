import sys
import os
import time
import threading
import random
import requests
from api import start_api
from strategy_store import save_strategy, load_strategy
from data import get_top5_ohlcv, get_market_summary
from backtest import run_backtest, is_strategy_good
from trader import execute_strategy
from monitor import needs_regeneration, bump_strategy_version, get_performance_summary

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
print("TRADING AGENT STARTED", flush=True)

active_strategy = None
active_good_coins = []
lock = threading.Lock()
trade_count = 0
revalidate_every = random.randint(10, 20)


def build_prompt(market_summary, coins):
    p = "You are an expert quantitative mathematician building crypto trading strategies.\n"
    p += "Market data: " + market_summary + "\n"
    p += "Target coins: " + ", ".join(coins) + "\n"
    p += "Write a Python function get_signals(df).\n"
    p += "df has columns: open, high, low, close, volume.\n"
    p += "Return pandas Series: 1=buy, -1=sell, 0=hold.\n"
    p += "The function MUST start with: import pandas as pd\n"
    p += "The function MUST start with: import numpy as np\n"
    p += "Use ONE of these proven quant math approaches:\n"
    p += "1. Z-Score mean reversion: zscore = (price - rolling_mean) / rolling_std, buy when zscore < -1.5, sell when zscore > 1.5\n"
    p += "2. Hurst exponent regime: calculate rolling variance ratio, buy in mean-reverting regime, sell in trending regime\n"
    p += "3. Volatility breakout: ATR-based entry when price breaks above upper band with volume confirmation\n"
    p += "4. Momentum z-score: standardized returns momentum with rolling 20 period window\n"
    p += "5. Ornstein-Uhlenbeck: estimate mean reversion speed, trade when price deviates more than 1.5 sigma\n"
    p += "IMPORTANT: Strategy must generate at least 15 trades over 1000 hourly candles.\n"
    p += "Use rolling windows of 20-50 periods maximum.\n"
    p += "Stop loss enforced externally at 3 percent. Take profit at 6 percent.\n"
    p += "Return ONLY the raw Python function. No markdown. No explanation.\n"
    return p


def build_fix_prompt(market_summary, strategy_code, failed_tests, coins):
    p = "Fix this Python trading function for coins: " + ", ".join(coins) + "\n"
    p += strategy_code + "\n"
    p += "These coins failed:\n"
    for f in failed_tests:
        p += f["coin"] + " failed " + f["test"] + " got " + f["value"] + "\n"
    p += "Fix only the weak parts. Return ONLY the function. No markdown.\n"
    return p


def clean_code(full):
    if "```python" in full:
        code = full.split("```python")[1].split("```")[0].strip()
    elif "```" in full:
        code = full.split("```")[1].split("```")[0].strip()
    elif "def get_signals" in full:
        idx = full.index("def get_signals")
        code = full[idx:].strip()
    else:
        code = full.strip()
    for tag in ["<think>", "</think>", "<reasoning>", "</reasoning>"]:
        code = code.replace(tag, "")
    if "def get_signals" not in code:
        return None
    return code.strip()


def call_nvidia(prompt):
    print("[AGENT] Calling NVIDIA API...", flush=True)
    headers = {
        "Authorization": "Bearer " + NVIDIA_API_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "model": "deepseek-ai/deepseek-v4-pro",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 800,
        "temperature": 0.3
    }
    try:
        r = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers=headers,
            json=body,
            timeout=120
        )
       if r.status_code == 429:
            print("[AGENT] Rate limited — waiting 60 seconds...", flush=True)
            time.sleep(60)
            return None
        if r.status_code != 200:
            print("[AGENT] NVIDIA error: " + str(r.text), flush=True)
            return None
        full = r.json()["choices"][0]["message"]["content"]
        code = clean_code(full)
        if code is None:
            print("[AGENT] No valid function found", flush=True)
            return None
        print("[AGENT] Strategy ready", flush=True)
        return code
    except Exception as e:
        print("[AGENT] NVIDIA failed: " + str(e), flush=True)
        return None


def search_strategy(all_data, market_summary, coins):
    global active_strategy, active_good_coins
    strategy_code = None
    failed_tests = []
    attempts = 0
    while attempts < 5:
        attempts += 1
        print("[SEARCH] Attempt " + str(attempts) + " for: " + str(coins), flush=True)
        if attempts == 1 or strategy_code is None:
            prompt = build_prompt(market_summary, coins)
        else:
            prompt = build_fix_prompt(market_summary, strategy_code, failed_tests, coins)
        strategy_code = call_nvidia(prompt)
        if strategy_code is None:
            time.sleep(30)
            continue
        subset_data = {c: all_data[c] for c in coins if c in all_data}
        results = run_backtest(strategy_code, subset_data)
        is_strategy_good(results)
        failed_tests = []
        still_pending = []
        for coin, score in results.items():
            if score["passed"]:
                with lock:
                    if coin not in active_good_coins:
                        active_good_coins.append(coin)
                        active_strategy = strategy_code
                        save_strategy(strategy_code, active_good_coins)
                        print("[SEARCH] " + coin + " added to active trading", flush=True)
            else:
                still_pending.append(coin)
                if score["win_rate"] < 55.0:
                    failed_tests.append({
                        "coin": coin,
                        "test": "win_rate",
                        "value": str(score["win_rate"]) + "%",
                        "required": "above 55%"
                    })
                if score["max_drawdown"] > 20.0:
                    failed_tests.append({
                        "coin": coin,
                        "test": "drawdown",
                        "value": str(score["max_drawdown"]) + "%",
                        "required": "below 20%"
                    })
                if score["sharpe"] < 0.5:
                    failed_tests.append({
                        "coin": coin,
                        "test": "sharpe",
                        "value": str(score["sharpe"]),
                        "required": "above 0.5"
                    })
        coins = still_pending
        if not coins:
            print("[SEARCH] All coins approved", flush=True)
            break
        time.sleep(60)
    print("[SEARCH] Done. Active: " + str(active_good_coins), flush=True)


def revalidate(all_data, market_summary):
    global active_strategy, active_good_coins, trade_count, revalidate_every
    print("[REVALIDATE] Running backtest on current strategy...", flush=True)
    with lock:
        strat = active_strategy
        coins = list(active_good_coins)
    if not strat or not coins:
        print("[REVALIDATE] No active strategy to validate", flush=True)
        return
    subset_data = {c: all_data[c] for c in coins if c in all_data}
    results = run_backtest(strat, subset_data)
    still_good = is_strategy_good(results)
    failed_coins = [c for c in coins if c not in still_good]
    if failed_coins:
        print("[REVALIDATE] " + str(failed_coins) + " failed — searching new strategy", flush=True)
        with lock:
            for c in failed_coins:
                if c in active_good_coins:
                    active_good_coins.remove(c)
            save_strategy(active_strategy, active_good_coins)
        threading.Thread(
            target=search_strategy,
            args=(all_data, market_summary, failed_coins),
            daemon=True
        ).start()
    else:
        print("[REVALIDATE] All coins still passing — keeping strategy", flush=True)
    trade_count = 0
    revalidate_every = random.randint(10, 20)
    print("[REVALIDATE] Next check in " + str(revalidate_every) + " trades", flush=True)


def trading_loop(all_data, market_summary):
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
                print("[TRADER] Trade count: " + str(trade_count) + " next revalidation at: " + str(revalidate_every), flush=True)
                if trade_count >= revalidate_every:
                    print("[TRADER] Triggering revalidation after " + str(trade_count) + " trades", flush=True)
                    revalidate(all_data, market_summary)
            else:
                print("[TRADER] Waiting for approved coins...", flush=True)
            time.sleep(3600)
        except Exception as e:
            print("[TRADER] Error: " + str(e), flush=True)
            time.sleep(300)


def run_agent():
    global active_strategy, active_good_coins
    if not NVIDIA_API_KEY:
        print("[ERROR] NVIDIA_API_KEY missing", flush=True)
        sys.exit(1)
    if not os.environ.get("COINDCX_API_KEY"):
        print("[ERROR] COINDCX_API_KEY missing", flush=True)
        sys.exit(1)
    if not os.environ.get("COINDCX_SECRET"):
        print("[ERROR] COINDCX_SECRET missing", flush=True)
        sys.exit(1)
    print("[AGENT] All keys found", flush=True)
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
            market_summary = get_market_summary(all_data)
            saved_code, saved_coins = load_strategy()
            if saved_code and saved_coins:
                with lock:
                    active_strategy = saved_code
                    active_good_coins = saved_coins
                print("[AGENT] Resuming saved strategy for: " + str(saved_coins), flush=True)
                remaining = [c for c in ["BTC", "ETH", "BNB", "SOL", "XRP"] if c not in saved_coins]
                if remaining:
                    print("[AGENT] Searching strategy for remaining: " + str(remaining), flush=True)
                    search_thread = threading.Thread(
                        target=search_strategy,
                        args=(all_data, market_summary, remaining),
                        daemon=True
                    )
                    search_thread.start()
            else:
                bump_strategy_version()
                active_good_coins = []
                active_strategy = None
                search_thread = threading.Thread(
                    target=search_strategy,
                    args=(all_data, market_summary, ["BTC", "ETH", "BNB", "SOL", "XRP"]),
                    daemon=True
                )
                search_thread.start()
            trade_thread = threading.Thread(
                target=trading_loop,
                args=(all_data, market_summary),
                daemon=True
            )
            trade_thread.start()
            if "search_thread" in dir():
                search_thread.join()
            print("[AGENT] Search done. Sleeping 1 hour", flush=True)
            time.sleep(3600)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("[AGENT] Error: " + str(e), flush=True)
            time.sleep(900)


if __name__ == "__main__":
    run_agent()
