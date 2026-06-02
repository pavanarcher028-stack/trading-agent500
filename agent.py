import time
import os
import anthropic
from data import get_top5_ohlcv, get_market_summary
from backtest import run_backtest, is_strategy_good
from trader import execute_strategy
from monitor import needs_regeneration, bump_strategy_version, get_performance_summary

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

strategy_code = None
entry_prices = {}

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
- Has more buy signals than sell signals

Rules:
- Use only pandas and numpy (already imported)
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

    print("Asking AI to generate strategy...")
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    code = response.content[0].text.strip()
    code = code.replace("```python", "").replace("```", "").strip()
    print("Strategy generated successfully")
    return code

def run_agent():
    global strategy_code, entry_prices

    print("=" * 50)
    print("TRADING AGENT STARTED")
    print("=" * 50)

    loop_count = 0
    feedback = None

    while True:
        try:
            loop_count += 1
            print(f"\n--- Loop {loop_count} ---")

            # step 1: fetch live market data
            print("Fetching market data...")
            all_data = get_top5_ohlcv()
            if not all_data:
                print("No data fetched — retrying in 10 mins")
                time.sleep(600)
                continue

            market_summary = get_market_summary(all_data)
            print(market_summary)

            # step 2: generate strategy if none exists or needs regeneration
            if strategy_code is None or needs_regeneration():
                bump_strategy_version()
                attempts = 0
                good_coins = []

                while len(good_coins) == 0 and attempts < 5:
                    attempts += 1
                    print(f"\nStrategy generation attempt {attempts}/5")
                    strategy_code = generate_strategy(market_summary, feedback)

                    # step 3: backtest the strategy
                    print("Backtesting strategy...")
                    results = run_backtest(strategy_code, all_data)
                    good_coins = is_strategy_good(results)

                    if not good_coins:
                        feedback = "Win rate below 65% or Sharpe below 2.0 or drawdown above 15%"
                        print("Strategy failed backtest — trying again")

                if not good_coins:
                    print("Could not find good strategy after 5 attempts — waiting 1 hour")
                    time.sleep(3600)
                    continue

                print(f"\nApproved coins: {good_coins}")

            else:
                # re-backtest existing strategy on fresh data
                results = run_backtest(strategy_code, all_data)
                good_coins = is_strategy_good(results)

            # step 4: execute trades
            print("\nExecuting trades...")
            trade_results = execute_strategy(strategy_code, all_data, good_coins)

            # step 5: print performance
            print("\nPerformance summary:")
            get_performance_summary()

            # wait 1 hour before next loop
            print("\nSleeping for 1 hour...")
            time.sleep(3600)

        except KeyboardInterrupt:
            print("\nAgent stopped manually")
            break

        except Exception as e:
            print(f"Unexpected error: {e}")
            print("Retrying in 15 minutes...")
            time.sleep(900)

if __name__ == "__main__":
    run_agent()
