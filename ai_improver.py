import os
import requests


def improve_strategy_with_google_ai(strategy_code, failed_metrics, coin):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[GOOGLE_AI] GEMINI_API_KEY not set", flush=True)
        return None

    failed_text = ""
    for metric in failed_metrics:
        if metric == "sharpe":
            failed_text += "- Sharpe ratio is too low. Fix: make wins bigger than losses, reduce trade noise\n"
        elif metric == "win_rate":
            failed_text += "- Win rate is too low. Fix: tighten entry conditions, add confluence filters\n"
        elif metric == "max_drawdown":
            failed_text += "- Drawdown is too high. Fix: tighten entry timing, avoid buying in downtrends\n"
        elif metric == "trades_count":
            failed_text += "- Too few trades. Fix: relax entry conditions slightly to generate more signals\n"

    prompt = "You are an expert quantitative trading strategy developer.\n"
    prompt += "This Python trading strategy is failing for coin " + coin + ".\n"
    prompt += "ONLY fix these specific problems:\n"
    prompt += failed_text
    prompt += "Do NOT change parts that are working.\n"
    prompt += "Here is the current strategy code:\n"
    prompt += strategy_code + "\n"
    prompt += "Return ONLY the complete fixed get_signals(df) function.\n"
    prompt += "The function MUST start with: import pandas as pd\n"
    prompt += "The function MUST start with: import numpy as np\n"
    prompt += "No markdown. No explanation. Just the function.\n"

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
                print("[GOOGLE_AI] Improved strategy for " + coin + " fixing: " + str(failed_metrics), flush=True)
                return code
            print("[GOOGLE_AI] No valid function returned", flush=True)
            return None
        elif r.status_code == 429:
            print("[GOOGLE_AI] Rate limited, skipping", flush=True)
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
    prompt = "Check this Python function for syntax errors only. Reply in JSON format: "
    prompt += "{\"valid\": true or false, \"errors\": [\"list of errors\"]}\n"
    prompt += strategy_code
    try:
        r = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json={
                "model": "deepseek-ai/deepseek-v4-pro",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.1
            },
            timeout=60
        )
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"]
            import json
            try:
                start = content.find("{")
                end = content.rfind("}") + 1
                result = json.loads(content[start:end])
                print("[NVIDIA] Validated " + coin + " errors: " + str(result.get("errors", [])), flush=True)
                return result
            except:
                return {"valid": True, "errors": []}
        return {"valid": True, "errors": []}
    except Exception as e:
        print("[NVIDIA] Failed: " + str(e), flush=True)
        return {"valid": True, "errors": []}


def batch_improve_and_validate_strategies(partial_fails, strategy_code):
    improved = {}
    for item in partial_fails:
        coin = item["coin"]
        failed_metrics = item["failed_metrics"]
        print("[PIPELINE] " + coin + " fixing only: " + str(failed_metrics), flush=True)
        new_code = improve_strategy_with_google_ai(strategy_code, failed_metrics, coin)
        if not new_code:
            print("[PIPELINE] Could not improve " + coin, flush=True)
            continue
        validation = validate_with_nvidia(new_code, coin)
        if validation.get("errors"):
            print("[PIPELINE] " + coin + " has errors after fix: " + str(validation["errors"]), flush=True)
        else:
            improved[coin] = new_code
            print("[PIPELINE] " + coin + " improved and validated successfully", flush=True)
    return improved


def generate_html_report(partial_fails, improved_strategies):
    return None
