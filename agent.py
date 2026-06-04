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


def build_prompt(market_summary, feedback=None):
    lines = []
    lines.append("You are an expert quantitative trading strategy developer for cryptocurrency markets.")
    lines.append("")
    lines.append("Current market data:")
    lines.append(market_summary)
    lines.append("")
    lines.append("Create a quantitative trading strategy for BTC, ETH, SOL, BNB, and XRP.")
    lines.append("")
    lines.append("Strategy Requirements:")
    lines.append("- Asset Focus: BTC, ETH, SOL, BNB, XRP on 1-hour timeframe")
    lines.append("- Use quantitative technical indicators like EMA, RSI, MACD, Bollinger Bands, Volume")
    lines.append("- Risk Management:")
    lines.append("  - Take Profit: entry_price * 1.06 (6% take profit)")
    lines.append("  - Stop Loss: entry_price * 0.97 (3% stop loss)")
    lines.append("- Position Sizing: fixed percentage of capital per trade")
    lines.append("")
    lines.append("Entry Conditions (Long/Buy):")
    lines.append("- Define at least 2 confluence conditions using technical indicators")
    lines.append("- Example: EMA crossover AND RSI oversold AND volume confirmation")
    lines.append("")
    lines.append("Exit Conditions (Sell):")
    lines.append("- Take profit at 6% above entry")
    lines.append("- Stop loss at 3% below entry")
    lines.append("- Technical exit signal as additional condition")
    lines.append("")
    if feedback:
        lines.append("IMPORTANT - Previous strategy failed these tests:")
        for f in feedback:
            lines.append("- Coin: " + f["coin"] + " Failed: " + f["test"] + " Got: " + f["value"])
        lines.append("Fix ONLY these specific weaknesses in the new strategy.")
        lines.append("Keep everything else the same.")
        lines.append("")
    lines.append("Write a Python function get_signals(df).")
    lines.append("df has columns: open, high, low, close, volume.")
    lines.append("Return pandas Series: 1=buy, -1=sell, 0=hold.")
    lines.append("Use only pandas and numpy. No external libraries.")
    lines.append("Return ONLY the raw Python function code. No explanation. No markdown.")
    return "\n".join(lines)


def call_nvidia(prompt):
    print("[AGENT] Calling NVIDIA API...", flush=True)
    headers = {
        "Authorization": "Bearer " + NVIDIA_API_KEY,
        "Content-Type": "application/json"
    }
    body = {
       "model": "deepseek-ai/deepseek-r1", ,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 800,
        "temperature": 0.5
    }
    try:
        r = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers=headers,
            json=body,
            timeout=120
        )
        if r.status_code != 200:
            print("[AGENT] NVIDIA error: " + str(r.text), flush=True)
            return None
        code = r.json()["choices"][0]["message"]["content"]
        code = code.replace("```python", "").replace("```", "").strip()
        print("[AGENT] Strategy ready", flush=True)
        return code
    except Exception as e:
        print("[AGENT] NVIDIA call failed: " + str(e), flush=True)
        return None


def build_fix_prompt(market_summary, strategy_code, failed_tests):
    lines = []
    lines.append("You are an expert quantitative trading strategy developer.")
    lines.append("")
    lines.append("Here is a trading strategy that partially works:")
    lines.append("")
    lines.append(strategy_code)
    lines.append("")
    lines.append("These coins PASSED all tests and are fine - do not change logic for them.")
    lines.append("")
    lines.append("These coins FAILED specific tests - fix ONLY these weaknesses:")
    for f in failed_tests:
        lines.append("- Coin: " + f["coin"] + " | Failed: " + f["test"] + " | Got: " + f["value"] + " | Required: " + f["required"])
    lines.append("")
    lines.append("Fix instructions:")
    lines.append("- If win_rate too low: tighten entry conditions, add more confluence filters")
    lines.append("- If drawdown too high: the stop loss is enforced externally at 3%, check entry timing")
    lines.append("- If sharpe too low: reduce trade frequency, only take highest quality signals")
    lines.append("")
    lines.append("Return the COMPLETE updated get_signals(df) function.")
    lines.append("Use only pandas and numpy. No external libraries.")
    lines.append("Return ONLY the raw Python function code. No explanation. No markdown.")
    return "\n".join(lines)


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

                    if attempts == 1 or strategy_code is None:
                        prompt = build_prompt(market_summary)
                        strategy_code = call_nvidia(prompt)
                    else:
                        fix_prompt = build_fix_prompt(market_summary, strategy_code, failed_tests)
                        strategy_code = call_nvidia(fix_prompt)

                    if strategy_code is None:
                        print("[AGENT] Generation failed, retrying...", flush=True)
                        time.sleep(10)
                        continue

                    results = run_backtest(strategy_code, all_data)
                    good_coins = is_strategy_good(results)

                    failed_tests = []
                    for coin, score in results.items():
                        if not score["passed"]:
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

                    if not good_coins and failed_tests:
                        print("[AGENT] Failed tests: " + str(len(failed_tests)) + " issues found", flush=True)
                        for f in failed_tests:
                            print("[AGENT] " + f["coin"] + " failed " + f["test"] + " got " + f["value"], flush=True)

                if not good_coins:
                    print("[AGENT] No good strategy after 5 attempts, waiting 1 hour", flush=True)
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
