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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
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
    p += "The function MUST start with these two lines:\n"
    p += "import pandas as pd\n"
    p += "import numpy as np\n"
    p += "Use ONE of these proven quant math approaches:\n"
    p += "1. Z-Score mean reversion: zscore = (price - rolling_mean) / rolling_std, buy when zscore < -1.5, sell when zscore > 1.5\n"
    p += "2. Volatility breakout: ATR-based entry when price breaks above upper band with volume confirmation\n"
    p += "3. Momentum z-score: standardized returns momentum with rolling 20 period window\n"
    p += "4. Ornstein-Uhlenbeck: estimate mean reversion speed, trade when price deviates more than 1.5 sigma\n"
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


def call_ai(prompt):
    print("[AGENT] Calling AI API...", flush=True)
    if GEMINI_API_KEY:
        try:
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY
            body = {"contents": [{"parts": [{"text": prompt}]}]}
            r = requests.post(url, json=body, timeout=60)
            if r.status_code == 200:
                full = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                print("[AGENT] Gemini raw: " + full[:150], flush=True)
                code = clean_code(full)
                if code:
                    print("[AGENT] Strategy ready via Gemini", flush=True)
                    return code
                print("[AGENT] Gemini returned no valid function", flush=True)
            else:
                print("[AGENT] Gemini error: " + str(r.status_code) + " " + r.text[:100], flush=True)
        except Exception as e:
            print("[AGENT] Gemini failed: " + str(e), flush=True)
    if NVIDIA_API_KEY:
        try:
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
            r = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers=headers,
                json=body,
                timeout=120
            )
            if r.status_code == 429:
                print("[AGENT] NVIDIA rate limited waiting 60 seconds...", flush=True)
                time.sleep(60)
                return None
            if r.status_code == 200:
                full = r.json()["choices"][0]["message"]["content"]
                code = clean_code(full)
                if code:
                    print("[AGENT] Strategy ready via NVIDIA", flush=True)
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
        strategy_code = call_ai(prompt)
        if strategy_code is None:
            time.sleep(60)
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
        print("[REVALIDATE] " + str(failed_coins) + " failed searching new strategy", flush=True)
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
        print("[REVALIDATE] All coins still passing keeping strategy", flush=True)
    trade_count = 0
    revalidate_every = random.randint(10, 20)
    print("[REVALIDATE] Next check in " + str(revalidate_every) + " trades", flush=True)


def trading_loop(all_data, market_summary):
    global trade_count
    while True:
        try:
            with lock:
                strat = active_strategy
                coins
