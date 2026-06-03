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
                
               sig = int(signals.iloc[i])
                if sig == 1 and position == 0:
                    position = capital / price
                    buy_price = price

                elif sig == -1 and position > 0:
                    sell_value = position * price
                    profit = sell_value - capital
                    trades.append(profit)
                    capital = sell_value
                    position = 0

                current_equity = capital + (position * price if position > 0 else 0)
                equity_curve.append(current_equity)
                if current_equity > peak:
                    peak = current_equity
                drawdown = ((peak - current_equity) / peak) * 100
                if drawdown > max_drawdown:
                    max_drawdown = drawdown 
