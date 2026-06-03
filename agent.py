import sys
import os
import time
import requests
from data import get_top5_ohlcv, get_market_summary
from backtest import run_backtest, is_strategy_good
from trader import execute_strategy
from monitor import needs_regeneration, bump_strategy_version, get_performance_summary

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")

print("==================================================", flush=True)
print("TRADING AGENT STARTED", flush=True)
print("==================================================", flush=True)

def generate_strategy(market_summary, previous_feedback=None):
    if previous_feedback:
        feedback_text = "Previous strategy failed: " + previous_feedback + " Make a different approach."
    else:
        feedback_text = ""

    prompt = (
        "You are an expert algorithmic trading strategy developer.\n\n"
        "Current market data:\n"
        + market_summary + "\n"
        + feedback_text + "\n\n"
        "Write a Python function called get_signals(df) that:\n"
        "- Takes a pandas DataFrame with columns: open, high, low, close, volume\n"
        "- Returns a pandas Series of signals: 1 = buy, -1 = sell, 0 = hold\n"
        "- Uses technical indicators like EMA, RSI, Bollinger Bands\n"
        "- Is conservative, only signals when very confident\n"
        "- Uses only pandas and numpy\n"
        "- Returns ONLY the raw Python function, no explanation, no markdown\n\n"
        "Example:\n"
        "def get_signals(df):\n"
        "    import pandas as pd\n"
        "    import numpy as np\n"
        "    signals = pd.Series(0, index=df.index)\n"
        "    return signals\n"
    )

    print("[AGENT] Calling NVIDIA API...", flush=True)

    headers = {
        "Authorization": "Bearer " + NVIDIA_API_KEY,
        "Content-Type": "application/json"
    }

    body = {
        "model": "meta/llama-3.3-70b-instruct",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1000,
        "temperature": 0.7
    }

    response = requests.post(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        headers=h
