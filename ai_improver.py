import os
import requests
import time
import json
import re

_seen_strategies = {}


SYSTEM_PROMPT = """You are QUANT-GPT, a quantitative trading AI that generates ONLY strategies proven to pass rigorous backtests.

CRITICAL — Strategies MUST pass ALL of these on 1000 hourly candles:
  Sharpe ≥ 0.5   (use signal /= close.rolling(20).std() to normalize)
  Win rate ≥ 55% (add confluence filters, never trade on a single signal)
  Drawdown ≤ 15% (add EMA 100 trend filter, tighten SL)
  Trades ≥ 5     (use rolling windows ≤ 20, thresholds ≤ 1.0 sigma)

HARD RULES:
- You MUST define SL_PCT and TP_PCT as floats inside get_signals()
- Mean reversion: SL=1.5-2.5, TP=2.0-4.0 | Momentum: SL=3.0-5.0, TP=6.0-12.0
- Time stop exits at 48 candles
- First 2 lines: import pandas as pd and import numpy as np
- Return pd.Series: 1=buy -1=sell 0=hold

PROVEN FORMULAS FOR SHARPE > 0.5:
1. SIGNAL /= close.rolling(20).std()  — this single transform fixes most Sharpe failures
2. Never use raw price differences — always z-score normalize
3. Add a second confirmation condition (volume + trend) to filter bad signals
4. Use .fillna(0) on all intermediate calculations

PROVEN FORMULAS FOR WIN RATE > 55%:
1. Require volume > volume.rolling(20).mean() as a filter
2. Only take trades in direction of 50-period EMA (price > ema for buys)
3. Require 2 independent indicators to agree before signaling

PROVEN FORMULAS FOR DRAWDOWN < 15%:
1. SL_PCT = 1.5-2.0 for mean reversion strategies
2. Add EMA 100 trend filter — never trade against the big trend
3. Exit immediately if signal flips (don't wait for SL/TP)

Return ONLY the complete get_signals(df) function. No markdown. No explanation."""


def build_generation_prompt(market_summary, coins):
    prompt = SYSTEM_PROMPT + "\n\n"
    prompt += "MARKET CONDITIONS:\n"
    prompt += market_summary + "\n\n"
    prompt += "TARGET COINS: " + ", ".join(coins) + "\n"
    prompt += "TIMEFRAME: 1 hour candles\n"
    prompt += "DATA AVAILABLE: open, high, low, close, volume (1000 candles)\n\n"
    prompt += "Your task: Write ONE get_signals(df) function that passes ALL backtest thresholds for these coins.\n\n"
    prompt += "Use this EXACT pattern — it is PROVEN to pass:\n"
    prompt += "def get_signals(df):\n"
    prompt += "    import pandas as pd\n"
    prompt += "    import numpy as np\n"
    prompt += "    SL_PCT = 2.0\n"
    prompt += "    TP_PCT = 4.0\n"
    prompt += "    close = df['close']\n"
    prompt += "    volume = df['volume']\n"
    prompt += "    # === INDICATOR ===\n"
    prompt += "    sma = close.rolling(20).mean()\n"
    prompt += "    std = close.rolling(20).std()\n"
    prompt += "    zscore = (close - sma) / std\n"
    prompt += "    vol_avg = volume.rolling(20).mean()\n"
    prompt += "    ema50 = close.ewm(span=50).mean()\n"
    prompt += "    # === SIGNAL GENERATION ===\n"
    prompt += "    raw = pd.Series(0, index=df.index)\n"
    prompt += "    raw[zscore < -1.5] = 1\n"
    prompt += "    raw[zscore > 1.5] = -1\n"
    prompt += "    # === CONFLUENCE FILTERS (boost win rate) ===\n"
    prompt += "    trend_ok = close > ema50\n"
    prompt += "    vol_ok = volume > vol_avg\n"
    prompt += "    signals = raw * 1\n"
    prompt += "    signals[~(trend_ok & vol_ok)] = 0\n"
    prompt += "    # === NORMALIZE (boost Sharpe) ===\n"
    prompt += "    signals = signals / close.rolling(20).std()\n"
    prompt += "    return signals.fillna(0)\n\n"
    prompt += "CRITICAL THINGS THAT MAKE STRATEGIES FAIL:\n"
    prompt += "- NOT normalizing signals (dividing by rolling std) — this kills Sharpe\n"
    prompt += "- NOT adding volume + trend filters — this kills win rate\n"
    prompt += "- Using windows > 30 periods — this kills trade count\n"
    prompt += "- Using SL > 3% for mean reversion — this kills drawdown\n"
    prompt += "- Not handling NaN with .fillna(0) — this crashes backtest\n\n"
    prompt += "Return ONLY the complete get_signals(df) function. No markdown. No explanation.\n"
    return prompt


def build_improvement_prompt(strategy_code, failed_metrics, coin, item):
    sharpe = item.get("sharpe", "?") if item else "?"
    win_rate = item.get("win_rate", "?") if item else "?"
    max_drawdown = item.get("max_drawdown", "?") if item else "?"
    trades = item.get("trades", "?") if item else "?"

    targets = {
        "sharpe": {"current": sharpe, "need": "0.5", "gap": "", "status": "", "fix": "Normalize signals by rolling volatility (divide signal by close.rolling(20).std()). Also tighten SL_PCT so smaller losses improve consistency."},
        "win_rate": {"current": win_rate, "need": "55%", "gap": "", "status": "", "fix": "Add multi-factor confluence: require volume > 20-period average AND momentum confirmation (close > close.rolling(10).mean()). Add EMA trend filter to avoid counter-trend entries."},
        "max_drawdown": {"current": max_drawdown, "need": "15%", "gap": "", "status": "", "fix": "Add trend filter: only enter when price > EMA 100. Tighten SL_PCT to 1.5 so each loss is smaller."},
        "trades_count": {"current": trades, "need": "5", "gap": "", "status": "", "fix": "Use shorter rolling windows (10-20 periods). Lower z-score thresholds from 1.5 to 1.0 so more signals trigger."}
    }

    try:
        for m, info in targets.items():
            cur = float(info["current"])
            need = float(info["need"].rstrip("%"))
            if m == "max_drawdown":
                passed = cur <= need
                gap = need - cur
                label = f"{cur}% ≤ {need}%"
            else:
                passed = cur >= need
                gap = cur - need
                label = f"{cur} ≥ {need}"
            info["status"] = "PASS" if passed else "FAIL"
            info["gap"] = f"{'+' if gap >= 0 else ''}{gap:.2f}" if isinstance(gap, float) else "?"
    except:
        pass

    prompt = SYSTEM_PROMPT + "\n\n"
    prompt += "=== IMPROVEMENT MISSION ===\n\n"
    prompt += f"Fix the FAILING metrics in this strategy for coin {coin}\n\n"
    prompt += "BACKTEST RESULTS (1000 candles, 1h timeframe):\n"
    prompt += "-" * 50 + "\n"
    prompt += f"  Metric         | Current | Target  | Gap    | Status\n"
    prompt += "-" * 50 + "\n"
    for m, info in targets.items():
        prompt += f"  {m:14s} | {str(info['current']):7s} | {info['need']:7s} | {info['gap']:6s} | {info['status']}\n"
    prompt += "-" * 50 + "\n\n"

    prompt += "PASSING METRICS (do NOT change these):\n"
    had_pass = False
    for m, info in targets.items():
        if info["status"] == "PASS":
            prompt += f"  ✓ {m}: {info['current']} (keep as-is)\n"
            had_pass = True
    if not had_pass:
        prompt += "  (none)\n"

    prompt += "\nFAILING METRICS (FIX ONLY THESE):\n"
    had_fail = False
    for m in failed_metrics:
        if m in targets:
            prompt += f"  ✗ {m}: current={targets[m]['current']}, need ≥ {targets[m]['need']}\n"
            prompt += f"    Recommended fix: {targets[m]['fix']}\n"
            had_fail = True
    if not had_fail:
        prompt += "  (none - but needs more signals or better entries)\n"

    prompt += "\nCURRENT STRATEGY CODE:\n"
    prompt += strategy_code + "\n\n"
    prompt += "BACKTEST SYSTEM RULES:\n"
    prompt += "- Define SL_PCT and TP_PCT inside the function\n"
    prompt += "- For mean reversion: SL_PCT = 1.5 to 2.5, TP_PCT = 2.0 to 4.0\n"
    prompt += "- For momentum: SL_PCT = 3.0 to 5.0, TP_PCT = 6.0 to 12.0\n"
    prompt += "- Time stop exits after 48 candles\n\n"
    prompt += "PROVEN FIX PATTERNS (use these):\n"
    prompt += "- To fix Sharpe: add 'signals = signals / close.rolling(20).std()' before return\n"
    prompt += "- To fix Win Rate: add volume filter 'volume > volume.rolling(20).mean()' AND trend filter 'close > close.ewm(span=50).mean()'\n"
    prompt += "- To fix Drawdown: add 'close > close.ewm(span=100).mean()' filter and tighten SL_PCT to 1.5\n"
    prompt += "- To fix Trade Count: use rolling(10) or rolling(14) instead of rolling(30), use threshold 1.0 instead of 1.5\n\n"
    prompt += "STRICT RULES:\n"
    prompt += "1. Fix ONLY failing metrics - do not change passing logic\n"
    prompt += "2. Use ONLY pandas and numpy\n"
    prompt += "3. First two lines inside function: import pandas as pd and import numpy as np\n"
    prompt += "4. Define SL_PCT and TP_PCT inside the function\n"
    prompt += "5. Return pandas Series: 1=buy -1=sell 0=hold\n"
    prompt += "6. Handle NaN with .fillna(0) or .dropna()\n"
    prompt += "7. Generate at least 10 signals over 1000 candles\n\n"
    prompt += "Return ONLY the complete get_signals(df) function. No markdown. No explanation.\n"
    return prompt


def normalize_code(code):
    return re.sub(r'\s+', '', code).strip()


def is_duplicate_strategy(code, coin, seen_set):
    norm = normalize_code(code)
    for existing in seen_set.get(coin, []):
        if normalize_code(existing) == norm:
            return True
    return False


def generate_unique_strategy(generate_fn, prompt, coin, original_code, max_retries=3):
    seen = _seen_strategies.setdefault(coin, [])
    if original_code:
        seen.append(original_code)
    current_prompt = prompt
    for attempt in range(max_retries):
        code = generate_fn(current_prompt)
        if not code:
            return None
        if is_duplicate_strategy(code, coin, {coin: seen}):
            print("[UNIQUE] Strategy " + str(attempt + 1) + " is duplicate - retrying...", flush=True)
            current_prompt = prompt + "\n\nSTRATEGY REJECTED: The code you just gave is IDENTICAL to a previous strategy.\n"
            current_prompt += "You MUST write a COMPLETELY DIFFERENT strategy using:\n"
            current_prompt += "- Different indicators (e.g. switch from z-score to RSI or MACD)\n"
            current_prompt += "- Different periods (e.g. use 14-period instead of 20-period)\n"
            current_prompt += "- Different logic (e.g. add volume filter or trend confirmation)\n"
            current_prompt += "Do NOT repeat the same indicator combinations. Be creative.\n"
            continue
        seen.append(code)
        return code
    print("[UNIQUE] Failed to generate unique strategy after " + str(max_retries) + " attempts", flush=True)
    return None


def parse_code(text):
    if "```python" in text:
        code = text.split("```python")[1].split("```")[0].strip()
    elif "```" in text:
        code = text.split("```")[1].split("```")[0].strip()
    elif "def get_signals" in text:
        code = text[text.index("def get_signals"):].strip()
    else:
        code = text.strip()
    if "def get_signals" in code:
        return code
    return None


def call_gemini(prompt):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[GOOGLE_AI] GEMINI_API_KEY not set", flush=True)
        return None
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + api_key
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = requests.post(url, json=body, timeout=60)
        if r.status_code == 200:
            full = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            code = parse_code(full)
            if code:
                return code
            print("[GOOGLE_AI] No valid function in response", flush=True)
        elif r.status_code == 429:
            print("[GOOGLE_AI] Rate limited - skipping to fallback", flush=True)
        else:
            print("[GOOGLE_AI] Error: " + str(r.status_code), flush=True)
    except Exception as e:
        print("[GOOGLE_AI] Failed: " + str(e), flush=True)
    return None


def improve_strategy_with_google_ai(strategy_code, failed_metrics, coin, item=None):
    print("[GOOGLE_AI] Building improvement prompt for " + coin + " fixing: " + str(failed_metrics), flush=True)
    prompt = build_improvement_prompt(strategy_code, failed_metrics, coin, item)
    code = generate_unique_strategy(call_gemini, prompt, coin, strategy_code)
    if code:
        print("[GOOGLE_AI] Strategy improved for " + coin, flush=True)
        return code, None
    return None, "Gemini rate limited or failed - check API key and quota"


def call_nvidia_for_improvement(prompt):
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        print("[NVIDIA_AI] NVIDIA_API_KEY not set", flush=True)
        return None
    for attempt in range(3):
        try:
            r = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": "Bearer " + api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-ai/deepseek-v4-pro",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0.3
                },
                timeout=120
            )
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"]
                code = parse_code(content)
                if code:
                    return code
                print("[NVIDIA_AI] No valid function in response", flush=True)
                return None
            elif r.status_code == 429:
                wait = 30 * (attempt + 1)
                print("[NVIDIA_AI] Rate limited - waiting " + str(wait) + "s attempt " + str(attempt + 1) + "/3", flush=True)
                time.sleep(wait)
                continue
            else:
                print("[NVIDIA_AI] Error " + str(r.status_code), flush=True)
                return None
        except Exception as e:
            print("[NVIDIA_AI] Failed: " + str(e), flush=True)
            return None
    print("[NVIDIA_AI] All retries failed", flush=True)
    return None


def improve_strategy_with_nvidia(strategy_code, failed_metrics, coin, item=None, prev_error=None):
    print("[NVIDIA_AI] Building improvement prompt for " + coin + " fixing: " + str(failed_metrics), flush=True)
    prompt = build_improvement_prompt(strategy_code, failed_metrics, coin, item)
    if prev_error:
        prompt += "\nPREVIOUS ATTEMPT ERROR:\n"
        prompt += prev_error + "\n\n"
        prompt += "The previous AI provider failed with the above error. Analyze this error and make sure your fix avoids it.\n"
        prompt += "If the error mentions rate limiting, connection timeout, or auth - ignore it and just produce a working strategy.\n"
        prompt += "If the error was a backtest failure, specifically fix that metric.\n"
        prompt += "Return ONLY the complete get_signals(df) function. No markdown. No explanation.\n"
    code = generate_unique_strategy(call_nvidia_for_improvement, prompt, coin, strategy_code)
    if code:
        print("[NVIDIA_AI] Strategy improved for " + coin, flush=True)
    return code


def batch_improve_and_validate_strategies(partial_fails, strategy_code, all_data):
    from backtest import run_backtest, is_strategy_good
    improved = {}
    for item in partial_fails:
        coin = item["coin"]
        failed_metrics = item["failed_metrics"]
        if len(failed_metrics) != 1:
            print("[PIPELINE] " + coin + " has " + str(len(failed_metrics)) + " failures - skip, only fix when exactly 1 fails", flush=True)
            continue
        print("[PIPELINE] Processing " + coin + " - fixing: " + str(failed_metrics), flush=True)
        print("[PIPELINE] Current scores - Sharpe: " + str(item.get("sharpe")) + " Win: " + str(item.get("win_rate")) + "% DD: " + str(item.get("max_drawdown")) + "% Trades: " + str(item.get("trades")), flush=True)
        time.sleep(90)
        new_code, gemini_error = improve_strategy_with_google_ai(strategy_code, failed_metrics, coin, item)
        if new_code:
            improved[coin] = new_code
            print("[PIPELINE] " + coin + " improved by Gemini - ready for backtest", flush=True)
        else:
            print("[PIPELINE] Gemini failed for " + coin + " - trying NVIDIA fallback...", flush=True)
            new_code = improve_strategy_with_nvidia(strategy_code, failed_metrics, coin, item, prev_error=gemini_error)
            if new_code:
                subset = {coin: all_data[coin]} if coin in all_data else {}
                if subset:
                    bt_results = run_backtest(new_code, subset)
                    bt_good, _ = is_strategy_good(bt_results)
                    if coin in bt_good:
                        improved[coin] = new_code
                        print("[PIPELINE] " + coin + " improved by NVIDIA - backtest PASSED", flush=True)
                    else:
                        score = bt_results.get(coin, {})
                        err_detail = "Backtest failed: " + ", ".join(score.get("failed_metrics", ["unknown"]))
                        err_detail += " | Sharpe: " + str(score.get("sharpe", "?"))
                        err_detail += " Win: " + str(score.get("win_rate", "?")) + "%"
                        err_detail += " DD: " + str(score.get("max_drawdown", "?")) + "%"
                        print("[PIPELINE] " + coin + " NVIDIA code failed backtest - retrying with error context...", flush=True)
                        retry_code = improve_strategy_with_nvidia(strategy_code, failed_metrics, coin, item, prev_error=err_detail)
                        if retry_code:
                            retry_results = run_backtest(retry_code, subset)
                            retry_good, _ = is_strategy_good(retry_results)
                            if coin in retry_good:
                                improved[coin] = retry_code
                                print("[PIPELINE] " + coin + " NVIDIA retry - backtest PASSED", flush=True)
                            else:
                                print("[PIPELINE] " + coin + " NVIDIA retry also failed backtest - skipping", flush=True)
                        else:
                            print("[PIPELINE] " + coin + " NVIDIA retry failed to generate code - skipping", flush=True)
            else:
                print("[PIPELINE] Both Gemini and NVIDIA failed for " + coin + " - skipping", flush=True)
    return improved


def generate_html_report(partial_fails, improved_strategies):
    return None
