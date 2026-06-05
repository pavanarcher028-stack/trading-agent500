import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np
import requests
import re
import json
import os
from datetime import datetime


def get_live_rate():
    try:
        r = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=10)
        rate = float(r.json()["rates"]["INR"])
        print("[BACKTEST] Live USD/INR: " + str(rate), flush=True)
        return rate
    except:
        return 84.0


def log_metric_failure(coin, failed_metrics):
    try:
        log_file = "metric_failures.json"
        logs = {}
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                logs = json.load(f)
        if coin not in logs:
            logs[coin] = {"failures": {}, "total_attempts": 0}
        logs[coin]["total_attempts"] += 1
        for metric in failed_metrics:
            if metric not in logs[coin]["failures"]:
                logs[coin]["failures"][metric] = 0
            logs[coin]["failures"][metric] += 1
        with open(log_file, "w") as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print("[METRICS] Logging failed: " + str(e), flush=True)


def run_backtest(strategy_code, all_data):
    usd_to_inr = get_live_rate()
    results = {}
    for coin, df in all_data.items():
        try:
            sl_pct = -100.0
            tp_pct = 1000.0
            sl_match = re.search(r'SL_PCT\s*=\s*([\d.]+)', strategy_code)
            tp_match = re.search(r'TP_PCT\s*=\s*([\d.]+)', strategy_code)
            if sl_match:
                sl_pct = -float(sl_match.group(1))
            if tp_match:
                tp_pct = float(tp_match.group(1))
            if sl_match or tp_match:
                print("[BACKTEST] AI defined SL=" + str(sl_pct) + "% TP=" + str(tp_pct) + "%", flush=True)
            else:
                print("[BACKTEST] No SL/TP defined by AI — strate
