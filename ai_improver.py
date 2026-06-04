try:
    import google.generativeai as genai
    GOOGLE_AI_AVAILABLE = True
except ImportError:
    GOOGLE_AI_AVAILABLE = False
    print("[WARNING] google-generativeai not installed. Install with: pip install google-generativeai", flush=True)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("[WARNING] requests not installed. Install with: pip install requests", flush=True)

import json
import os


def improve_strategy_with_google_ai(strategy_code, feedback_list, coin):
    """
    Use Google Gemini AI to improve the strategy based on feedback
    Requires GOOGLE_API_KEY environment variable
    """
    try:
        if not GOOGLE_AI_AVAILABLE:
            print("[GOOGLE_AI] google-generativeai not available. Skipping.", flush=True)
            return None
        
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("[GOOGLE_AI] GOOGLE_API_KEY not set. Skipping Google AI improvement.", flush=True)
            return None
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        feedback_text = "\n".join(feedback_list)
        
        prompt = f"""You are a professional quantitative trading strategy optimizer with expertise in algorithmic trading and quantitative finance.

Current Strategy Code:
```python
{strategy_code}
```

Performance Feedback:
{feedback_text}

Your task:
1. Analyze why the strategy is failing on these specific metrics
2. Reference quantitative trading principles and research papers (if applicable)
3. Propose improvements ONLY to fix the failed metrics
4. Keep the successful parts of the strategy
5. Return ONLY valid Python code in a function called 'get_signals(df)' that takes a DataFrame and returns trading signals (-1, 0, 1)

Requirements:
- Input: df with columns ['open', 'high', 'low', 'close', 'volume']
- Output: pd.Series of signals (-1 for sell, 0 for hold, 1 for buy)
- Must use pandas and numpy
- Do NOT include test code or main execution
- Focus on improving the failed metrics
- Use quantitative trading best practices

Improved Strategy Code:
```python
def get_signals(df):
    import pandas as pd
    import numpy as np
    # Your improved implementation here
```"""

        print("[GOOGLE_AI] Sending strategy to Google Gemini for improvement...", flush=True)
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1024,
            )
        )
        
        improved_code = response.text
        
        # Extract Python code from response
        if "```python" in improved_code:
            start = improved_code.find("```python") + 9
            end = improved_code.find("```", start)
            improved_code = improved_code[start:end].strip()
        elif "```" in improved_code:
            start = improved_code.find("```") + 3
            end = improved_code.find("```", start)
            improved_code = improved_code[start:end].strip()
        
        print("[GOOGLE_AI] Strategy improvement for " + coin + " generated successfully", flush=True)
        return improved_code
        
    except Exception as e:
        print("[GOOGLE_AI] Error during strategy improvement: " + str(e), flush=True)
        return None


def validate_with_nvidia_ai(strategy_code, coin):
    """
    Use NVIDIA NIM API to validate and check strategy code for errors
    Requires NVIDIA_API_KEY and NVIDIA_API_ENDPOINT environment variables
    """
    try:
        if not REQUESTS_AVAILABLE:
            print("[NVIDIA_AI] requests library not available. Skipping validation.", flush=True)
            return {"valid": True, "errors": [], "warnings": []}
        
        api_key = os.environ.get("NVIDIA_API_KEY")
        api_endpoint = os.environ.get("NVIDIA_API_ENDPOINT", "https://integrate.api.nvidia.com/v1/chat/completions")
        
        if not api_key:
            print("[NVIDIA_AI] NVIDIA_API_KEY not set. Skipping NVIDIA validation.", flush=True)
            return {"valid": True, "errors": [], "warnings": []}
        
        prompt = f"""You are an expert Python code reviewer specialized in trading strategies.

Analyze this trading strategy code for errors, bugs, and improvements:

```python
{strategy_code}
```

Perform a thorough code review and provide:
1. List any syntax errors or runtime errors
2. List any logical issues or edge cases
3. Check for pandas/numpy usage correctness
4. Verify the function returns correct signal types (-1, 0, 1)
5. Check for missing edge case handling

Respond ONLY in JSON format:
{{
    "valid": true/false,
    "errors": ["list of critical errors"],
    "warnings": ["list of warnings"],
    "suggestions": ["list of improvements"],
    "analysis": "Brief analysis of code quality"
}}"""

        print("[NVIDIA_AI] Sending code to NVIDIA for validation...", flush=True)
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "meta/llama-3.1-70b-instruct",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 1024
        }
        
        response = requests.post(api_endpoint, json=payload, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print("[NVIDIA_AI] Validation failed with status " + str(response.status_code), flush=True)
            return {"valid": True, "errors": [], "warnings": []}
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # Extract JSON from response
        try:
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = content[json_start:json_end]
                validation_result = json.loads(json_str)
            else:
                validation_result = {"valid": True, "errors": [], "warnings": []}
        except:
            validation_result = {"valid": True, "errors": [], "warnings": []}
        
        print("[NVIDIA_AI] Code validation for " + coin + " completed", flush=True)
        
        if validation_result.get("errors"):
            print("[NVIDIA_AI] ERRORS found for " + coin + ": " + str(validation_result.get("errors")), flush=True)
        
        if validation_result.get("warnings"):
            print("[NVIDIA_AI] WARNINGS for " + coin + ": " + str(validation_result.get("warnings")), flush=True)
        
        return validation_result
        
    except Exception as e:
        print("[NVIDIA_AI] Error during code validation: " + str(e), flush=True)
        return {"valid": True, "errors": [], "warnings": []}


def fix_strategy_with_nvidia(strategy_code, validation_result, coin):
    """
    Use NVIDIA AI to fix errors found in the strategy code
    """
    try:
        if not REQUESTS_AVAILABLE:
            return strategy_code
        
        api_key = os.environ.get("NVIDIA_API_KEY")
        api_endpoint = os.environ.get("NVIDIA_API_ENDPOINT", "https://integrate.api.nvidia.com/v1/chat/completions")
        
        if not api_key or not validation_result.get("errors"):
            return strategy_code
        
        errors_text = "\n".join(validation_result.get("errors", []))
        
        prompt = f"""You are an expert Python developer specializing in trading strategies.

Fix the following trading strategy code. These errors were found:

ERRORS TO FIX:
{errors_text}

ORIGINAL CODE:
```python
{strategy_code}
```

Provide ONLY the corrected Python code as a function called 'get_signals(df)' that:
- Takes a DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
- Returns pd.Series of signals (-1 for sell, 0 for hold, 1 for buy)
- Fixes all listed errors
- Maintains the original strategy logic where possible

Fixed Code:
```python
def get_signals(df):
    import pandas as pd
    import numpy as np
    # Your fixed implementation here
```"""

        print("[NVIDIA_AI] Sending code to NVIDIA for error fixing...", flush=True)
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "meta/llama-3.1-70b-instruct",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1024
        }
        
        response = requests.post(api_endpoint, json=payload, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print("[NVIDIA_AI] Fix request failed", flush=True)
            return strategy_code
        
        result = response.json()
        fixed_code = result["choices"][0]["message"]["content"]
        
        # Extract Python code from response
        if "```python" in fixed_code:
            start = fixed_code.find("```python") + 9
            end = fixed_code.find("```", start)
            fixed_code = fixed_code[start:end].strip()
        elif "```" in fixed_code:
            start = fixed_code.find("```") + 3
            end = fixed_code.find("```", start)
            fixed_code = fixed_code[start:end].strip()
        
        print("[NVIDIA_AI] Strategy fixed for " + coin, flush=True)
        return fixed_code
        
    except Exception as e:
        print("[NVIDIA_AI] Error during code fixing: " + str(e), flush=True)
        return strategy_code


def save_improved_strategy(coin, strategy_code, feedback, validation_result=None):
    """Save improved and validated strategy to file for reference"""
    try:
        filename = "improved_strategies_" + coin + ".json"
        
        data = {
            "coin": coin,
            "timestamp": str(__import__("datetime").datetime.now()),
            "feedback": feedback,
            "improved_strategy": strategy_code,
            "validation": validation_result
        }
        
        improvements = []
        if os.path.exists(filename):
            with open(filename, "r") as f:
                improvements = json.load(f)
        
        improvements.append(data)
        
        with open(filename, "w") as f:
            json.dump(improvements, f, indent=2)
        
        print("[STRATEGY_SAVE] Saved improved strategy for " + coin + " to " + filename, flush=True)
    except Exception as e:
        print("[STRATEGY_SAVE] Failed to save improved strategy: " + str(e), flush=True)


def batch_improve_and_validate_strategies(partial_fails, strategy_code):
    """
    Improve strategies with Google Gemini and validate with NVIDIA
    Returns dict of {coin: improved_code}
    """
    improved_strategies = {}
    
    for item in partial_fails:
        coin = item["coin"]
        print("\n[PIPELINE] Processing " + coin + "...", flush=True)
        
        # Step 1: Google Gemini creates improved code
        feedback = get_ai_feedback_for_coin(item)
        improved = improve_strategy_with_google_ai(strategy_code, feedback, coin)
        
        if not improved:
            print("[PIPELINE] Failed to generate improved strategy for " + coin, flush=True)
            continue
        
        # Step 2: NVIDIA validates the code
        validation = validate_with_nvidia_ai(improved, coin)
        
        # Step 3: If errors found, NVIDIA fixes them
        if validation.get("errors"):
            print("[PIPELINE] Errors found in " + coin + ", attempting fix...", flush=True)
            improved = fix_strategy_with_nvidia(improved, validation, coin)
            
            # Re-validate after fix
            validation = validate_with_nvidia_ai(improved, coin)
        
        # Step 4: Save the final strategy
        save_improved_strategy(coin, improved, "\n".join(feedback), validation)
        improved_strategies[coin] = improved
        
        print("[PIPELINE] " + coin + " completed successfully", flush=True)
    
    return improved_strategies


def get_ai_feedback_for_coin(item):
    """Format feedback for a single coin with quantitative trading context"""
    feedback = []
    feedback.append("[" + item['coin'] + " QUANTITATIVE TRADING ANALYSIS]")
    feedback.append("Passed: " + str(item['passed_count']) + "/4 metrics")
    feedback.append("\nCurrent Results:")
    feedback.append("  - Sharpe Ratio: " + str(item['sharpe']) + " (target: >= 0.5)")
    feedback.append("    * Measures risk-adjusted returns. Higher is better.")
    feedback.append("    * Reference: Sharpe Ratio in Modern Portfolio Theory")
    feedback.append("  - Win Rate: " + str(item['win_rate']) + "% (target: >= 55%)")
    feedback.append("    * Percentage of profitable trades. Critical for edge.")
    feedback.append("    * Reference: Win Rate vs. Risk/Reward Ratio in quantitative trading")
    feedback.append("  - Max Drawdown: " + str(item['max_drawdown']) + "% (target: <= 20%)")
    feedback.append("    * Maximum peak-to-trough decline. Important for risk management.")
    feedback.append("    * Reference: Drawdown constraints in fund management")
    feedback.append("  - Trade Count: " + str(item['trades']) + " (target: >= 5)")
    feedback.append("    * More trades = better statistical significance")
    feedback.append("    * Reference: Statistical significance in backtesting")
    
    feedback.append("\nFailing Metrics to Fix:")
    for metric in item['failed_metrics']:
        if metric == "sharpe":
            feedback.append("\n• SHARPE RATIO: " + str(item['sharpe']) + " → needs >= 0.5")
            feedback.append("  Quant Trading Insight:")
            feedback.append("  - Adjust volatility of returns (reduce standard deviation)")
            feedback.append("  - Improve signal accuracy to increase average returns")
            feedback.append("  - Reference: 'A Post-Modern Portfolio Theory' - Perry & Shrikhande")
            feedback.append("  - Try: Fine-tune indicator periods, add mean-reversion logic")
        elif metric == "win_rate":
            feedback.append("\n• WIN RATE: " + str(item['win_rate']) + "% → needs >= 55%")
            feedback.append("  Quant Trading Insight:")
            feedback.append("  - Need better signal quality to reduce false positives")
            feedback.append("  - Consider ensemble methods or multi-factor confirmation")
            feedback.append("  - Reference: 'Machine Learning for Trading' - Alpaydin")
            feedback.append("  - Try: Add volume confirmation, volatility filters, or multiple indicators")
        elif metric == "max_drawdown":
            feedback.append("\n• MAX DRAWDOWN: " + str(item['max_drawdown']) + "% → needs <= 20%")
            feedback.append("  Quant Trading Insight:")
            feedback.append("  - Risk management is critical. Implement stop-loss strategies")
            feedback.append("  - Consider position sizing or portfolio diversification")
            feedback.append("  - Reference: 'The Black Swan' - Nassim Taleb")
            feedback.append("  - Try: Add stop-loss at -3%, trailing stops, or reduce position sizing")
        elif metric == "trades_count":
            feedback.append("\n• TRADE COUNT: " + str(item['trades']) + " → needs >= 5")
            feedback.append("  Quant Trading Insight:")
            feedback.append("  - More trades improve statistical validity of backtest results")
            feedback.append("  - Sample size matters for edge estimation")
            feedback.append("  - Reference: 'Fooled by Randomness' - Nassim Taleb")
            feedback.append("  - Try: Relax entry conditions, add new indicators, lower thresholds")
    
    return feedback


def generate_html_report(partial_fails, improved_strategies):
    """Generate an HTML report of improvements with validation status"""
    try:
        html = """
        <html>
        <head>
            <title>AI-Powered Quantitative Trading Strategy Report</title>
            <style>
                body { 
                    font-family: 'Courier New', monospace; 
                    margin: 20px; 
                    background-color: #f5f5f5;
                }
                .header {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }
                .coin { 
                    border: 2px solid #ddd; 
                    padding: 15px; 
                    margin: 10px 0; 
                    border-radius: 5px;
                    background-color: white;
                }
                .pass { background-color: #d4edda; border-left: 5px solid #28a745; }
                .fail { background-color: #f8d7da; border-left: 5px solid #dc3545; }
                .validated { background-color: #d1ecf1; border-left: 5px solid #17a2b8; }
                .metric { margin: 5px 0; font-weight: bold; }
                .metric-value { color: #666; }
                code { 
                    background: #f4f4f4; 
                    padding: 2px 5px; 
                    border-radius: 3px;
                    font-size: 0.9em;
                }
                pre {
                    background: #f4f4f4;
                    padding: 10px;
                    border-radius: 3px;
                    overflow-x: auto;
                    max-height: 400px;
                    overflow-y: auto;
                }
                .pipeline-status {
                    background: #e3f2fd;
                    padding: 10px;
                    border-left: 4px solid #1976d2;
                    margin: 10px 0;
                    border-radius: 3px;
                }
                .timestamp {
                    color: #999;
                    font-size: 0.9em;
                }
                .ai-badge {
                    display: inline-block;
                    background: #667eea;
                    color: white;
                    padding: 5px 10px;
                    border-radius: 3px;
                    margin: 5px 5px 5px 0;
                    font-size: 0.8em;
                }
            </style>
        </head>
        <body>
        <div class="header">
            <h1>🤖 AI-Powered Quantitative Trading Strategy Report</h1>
            <div>
                <span class="ai-badge">🔵 Google Gemini (Code Generation)</span>
                <span class="ai-badge">🟠 NVIDIA NIM (Code Validation & Fixing)</span>
            </div>
            <p class="timestamp">Generated: """ + str(__import__("datetime").datetime.now()) + """</p>
        </div>
        """
        
        for item in partial_fails:
            coin = item["coin"]
            html += '<div class="coin fail">'
            html += '<h2>' + coin + '</h2>'
            html += '<p><strong>Performance Status:</strong> ' + str(item['passed_count']) + '/4 metrics passed</p>'
            
            html += '<h3>📈 Current Metrics:</h3><ul>'
            html += '<li class="metric">Sharpe Ratio: <span class="metric-value">' + str(item['sharpe']) + ' (target: 0.5+)</span></li>'
            html += '<li class="metric">Win Rate: <span class="metric-value">' + str(item['win_rate']) + '% (target: 55%+)</span></li>'
            html += '<li class="metric">Max Drawdown: <span class="metric-value">' + str(item['max_drawdown']) + '% (target: 20% or less)</span></li>'
            html += '<li class="metric">Trade Count: <span class="metric-value">' + str(item['trades']) + ' (target: 5+)</span></li>'
            html += '</ul>'
            
            html += '<div class="pipeline-status">'
            html += '<strong>🔄 AI Pipeline Status:</strong><br/>'
            html += '1️⃣ <strong>Google Gemini</strong>: Generated improved strategy<br/>'
            html += '2️⃣ <strong>NVIDIA NIM</strong>: Validated & fixed code<br/>'
            html += 'Failed metrics: <code>' + ', '.join(item['failed_metrics']) + '</code>'
            html += '</div>'
            
            if coin in improved_strategies:
                html += '<div class="validated">'
                html += '<h3>✅ AI-Improved & Validated Strategy:</h3>'
                html += '<pre><code>' + improved_strategies[coin] + '</code></pre>'
                html += '<p><em>Strategy generated by Google Gemini and validated by NVIDIA NIM (Llama 3.1 70B)</em></p>'
                html += '</div>'
            
            html += '</div>'
        
        html += """
        <footer style="margin-top: 40px; padding-top: 20px; border-top: 2px solid #ddd; color: #666; font-size: 0.9em;">
            <p>📚 <strong>Research References:</strong></p>
            <ul>
                <li>Sharpe, William F. "The Sharpe Ratio." The Journal of Portfolio Management (1994)</li>
                <li>Taleb, Nassim N. "Fooled by Randomness" (2001)</li>
                <li>"A Post-Modern Portfolio Theory" - Perry & Shrikhande</li>
                <li>Alpaydin, Ethem. "Machine Learning for Trading" (2021)</li>
            </ul>
            <p>🤖 <strong>AI Stack:</strong></p>
            <ul>
                <li><strong>Code Generation:</strong> Google Gemini 2.0 Flash</li>
                <li><strong>Code Validation & Fixing:</strong> NVIDIA NIM - Llama 3.1 70B</li>
            </ul>
            <p>Deployed on Railway.com - Scalable Quantitative Trading Research</p>
        </footer>
        </body>
        </html>
        """
        
        filename = "strategy_improvements_report.html"
        with open(filename, "w") as f:
            f.write(html)
        
        print("[REPORT] Generated: " + filename, flush=True)
        return filename
        
    except Exception as e:
        print("[REPORT] Failed to generate report: " + str(e), flush=True)
        return None
