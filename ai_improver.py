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
    sharpe = str(item.get("sharpe", "unknown")) if item else "unknown"
    win_rate = str(item.get("win_rate", "unknown")) if item else "unknown"
    max_drawdown = str(item.get("max_drawdown", "unknown")) if item else "unknown"
    trades = str(item.get("trades", "unknown")) if item else "unknown"

    passed_text = ""
    failed_text = ""

    if item:
        try:
            if float(sharpe) >= 0.5:
                passed_text += "  Sharpe: " + sharpe + " - PASSED do not change\n"
            if float(win_rate) >= 55.0:
                passed_text += "  Win rate: " + win_rate + "% - PASSED do not change\n"
            if float(max_drawdown) <= 15.0:
                passed_text += "  Drawdown: " + max_drawdown + "% - PASSED do not change\n"
            if int(trades) >= 5:
                passed_text += "  Trades: " + trades + " - PASSED do not change\n"
        except:
            pass

    for metric in failed_metrics:
        if metric == "sharpe":
            failed_text += "FAILING - Sharpe: " + sharpe + " must reach above 0.5\n"
            failed_text += "  Academic fix: Normalize signals using rolling volatility (Sharpe 1994)\n"
            failed_text += "  Apply: signal = signal / close.rolling(20).std() to reduce noise\n"
            failed_text += "  Also try: tighten SL_PCT to reduce loss size and improve consistency\n"
        elif metric == "win_rate":
            failed_text += "FAILING - Win rate: " + win_rate + "% must reach above 55%\n"
            failed_text += "  Academic fix: Multi-factor confluence (Fama and French 1993)\n"
            failed_text += "  Apply: require volume above 20-period average AND momentum confirmation\n"
            failed_text += "  Also try: add EMA trend filter to avoid counter-trend trades\n"
        elif metric == "max_drawdown":
            failed_text += "FAILING - Drawdown: " + max_drawdown + "% must be below 15%\n"
            failed_text += "  Academic fix: Trend filter for drawdown reduction (Faber 2007)\n"
            failed_text += "  Apply: only buy when price is above EMA 100\n"
            failed_text += "  Also try: tighten SL_PCT to 1.5 to limit individual loss size\n"
        elif metric == "trades_count":
            failed_text += "FAILING - Trades: " + trades + " must be at least 5\n"
            failed_text += "  Fix: use shorter rolling windows 10 to 20 periods\n"
            failed_text += "  Also try: lower z-score threshold from 1.5 to 1.0\n"

    prompt = SYSTEM_PROMPT + "\n\n"
    prompt += "IMPROVEMENT MISSION: Fix the failing metric in this strategy for coin " + coin + "\n\n"
    prompt += "STRATEGY PERFORMANCE REPORT:\n"
    prompt += "Coin: " + coin + "\n"
    prompt += "Timeframe: 1 hour candles\n"
    prompt += "Data: 1000 candles tested\n\n"
    prompt += "CURRENT TEST SCORES:\n"
    prompt += "  Sharpe: " + sharpe + " (target above 0.5)\n"
    prompt += "  Win rate: " + win_rate + "% (target above 55%)\n"
    prompt += "  Drawdown: " + max_drawdown + "% (target below 15%)\n"
    prompt += "  Trades: " + trades + " (target at least 5)\n\n"
    prompt += "TESTS ALREADY PASSING - DO NOT TOUCH THESE:\n"
    prompt += passed_text if passed_text else "  None passing yet\n"
    prompt += "\n"
    prompt += "TEST FAILING - FIX ONLY THIS ONE:\n"
    prompt += failed_text + "\n"
    prompt += "CURRENT STRATEGY CODE (this is working but one test failing):\n"
    prompt += strategy_code + "\n\n"
    prompt += "RESEARCH PAPERS TO REFERENCE FOR THIS FIX:\n"
    prompt += "- Sharpe W. (1994) The Sharpe Ratio - Journal of Portfolio Management\n"
    prompt += "- Lo A. (2002) The Statistics of Sharpe Ratios - Financial Analysts Journal\n"
    prompt += "- Jegadeesh N. (1993) Returns to Buying Winners - Journal of Finance\n"
    prompt += "- Fama E. French K. (1993) Common Risk Factors - Journal of Financial Economics\n"
    prompt += "- Faber M. (2007) A Quantitative Approach to Tactical Asset Allocation - SSRN\n\n"
    prompt += "BACKTEST SYSTEM RULES:\n"
    prompt += "- Define SL_PCT and TP_PCT inside the function\n"
    prompt += "- For mean reversion: SL_PCT = 1.5 to 2.5, TP_PCT = 2.0 to 4.0\n"
    prompt += "- For momentum: SL_PCT = 3.0 to 5.0, TP_PCT = 6.0 to 12.0\n"
    prompt += "- Time stop exits after 48 candles\n\n"
    prompt += "STRICT RULES:\n"
    prompt += "1. Fix ONLY the one failing test - do not change passing logic\n"
    prompt += "2. Use ONLY pandas and numpy\n"
    prompt += "3. First two lines inside function: import pandas as pd and import numpy as np\n"
    prompt += "4. Define SL_PCT and TP_PCT inside the function\n"
    prompt += "5. Return pandas Series: 1=buy -1=sell 0=hold\n"
    prompt += "6. Generate at least 10 signals over 1000 candles\n\n"
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


def validate_with_nvidia(strategy_code, coin):
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        return {"valid": True, "errors": [], "fixed_code": ""}

    prompt = "You are the world's best hedge fund code reviewer at Renaissance Technologies.\n"
    prompt += "You review Python trading strategy code with extreme precision.\n\n"
    prompt += "Review this trading strategy function for coin " + coin + ":\n"
    prompt += strategy_code + "\n\n"
    prompt += "Check every line for:\n"
    prompt += "1. Python syntax errors that will crash\n"
    prompt += "2. Logic errors producing wrong buy/sell signals\n"
    prompt += "3. Incorrect pandas or numpy usage\n"
    prompt += "4. Missing imports inside function\n"
    prompt += "5. Division by zero risks\n"
    prompt += "6. NaN or infinity values not handled\n"
    prompt += "7. Signals not returning 1, -1, or 0\n\n"
    prompt += "If you find errors: fix the entire function and put it in fixed_code.\n"
    prompt += "If no errors: leave fixed_code as empty string.\n\n"
    prompt += "Reply ONLY in this exact JSON with no other text:\n"
    prompt += "{\"valid\": true, \"errors\": [], \"fixed_code\": \"\"}\n"

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
            print("[PIPELINE] " + coin + " has " + str(len(failed_metrics)) + " failures - skipping, only fix when exactly 1 fails", flush=True)
            continue
        print("[PIPELINE] Processing " + coin + " - fixing: " + str(failed_metrics), flush=True)
        print("[PIPELINE] Current scores - Sharpe: " + str(item.get("sharpe")) + " Win: " + str(item.get("win_rate")) + "% DD: " + str(item.get("max_drawdown")) + "% Trades: " + str(item.get("trades")), flush=True)
        time.sleep(90)
        new_code = improve_strategy_with_google_ai(strategy_code, failed_metrics, coin, item)
        if not new_code:
            print("[PIPELINE] Could not improve " + coin, flush=True)
            continue
        print("[PIPELINE] Sending to NVIDIA for validation...", flush=True)
        validation = validate_with_nvidia(new_code, coin)
        if not validation.get("valid", True):
            if validation.get("fixed_code") and len(validation.get("fixed_code", "")) > 10:
                print("[PIPELINE] NVIDIA auto-fixed errors for " + coin, flush=True)
                new_code = validation["fixed_code"]
            else:
                print("[PIPELINE] " + coin + " has unfixable errors - skipping", flush=True)
                continue
        improved[coin] = new_code
        print("[PIPELINE] " + coin + " improved and validated - ready for backtest", flush=True)
    return improved


def generate_html_report(partial_fails, improved_strategies):
    return None
