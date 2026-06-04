import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np
import requests
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
    """Log failed metrics to file for tracking"""
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
        
        print("[METRICS] Logged failures for " + coin + ": " + str(failed_metrics), flush=True)
    except Exception as e:
        print("[METRICS] Logging failed: " + str(e), flush=True)


def run_backtest(strategy_code, all_data):
    usd_to_inr = get_live_rate()
    results = {}
    for coin, df in all_data.items():
        try:
            local_env = {}
            exec(strategy_code, local_env)
            get_signals = local_env["get_signals"]
            raw = get_signals(df.copy())
            if isinstance(raw, pd.DataFrame):
                raw = raw.iloc[:, 0]
            raw = pd.Series(raw).reset_index(drop=True)
            signals = pd.to_numeric(raw, errors="coerce").fillna(0)
            close = df["close"].reset_index(drop=True)
            capital = 10000.0
            position = 0.0
            buy_price = 0.0
            hold_count = 0
            trades = []
            equity = [capital]
            for i in range(1, len(signals)):
                price = float(close.iat[i])
                try:
                    val = float(signals.iat[i])
                except:
                    val = 0.0
                if val > 0:
                    sig = 1
                elif val < 0:
                    sig = -1
                else:
                    sig = 0
                if sig == 1 and position == 0.0:
                    position = capital / price
                    buy_price = price
                    hold_count = 0
                elif position > 0.0:
                    hold_count += 1
                    pct = (price - buy_price) / buy_price * 100.0
                    if pct <= -3.0 or pct >= 6.0 or hold_count >= 48 or sig == -1:
                        new_capital = position * price
                        profit = new_capital - capital
                        trades.append(profit)
                        capital = new_capital
                        position = 0.0
                        buy_price = 0.0
                        hold_count = 0
                if position > 0.0:
                    current = position * price
                else:
                    current = capital
                equity.append(current)
            equity = np.array(equity)
            peak = np.maximum.accumulate(equity)
            drawdowns = (peak - equity) / peak * 100.0
            max_drawdown = round(float(np.max(drawdowns)), 2)
            if len(trades) == 0:
                failed_metrics = ["sharpe", "win_rate", "trades_count"]
                log_metric_failure(coin, failed_metrics)
                results[coin] = {
                    "sharpe": 0,
                    "win_rate": 0,
                    "max_drawdown": max_drawdown,
                    "trades": 0,
                    "passed": False,
                    "failed_metrics": failed_metrics
                }
                continue
            trades_arr = np.array(trades)
            wins = int(np.sum(trades_arr > 0))
            win_rate = round(wins / len(trades_arr) * 100.0, 1)
            avg = float(np.mean(trades_arr))
            std = float(np.std(trades_arr))
            sharpe = round(avg / std if std > 0 else 0.0, 2)
            
            # Check individual metrics
            passed = sharpe >= 0.5 and win_rate >= 55.0 and max_drawdown <= 20.0 and len(trades) >= 5
            
            # Track which metrics failed
            failed_metrics = []
            if sharpe < 0.5:
                failed_metrics.append("sharpe")
            if win_rate < 55.0:
                failed_metrics.append("win_rate")
            if max_drawdown > 20.0:
                failed_metrics.append("max_drawdown")
            if len(trades) < 5:
                failed_metrics.append("trades_count")
            
            if failed_metrics:
                log_metric_failure(coin, failed_metrics)
            
            results[coin] = {
                "sharpe": sharpe,
                "win_rate": win_rate,
                "max_drawdown": max_drawdown,
                "trades": len(trades),
                "passed": passed,
                "failed_metrics": failed_metrics if not passed else []
            }
            
            status = "PASS" if passed else "FAIL"
            price_inr = round(float(df["close"].iloc[-1]) * usd_to_inr, 2)
            print(coin + " [" + status + "] Sharpe: " + str(sharpe) + " Win: " + str(win_rate) + "% DD: " + str(max_drawdown) + "% Trades: " + str(len(trades)) + " Price: Rs." + str(price_inr), flush=True)
            
            if not passed and failed_metrics:
                print(coin + " FAILED - Improve: " + ", ".join(failed_metrics), flush=True)
                
        except Exception as e:
            print("Backtest failed for " + coin + ": " + str(e), flush=True)
            failed_metrics = ["execution_error"]
            log_metric_failure(coin, failed_metrics)
            results[coin] = {
                "sharpe": 0,
                "win_rate": 0,
                "max_drawdown": 100,
                "trades": 0,
                "passed": False,
                "failed_metrics": failed_metrics
            }
    return results


def is_strategy_good(results):
    good_coins = []
    partial_fails = []
    
    for coin, score in results.items():
        if score["passed"]:
            good_coins.append(coin)
            print(coin + " approved for live trading", flush=True)
        else:
            # Check if partially passed (2+ metrics passed, some failed)
            failed_count = len(score.get("failed_metrics", []))
            total_metrics = 4
            passed_count = total_metrics - failed_count
            
            if passed_count >= 2 and failed_count > 0 and "execution_error" not in score.get("failed_metrics", []):
                partial_fails.append({
                    "coin": coin,
                    "passed_count": passed_count,
                    "failed_metrics": score.get("failed_metrics", []),
                    "sharpe": score["sharpe"],
                    "win_rate": score["win_rate"],
                    "max_drawdown": score["max_drawdown"],
                    "trades": score["trades"]
                })
    
    if partial_fails:
        print("\n[AI FEEDBACK] Coins with partial passes - need improvement:", flush=True)
        for item in partial_fails:
            print("[AI] " + item['coin'] + ": " + str(item['passed_count']) + "/4 metrics passed", flush=True)
            print("[AI] Current - Sharpe: " + str(item['sharpe']) + ", Win Rate: " + str(item['win_rate']) + "%, DD: " + str(item['max_drawdown']) + "%, Trades: " + str(item['trades']), flush=True)
            print("[AI] Fix these: " + ", ".join(item['failed_metrics']), flush=True)
    
    if not good_coins:
        print("No coins passed", flush=True)
    
    return good_coins, partial_fails


def get_metric_statistics():
    """Get failure statistics for tracking"""
    try:
        log_file = "metric_failures.json"
        if not os.path.exists(log_file):
            return None
        
        with open(log_file, "r") as f:
            logs = json.load(f)
        
        print("\n[METRICS STATISTICS]", flush=True)
        for coin, data in logs.items():
            print(coin + ": " + str(data["total_attempts"]) + " attempts, Failures: " + str(data["failures"]), flush=True)
        
        return logs
    except Exception as e:
        print("[METRICS] Failed to read statistics: " + str(e), flush=True)
        return None
