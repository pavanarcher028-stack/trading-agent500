import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np
import requests
import re
import json
import os


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
                print("[BACKTEST] No SL/TP from AI - strategy manages own exits", flush=True)
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
                    if pct <= sl_pct or pct >= tp_pct or hold_count >= 48 or sig == -1:
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
            passed = sharpe >= 0.5 and win_rate >= 55.0 and max_drawdown <= 15.0 and len(trades) >= 5
            failed_metrics = []
            if sharpe < 0.5:
                failed_metrics.append("sharpe")
            if win_rate < 55.0:
                failed_metrics.append("win_rate")
            if max_drawdown > 15.0:
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
            log_metric_failure(coin,
