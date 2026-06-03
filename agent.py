import sys
import os
import time
import requests
from data import get_top5_ohlcv, get_market_summary
from backtest import run_backtest, is_strategy_good
from trader import execute_strategy
from monitor import needs_regeneration, bump_strategy_version, get_performance_summary

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")

print("TRADING AGENT STARTED", flush=True)


def build_prompt(market_summary, feedback):
    lines = []
    lines.append("You are an expert quant trader building strict risk-managed strategies.")
    lines.append("Market data:")
    lines.append(market_summary)
    if feedback:
        lines.append("Previous failed: " + feedback + " Try different approach.")
    lines.append("Write a Python function get_signals(df).")
    lines.append("df has columns: open, high, low, close, volume.")
    lines.append("Return pandas Series: 1=buy, -1=sell, 0=hold.")
    lines.append("Use only pandas and numpy. No external libraries.")
    lines.append("STRICT RULES:")
    lines.append("1. Only buy when RSI is below 35 AND price is above 200 EMA.")
    lines.append("2. Sell if price drops 3 percent below entry price (stop loss).")
    lines.append("3. Sell when RSI goes above 65 (take profit).")
    lines.append("4. Never hold more than 20 candles (time stop).")
    lines.append("5. Only buy after 3 consecutive green candles confirm trend.")
    lines.append("These rules keep drawdown below 15 percent.")
    lines.append("Return ONLY the raw function code, no explanation, no markdown.")
    return "\n".join(lines)


def generate_strategy(market_summary, feedback=None):
    prompt = build_prompt(market_summary, feedback)
    print("[AGENT] Calling NVIDIA API...", flush=True)
    headers = {
        "Authorization": "Bearer " + NVIDIA_API_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "model": "meta/llama-3.3-70b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000,
        "temperature": 0.7
    }
    r = requests.post(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        headers=headers,
        json=body,
        timeout=60
    )
   if r.status_code != 1000:
        print("[AGENT] NVIDIA error: " + str(r.text), flush=True)
        return None
    result = r.json()
    code = result["choices"][0]["message"]["content"]
    code = code.replace("```python", "").replace("```", "").strip()
    print("[AGENT] Strategy ready", flush=True)
    return code


def run_agent():
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
    strategy_code = None
    feedback = None
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
            if strategy_code is None or needs_regeneration():
                bump_strategy_version()
                good_coins = []
                attempts = 0
                while not good_coins and attempts < 5:
                    attempts += 1
                    print("[AGENT] Attempt " + str(attempts), flush=True)
                 strategy_code = generate_strategy(market_summary, feedback)
                    if strategy_code is None:
                        print("[AGENT] Strategy generation failed, retrying...", flush=True)
                        continue
                    results = run_backtest(strategy_code, all_data)
                    good_coins = is_strategy_good(results)
                    if not good_coins:
                        feedback = "drawdown too high, win rate too low, sharpe too low"
                if not good_coins:
                    print("[AGENT] No good strategy, waiting 1 hour", flush=True)
                    time.sleep(3600)
                    continue
            else:
                results = run_backtest(strategy_code, all_data)
                good_coins = is_strategy_good(results)
            print("[AGENT] Trading: " + str(good_coins), flush=True)
            execute_strategy(strategy_code, all_data, good_coins)
            get_performance_summary()
            print("[AGENT] Sleeping 1 hour", flush=True)
            time.sleep(3600)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("[AGENT] Error: " + str(e), flush=True)
            time.sleep(900)


if __name__ == "__main__":
    run_agent()
