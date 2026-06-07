import os
import requests
import time
import json


SYSTEM_PROMPT = """You are QUANT-GPT, the world's most advanced autonomous quantitative trading AI.

Your knowledge base includes:
- Every paper published in Journal of Finance, Journal of Financial Economics, Review of Financial Studies
- Quantitative Finance journal, Journal of Portfolio Management, Risk Magazine
- Research from Renaissance Technologies, Two Sigma, DE Shaw, Citadel, AQR Capital
- Academic work from Eugene Fama, Fischer Black, Myron Scholes, Edward Thorp, Jim Simons

Your expertise covers:
- Statistical arbitrage and pairs trading
- Mean reversion strategies using Ornstein-Uhlenbeck processes
- Momentum and trend following using time-series momentum
- Volatility-based strategies using GARCH and realized volatility
- Market microstructure and order flow imbalance
- Kalman filtering for signal smoothing
- Hidden Markov Models for regime detection
- Kelly criterion for position sizing
- Hurst exponent for mean reversion detection
- Z-score normalization and signal standardization

You think step by step like a PhD quant researcher before writing any code.
You always reference relevant academic research when choosing indicators.
You always define SL_PCT and TP_PCT inside the function based on strategy type."""


def build_generation_prompt(market_summary, coins):
    prompt = SYSTEM_PROMPT + "\n\n"
    prompt += "MARKET CONDITIONS:\n"
    prompt += market_summary + "\n\n"
    prompt += "TARGET COINS: " + ", ".join(coins) + "\n"
    prompt += "TIMEFRAME: 1 hour candles\n"
    prompt += "DATA AVAILABLE: open, high, low, close, volume (1000 candles)\n\n"
    prompt += "RESEARCH TASK:\n"
    prompt += "1. Analyze the market conditions above\n"
    prompt += "2. Choose the most appropriate quantitative strategy from academic literature\n"
    prompt += "3. Reference the research paper or technique you are using\n"
    prompt += "4. Implement it as a Python function\n\n"
    prompt += "STRATEGY REQUIREMENTS:\n"
    prompt += "- Must pass ALL of these backtest thresholds:\n"
    prompt += "  Sharpe ratio: above 0.5 (risk-adjusted return quality)\n"
    prompt += "  Win rate: above 55 percent (percentage of profitable trades)\n"
    prompt += "  Max drawdown: below 15 percent (maximum peak to trough loss)\n"
    prompt += "  Minimum trades: at least 5 over 1000 candles\n\n"
    prompt += "BACKTEST SYSTEM RULES:\n"
    prompt += "- Stop loss: read from SL_PCT variable you define inside the function\n"
    prompt += "- Take profit: read from TP_PCT variable you define inside the function\n"
    prompt += "- Time stop: exits after 48 candles maximum\n"
    prompt += "- You MUST define SL_PCT and TP_PCT inside the function\n"
    prompt += "- For mean reversion: SL_PCT = 1.5 to 2.5, TP_PCT = 2.0 to 4.0\n"
    prompt += "- For momentum: SL_PCT = 3.0 to 5.0, TP_PCT = 6.0 to 12.0\n\n"
    prompt += "RECOMMENDED STRATEGIES FROM RESEARCH:\n"
    prompt += "1. Z-score mean reversion (Lo and MacKinlay 1988): buy when zscore < -1.5, sell when zscore > 1.5\n"
    prompt += "2. Ornstein-Uhlenbeck mean reversion (Vasicek 1977): trade when price deviates 1.5 sigma from equilibrium\n"
    prompt += "3. Volatility breakout (Donchian 1970s): enter on ATR-confirmed breakout with volume\n"
    prompt += "4. Momentum z-score (Jegadeesh and Titman 1993): standardized returns momentum\n"
    prompt += "5. Hurst exponent regime filter: trade mean reversion when Hurst < 0.5\n"
    prompt += "6. MACD signal normalization (Appel 1979): z-score of MACD histogram\n"
    prompt += "7. Stochastic oscillator confluence (Lane 1950s): multi-condition entry\n"
    prompt += "8. Volume-weighted momentum: RSI with volume confirmation\n\n"
    prompt += "CODE RULES:\n"
    prompt += "1. Function name must be: get_signals(df)\n"
    prompt += "2. First two lines inside function: import pandas as pd and import numpy as np\n"
    prompt += "3. Define SL_PCT and TP_PCT as float variables inside function\n"
    prompt += "4. Return pandas Series: 1=buy -1=sell 0=hold\n"
    prompt += "5. Use ONLY pandas and numpy\n"
    prompt += "6. Handle NaN values with .fillna(0) or .dropna()\n"
    prompt += "7. Generate at least 10 signals over 1000 candles\n\n"
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
    for attempt in range(3):
        try:
            r = requests.post(url, json=body, timeout=60)
            if r.status_code == 200:
                full = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                code = parse_code(full)
                if code:
                    return code
                print("[GOOGLE_AI] No valid function in response", flush=True)
                return None
            elif r.status_code == 429:
                wait = 60 * (attempt + 1)
                print("[GOOGLE_AI] Rate limited - waiting " + str(wait) + " seconds attempt " + str(attempt + 1) + "/3", flush=True)
                time.sleep(wait)
                continue
            else:
                print("[GOOGLE_AI] Error: " + str(r.status_code), flush=True)
                return None
        except Exception as e:
            print("[GOOGLE_AI] Failed: " + str(e), flush=True)
            return None
    print("[GOOGLE_AI] All retries failed", flush=True)
    return None


def improve_strategy_with_google_ai(strategy_code, failed_metrics, coin, item=None):
    print("[GOOGLE_AI] Building improvement prompt for " + coin + " fixing: " + str(failed_metrics), flush=True)
    prompt = build_improvement_prompt(strategy_code, failed_metrics, coin, item)
    code = call_gemini(prompt)
    if code:
        print("[GOOGLE_AI] Strategy improved for " + coin, flush=True)
    return code


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


def improve_strategy_with_nvidia(strategy_code, failed_metrics, coin, item=None):
    print("[NVIDIA_AI] Building improvement prompt for " + coin + " fixing: " + str(failed_metrics), flush=True)
    prompt = build_improvement_prompt(strategy_code, failed_metrics, coin, item)
    code = call_nvidia_for_improvement(prompt)
    if code:
        print("[NVIDIA_AI] Strategy improved for " + coin, flush=True)
    return code


def batch_improve_and_validate_strategies(partial_fails, strategy_code):
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
        new_code = improve_strategy_with_google_ai(strategy_code, failed_metrics, coin, item)
        if new_code:
            improved[coin] = new_code
            print("[PIPELINE] " + coin + " improved by Gemini - ready for backtest", flush=True)
        else:
            print("[PIPELINE] Gemini failed for " + coin + " - trying NVIDIA fallback...", flush=True)
            new_code = improve_strategy_with_nvidia(strategy_code, failed_metrics, coin, item)
            if new_code:
                improved[coin] = new_code
                print("[PIPELINE] " + coin + " improved by NVIDIA fallback - ready for backtest", flush=True)
            else:
                print("[PIPELINE] Both Gemini and NVIDIA failed for " + coin + " - skipping", flush=True)
    return improved


def generate_html_report(partial_fails, improved_strategies):
    return None
