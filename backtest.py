import pandas as pd
import numpy as np

def run_backtest(strategy_code, all_data):
    results = {}
    
    for coin, df in all_data.items():
        try:
            # run the AI generated strategy code
            local_env = {}
            exec(strategy_code, local_env)
            get_signals = local_env['get_signals']
            
            # get buy/sell signals
            signals = get_signals(df)
            
            # simulate trades
            capital = 10000
            position = 0
            trades = []
            equity_curve = [capital]
            peak = capital
            max_drawdown = 0
            
            for i in range(1, len(signals)):
                price = df['close'].iloc[i]
                
                if signals.iloc[i] == 1 and position == 0:
                    # buy
                    position = capital / price
                    buy_price = price

                elif signals.iloc[i] == -1 and position > 0:
                    # sell
                    sell_value = position * price
                    profit = sell_value - capital
                    trades.append(profit)
                    capital = sell_value
                    position = 0

                # track equity and drawdown
                current_equity = capital + (position * price if position > 0 else 0)
                equity_curve.append(current_equity)
                if current_equity > peak:
                    peak = current_equity
                drawdown = ((peak - current_equity) / peak) * 100
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

            if len(trades) == 0:
                results[coin] = {
                    'sharpe': 0,
                    'win_rate': 0,
                    'max_drawdown': 100,
                    'trades': 0,
                    'passed': False
                }
                continue

            # score the strategy
            trades_arr = np.array(trades)
            win_rate = round(len(trades_arr[trades_arr > 0]) / len(trades_arr) * 100, 1)
            avg = np.mean(trades_arr)
            std = np.std(trades_arr)
            sharpe = round(avg / std if std > 0 else 0, 2)
            max_drawdown = round(max_drawdown, 2)

            passed = (
                sharpe >= 2.0 and
                win_rate >= 65.0 and
                max_drawdown <= 15.0 and
                len(trades) >= 5
            )

            results[coin] = {
                'sharpe': sharpe,
                'win_rate': win_rate,
                'max_drawdown': max_drawdown,
                'trades': len(trades),
                'passed': passed
            }

            status = "PASS" if passed else "FAIL"
            print(f"{coin} [{status}] → Sharpe: {sharpe} | Win rate: {win_rate}% | Drawdown: {max_drawdown}% | Trades: {len(trades)}")

        except Exception as e:
            print(f"Backtest failed for {coin}: {e}")
            results[coin] = {
                'sharpe': 0,
                'win_rate': 0,
                'max_drawdown': 100,
                'trades': 0,
                'passed': False
            }

    return results

def is_strategy_good(results):
    good_coins = []
    for coin, score in results.items():
        if score['passed']:
            good_coins.append(coin)
            print(f"{coin} approved for live trading")
    if not good_coins:
        print("No coins passed — agent will regenerate strategy")
    return good_coins
