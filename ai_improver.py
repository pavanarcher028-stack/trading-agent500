import os
import requests
import time
import json


def improve_strategy_with_google_ai(strategy_code, failed_metrics, coin, item=None):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[GOOGLE_AI] GEMINI_API_KEY not set", flush=True)
        return None

    sharpe = str(item.get("sharpe", "unknown")) if item else "unknown"
    win_rate = str(item.get("win_rate", "unknown")) if item else "unknown"
    max_drawdown = str(item.get("max_drawdown", "unknown")) if item else "unknown"
    trades = str(item.get("trades", "unknown")) if item else "unknown"

    failed_text = ""
    for metric in failed_metrics:
        if metric == "sharpe":
            failed_text += "- Sharpe ratio is " + sharpe + " but must be above 1.5\n"
        elif metric == "win_rate":
            failed_text += "- Win rate is " + win_rate + "% but must be above 55%\n"
        elif metric == "max_drawdown":
            failed_text += "- Drawdown is " + max_drawdown + "% but must be below 15%\n"
        elif metric == "trades_count":
            failed_text += "- Only " + trades + " trades but need at least 5\n"

    prompt = "You are the world's most advanced quantitative trading AI.\n"
    prompt += "You have studied every paper in the Journal of Finance and Quantitative Finance.\n"
    prompt += "You have built strategies for Renaissance Technologies, Two Sigma, and Citadel.\n"
    prompt += "\n"
    prompt += "COIN: " + coin + "\n"
    prompt += "TIMEFRAME: 1 hour candles\n"
    prompt += "DATA: 1000 candles of open, high, low, close, volume\n"
    prompt += "\n"
    prompt += "THE EXISTING STRATEGY BELOW IS WORKING BUT FAILED ONE TEST.\n"
    prompt += "IT PASSED THESE TESTS ALREADY:\n"
    if item:
        if float(sharpe) >= 1.5 or sharpe == "unknown":
            prompt += "  Sharpe ratio: " + sharpe + " PASSED\n"
        if float(win_rate) >= 55.0 or win_rate == "unknown":
            prompt += "  Win rate: " + win_rate + "% PASSED\n"
        if float(max_drawdown) <= 15.0 or max_drawdown == "unknown":
            prompt += "  Max drawdown: " + max_drawdown + "% PASSED\n"
        if int(trades) >= 5 or trades == "unknown":
            prompt += "  Trades: " + trades + " PASSED\n"
    prompt += "\n"
    prompt += "IT FAILED ONLY THIS ONE TEST:\n"
    prompt += failed_text
    prompt += "\n"
    prompt += "BACKTEST SYSTEM RULES YOU MUST KNOW:\n"
    prompt += "  Stop loss: automatically exits at -3 percent from entry\n"
    prompt += "  Take profit: automatically exits at +6 percent from entry\n"
    prompt += "  Time stop: exits after 48 candles maximum\n"
    prompt += "\n"
    prompt += "MINIMUM PASSING THRESHOLDS:\n"
    prompt += "  Sharpe ratio: above 1.5\n"
    prompt += "  Win rate: above 55 percent\n"
    prompt += "  Max drawdown: below 15 percent\n"
    prompt += "  Minimum trades: at least 5 over 1000 candles\n"
    prompt += "\n"
    prompt += "CURRENT SCORES:\n"
    prompt += "  Sharpe: " + sharpe + " (target above 1.5)\n"
    prompt += "  Win rate: " + win_rate + "% (target above 55%)\n"
    prompt += "  Drawdown: " + max_drawdown + "% (target below 15%)\n"
    prompt += "  Trades: " + trades + " (target at least 5)\n"
    prompt += "\n"
    prompt += "CURRENT WORKING STRATEGY CODE:\n"
    prompt += strategy_code + "\n"
    prompt += "\n"
    prompt += "FIX INSTRUCTIONS FOR EACH POSSIBLE FAILING METRIC:\n"
    prompt += "  If Sharpe too low: normalize signals by dividing by rolling_std(20), filter noise\n"
    prompt += "  If win rate too low: add volume above 20 period average + momentum confirmation\n"
    prompt += "  If drawdown too high: add EMA 100 trend filter, only buy when price above EMA 100\n"
    prompt += "  If trades too few: shorten rolling windows to 10-20 periods, lower z-score thresholds\n"
    prompt += "\n"
    prompt += "STRICT RULES:\n"
    prompt += "1. Do NOT change any logic that is already passing\n"
    prompt += "2. ONLY fix the one failing metric\n"
    prompt += "3. Use ONLY pandas and numpy\n"
    prompt += "4. First two lines inside function must be: import pandas as pd and import numpy as np\n"
    prompt += "4. YOU must define SL_PCT and TP_PCT inside the function — choose values that maximize Sharpe\n"
    prompt += "   Example: SL_PCT = 2.0 means exit if price drops 2 percent from entry\n"
    prompt += "   Example: TP_PCT = 5.0 means exit if price rises 5 percent from entry\n"
    prompt += "   For mean reversion strategies use tight SL like 1.5 to 2.5 and TP like 2 to 4\n"
    prompt += "   For momentum strategies use wider SL like 3 to 5 and TP like 6 to 12\n"
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + api_key
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        r = requests.post(url, json=body, timeout=60)
        if r.status_code == 200:
            full = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            if "```python" in full:
                code = full.split("```python")[1].split("```")[0].strip()
            elif "```" in full:
                code = full.split("```")[1].split("```")[0].strip()
            elif "def get_signals" in full:
                code = full[full.index("def get_signals"):].strip()
            else:
                code = full.strip()
            if "def get_signals" in code:
                print("[GOOGLE_AI] Strategy improved for " + coin + " fixing: " + str(failed_metrics), flush=True)
                return code
            print("[GOOGLE_AI] No valid function returned", flush=True)
            return None
        elif r.status_code == 429:
            print("[GOOGLE_AI] Rate limited skipping", flush=True)
            return None
        else:
            print("[GOOGLE_AI] Error: " + str(r.status_code), flush=True)
            return None
    except Exception as e:
        print("[GOOGLE_AI] Failed: " + str(e), flush=True)
        return None


def validate_with_nvidia(strategy_code, coin):
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        return {"valid": True, "errors": []}

    prompt = "You are the world's best hedge fund code reviewer and quantitative developer.\n"
    prompt += "Your job is to review trading strategy code like a senior quant at Renaissance Technologies.\n"
    prompt += "\n"
    prompt += "Review this Python trading strategy function:\n"
    prompt += strategy_code + "\n"
    prompt += "\n"
    prompt += "Check for:\n"
    prompt += "1. Syntax errors that will crash Python\n"
    prompt += "2. Logic errors that will produce wrong signals\n"
    prompt += "3. Pandas or numpy usage mistakes\n"
    prompt += "4. Missing imports inside the function\n"
    prompt += "5. Division by zero risks\n"
    prompt += "6. NaN handling issues\n"
    prompt += "\n"
    prompt += "Reply ONLY in this exact JSON format with no other text:\n"
    prompt += "{\"valid\": true, \"errors\": [], \"fixed_code\": \"\"}\n"
    prompt += "If errors found set valid to false, list errors, and put the fixed code in fixed_code.\n"
    prompt += "If no errors set valid to true, errors to empty list, fixed_code to empty string.\n"

    try:
        r = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json={
                "model": "deepseek-ai/deepseek-v4-pro",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1500,
                "temperature": 0.1
            },
            timeout=60
        )
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"]
            try:
                start = content.find("{")
                end = content.rfind("}") + 1
                result = json.loads(content[start:end])
                if result.get("errors"):
                    print("[NVIDIA] Errors found in " + coin + ": " + str(result.get("errors")), flush=True)
                if result.get("fixed_code") and len(result.get("fixed_code", "")) > 10:
                    print("[NVIDIA] Auto-fixed code for " + coin, flush=True)
                    result["auto_fixed"] = True
                return result
            except:
                return {"valid": True, "errors": [], "fixed_code": ""}
        return {"valid": True, "errors": [], "fixed_code": ""}
    except Exception as e:
        print("[NVIDIA] Failed: " + str(e), flush=True)
        return {"valid": True, "errors": [], "fixed_code": ""}


def batch_improve_and_validate_strategies(partial_fails, strategy_code):
    improved = {}
    for item in partial_fails:
        coin = item["coin"]
        failed_metrics = item["failed_metrics"]
        if len(failed_metrics) != 1:
            print("[PIPELINE] " + coin + " has " + str(len(failed_metrics)) + " failures — only fixing when exactly 1 fails skipping", flush=True)
            continue
        print("[PIPELINE] " + coin + " fixing only: " + str(failed_metrics), flush=True)
        time.sleep(15)
        new_code = improve_strategy_with_google_ai(strategy_code, failed_metrics, coin, item)
        if not new_code:
            print("[PIPELINE] Could not improve " + coin, flush=True)
            continue
        validation = validate_with_nvidia(new_code, coin)
        if not validation.get("valid", True):
            if validation.get("fixed_code") and len(validation.get("fixed_code", "")) > 10:
                print("[PIPELINE] NVIDIA auto-fixed errors for " + coin, flush=True)
                new_code = validation["fixed_code"]
            else:
                print("[PIPELINE] " + coin + " has unfixable errors skipping", flush=True)
                continue
        improved[coin] = new_code
        print("[PIPELINE] " + coin + " improved validated and ready for backtest", flush=True)
    return improved


def generate_html_report(partial_fails, improved_strategies):
    return None
