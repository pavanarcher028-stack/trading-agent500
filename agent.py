import sys
import os
import time
import anthropic

print("=" * 50, flush=True)
print("TRADING AGENT STARTING", flush=True)
print("=" * 50, flush=True)

from data import get_top5_ohlcv, get_market_summary
from backtest import run_backtest, is_strategy_good
from trader import execute_strategy
from monitor import needs_regeneration, bump_strategy_version, get_performance_summary

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

strategy_code = None
feedback = None

def generate_strategy(market_summary, previous_feedback=None):
    feedback_text = ""
    if previous_feedback:
        feedback_text = f"\nPrevious strategy failed because: {previous_feedback}\nMake a completely different approach."

    prompt = f"""
You are an expert algorithmic trading strategy developer.

Current market data:
{market_summary}
{feedback_text}

Write a Python function called get_signals(df) that:
- Takes a pandas DataFrame with columns: open, high, low, close, volume
- Returns a pandas Series of signals: 1 = buy, -1 = sell, 0 = hold
- Uses technical indicators like EMA, RSI, or momentum
- Is conservative — only signals when very confident

Rules:
- Use only pandas and numpy
- No external libraries
- Return ONLY the raw Python function, no explanation, no markdown

Example structure:
def get_signals(df):
    import pandas as pd
    import numpy as np
    signals = pd.Series(0, index=df.index)
    # your logic here
    return signals
"""

    print("[AGENT] Calling Claude API...", flush=True)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    code = response.content[0].text.strip()
    code = code.replace("```python", "").replace("```", "").strip()
    print("[AGENT] Strategy generated successfully", flush=True)
    return code

def run_agent():
    global strategy_code, feedback

    print("[AGENT] Checking environment variables...", flush=True)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[ERROR] ANTHROPIC_API_KEY is missing!", flush=True)
        sys.exit(1)

    if not os.environ.get("COINDCX_API_KEY"):
        print("[ERROR] COINDCX_API_KEY is missing!", flush=True)
        sys.exit(1)

    if not os.environ.get("COINDCX_SECRET"):
        print("[ERROR] COINDCX_SECRET is missing!", flush=True)
        sys.exit(1)

    print("[AGENT] All environment variables found", flush=True)

    loop_count = 0

    while True:
        try:
            loop_count += 1
            print(f"\n[AGENT] ===== Loop {loop_count} =====", flush=True)

            # step 1: fetch data
            print("[AGENT] Step 1 — Fetching market data", flush=True)
            all_data = get_top5_ohlcv()

            if not all_data:
                print("[AGENT] No data received — retrying in 10 mins", flush=True)
                time.sleep(600)
                continue

            print(f"[AGENT] Got data for {len(all_data)} coins", flush=True)
            market_summary = get_market_summary(all_data)

            # step 2: generate strategy
            print("[AGENT] Step 2 — Generating strategy", flush=True)
            good_coins = []
            attempts = 0

            if strategy_code is None or needs_regeneration():
                bump_strategy_version()

                while len(good_coins) == 0 and attempts < 5:
                    attempts += 1
                    print(f"[AGENT] Strategy attempt {attempts}/5", flush=True)
                    strategy_code = generate_strategy(market_summary, feedback)

                    # step 3: backtest
                    print("[AGENT] Step 3 — Backtesting", flush=True)
                    results = run_backtest(strategy_code, all_data)
                    good_coins = is_strategy_good(results)

                    if not good_coins:
                        feedback = "win rate below 65%, sharpe below 2.0, or drawdown above 15%"
                        print("[AGENT] Strategy failed — trying again", flush=True)

                if not good_coins:
                    print("[AGENT] No good strategy found — waiting 1 hour", flush=True)
                    time.sleep(3600)
                    continue
            else:
                results = run_backtest(strategy_code, all_data)
                good_coins = is_strategy_good(results)

            print(f"[AGENT] Approved coins: {good_coins}", flush=True)

            # step 4: trade
            print("[AGENT] Step 4 — Executing trades", flush=True)
            execute_strategy(strategy_code, all_data, good_coins)

            # step 5: monitor
            print("[AGENT] Step 5 — Performance summary", flush=True)
            get_performance_summary()

            print("[AGENT] Sleeping 1 hour...", flush=True)
            time.sleep(3600)

        except KeyboardInterrupt:
            print("[AGENT] Stopped manually", flush=True)
            break

        except Exception as e:
            print(f"[AGENT] Unexpected error: {e}", flush=True)
            print("[AGENT] Retrying in 15 minutes...", flush=True)
            time.sleep(900)

if __name__ == "__main__":
    run_agent()
