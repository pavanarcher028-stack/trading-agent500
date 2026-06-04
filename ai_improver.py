import anthropic
import json
import os


def improve_strategy_with_ai(strategy_code, feedback_list, coin):
    """
    Use Claude AI to improve the strategy based on feedback
    Requires ANTHROPIC_API_KEY environment variable
    """
    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("[AI] ANTHROPIC_API_KEY not set. Skipping AI improvement.", flush=True)
            return None
        
        client = anthropic.Anthropic(api_key=api_key)
        
        feedback_text = "\n".join(feedback_list)
        
        prompt = f"""You are a professional trading strategy optimizer.

Current Strategy Code:
```python
{strategy_code}
```

Performance Feedback:
{feedback_text}

Your task:
1. Analyze why the strategy is failing on these specific metrics
2. Propose improvements ONLY to fix the failed metrics
3. Keep the successful parts of the strategy
4. Return ONLY valid Python code in a function called 'get_signals(df)' that takes a DataFrame and returns trading signals (-1, 0, 1)

Requirements:
- Input: df with columns ['open', 'high', 'low', 'close', 'volume']
- Output: pd.Series of signals (-1 for sell, 0 for hold, 1 for buy)
- Must use pandas and numpy
- Do NOT include test code or main execution
- Focus on improving the failed metrics

Improved Strategy Code:
```python
def get_signals(df):
    import pandas as pd
    import numpy as np
    # Your improved implementation here
```"""

        print("[AI] Sending strategy to Claude for improvement...", flush=True)
        
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        improved_code = message.content[0].text
        
        # Extract Python code from response
        if "```python" in improved_code:
            start = improved_code.find("```python") + 9
            end = improved_code.find("```", start)
            improved_code = improved_code[start:end].strip()
        
        print("[AI] Strategy improvement for " + coin + " generated successfully", flush=True)
        
        # Save improved strategy to file
        save_improved_strategy(coin, improved_code, feedback_text)
        
        return improved_code
        
    except ImportError:
        print("[AI] anthropic library not installed. Install with: pip install anthropic", flush=True)
        return None
    except Exception as e:
        print("[AI] Error during strategy improvement: " + str(e), flush=True)
        return None


def save_improved_strategy(coin, strategy_code, feedback):
    """Save improved strategy to file for reference"""
    try:
        filename = "improved_strategies_" + coin + ".json"
        
        data = {
            "coin": coin,
            "timestamp": str(__import__("datetime").datetime.now()),
            "feedback": feedback,
            "improved_strategy": strategy_code
        }
        
        improvements = []
        if os.path.exists(filename):
            with open(filename, "r") as f:
                improvements = json.load(f)
        
        improvements.append(data)
        
        with open(filename, "w") as f:
            json.dump(improvements, f, indent=2)
        
        print("[AI] Saved improved strategy for " + coin + " to " + filename, flush=True)
    except Exception as e:
        print("[AI] Failed to save improved strategy: " + str(e), flush=True)


def batch_improve_strategies(partial_fails, strategy_code):
    """
    Improve multiple strategies based on feedback
    Returns dict of {coin: improved_code}
    """
    improved_strategies = {}
    
    for item in partial_fails:
        coin = item["coin"]
        print("\n[AI] Improving strategy for " + coin + "...", flush=True)
        
        feedback = get_ai_feedback_for_coin(item)
        improved = improve_strategy_with_ai(strategy_code, feedback, coin)
        
        if improved:
            improved_strategies[coin] = improved
    
    return improved_strategies


def get_ai_feedback_for_coin(item):
    """Format feedback for a single coin"""
    feedback = []
    feedback.append("[" + item['coin'] + " PERFORMANCE ANALYSIS]")
    feedback.append("Passed: " + str(item['passed_count']) + "/4 metrics")
    feedback.append("Current Results:")
    feedback.append("  - Sharpe Ratio: " + str(item['sharpe']) + " (target: >= 0.5)")
    feedback.append("  - Win Rate: " + str(item['win_rate']) + "% (target: >= 55%)")
    feedback.append("  - Max Drawdown: " + str(item['max_drawdown']) + "% (target: <= 20%)")
    feedback.append("  - Trade Count: " + str(item['trades']) + " (target: >= 5)")
    
    feedback.append("\nMetrics Failing:")
    for metric in item['failed_metrics']:
        if metric == "sharpe":
            feedback.append("  - Sharpe Ratio is too low. Improve entry/exit signal quality.")
        elif metric == "win_rate":
            feedback.append("  - Win rate is too low. Enhance signal accuracy to reduce false positives.")
        elif metric == "max_drawdown":
            feedback.append("  - Drawdown is too high. Add better risk management or stop-loss logic.")
        elif metric == "trades_count":
            feedback.append("  - Not enough trades generated. Make signals trigger more frequently.")
    
    return feedback


def generate_html_report(partial_fails, improved_strategies):
    """Generate an HTML report of improvements"""
    try:
        html = """
        <html>
        <head>
            <title>Trading Strategy Improvements Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .coin { border: 1px solid #ccc; padding: 15px; margin: 10px 0; border-radius: 5px; }
                .pass { background-color: #d4edda; }
                .fail { background-color: #f8d7da; }
                .metric { margin: 5px 0; }
                code { background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }
            </style>
        </head>
        <body>
        <h1>Strategy Improvement Report</h1>
        """
        
        for item in partial_fails:
            coin = item["coin"]
            html += '<div class="coin fail">'
            html += '<h2>' + coin + '</h2>'
            html += '<p>Passed: ' + str(item['passed_count']) + '/4 metrics</p>'
            html += '<h3>Metrics:</h3><ul>'
            html += '<li>Sharpe: ' + str(item['sharpe']) + ' (target: 0.5+)</li>'
            html += '<li>Win Rate: ' + str(item['win_rate']) + '% (target: 55%+)</li>'
            html += '<li>Max Drawdown: ' + str(item['max_drawdown']) + '% (target: 20% or less)</li>'
            html += '<li>Trades: ' + str(item['trades']) + ' (target: 5+)</li>'
            html += '</ul>'
            
            if coin in improved_strategies:
                html += '<h3>AI-Improved Strategy:</h3>'
                html += '<pre><code>' + improved_strategies[coin] + '</code></pre>'
            
            html += '</div>'
        
        html += """
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
