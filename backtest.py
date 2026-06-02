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
            
            if len(trades) == 0:
                results[coin] = {'sharpe': 0, 'win_rate': 0, 'trades': 0}
                continue
            
            # score the strategy
            trades = np.array(trades)
            win_rate = round(len(trades[trades > 0]) / len(trades) * 100, 1)
            avg = np.mean(trades)
            std = np.std(trades)
            sharpe = round(avg / std if std > 0 else 0, 2)
            
            results[coin] = {
                'sharpe': sharpe,
                'win_rate': win_rate,
                'trades': len(trades)
            }
            print(f"{coin} → Sharpe: {sharpe}, Win rate: {win_rate}%, Trades: {len(trades)}")
            
        except Exception as e:
            print(f"Backtest failed for {coin}: {e}")
            results[coin] = {'sharpe': 0, 'win_rate': 0, 'trades': 0}
    
    return results

def is_strategy_good(results):
    good_coins = []
    for coin, score in results.items():
        if score['sharpe'] > 0.5 and score['win_rate'] > 45 and score['trades'] >= 5:
            good_coins.append(coin)
    return good_coins
