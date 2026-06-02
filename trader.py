import ccxt
import time
import os

API_KEY = os.environ.get("COINDCX_API_KEY")
API_SECRET = os.environ.get("COINDCX_SECRET")

exchange = ccxt.coindcx({
    'apiKey': API_KEY,
    'secret': API_SECRET,
})

# how much of your balance to use per trade (30%)
TRADE_PERCENT = 0.30

def get_balance():
    try:
        balance = exchange.fetch_balance()
        inr = balance['INR']['free']
        print(f"Available balance: ₹{round(inr, 2)}")
        return inr
    except Exception as e:
        print(f"Balance fetch failed: {e}")
        return 0

def place_buy(coin, inr_amount):
    try:
        ticker = exchange.fetch_ticker(coin)
        price = ticker['last']
        amount = inr_amount / price
        amount = round(amount, 6)

        order = exchange.create_market_buy_order(coin, amount)
        print(f"BUY {coin} → ₹{round(inr_amount, 2)} at ₹{price}")
        return order
    except Exception as e:
        print(f"Buy failed for {coin}: {e}")
        return None

def place_sell(coin):
    try:
        balance = exchange.fetch_balance()
        symbol = coin.split('/')[0]
        amount = balance[symbol]['free']

        if amount <= 0:
            print(f"Nothing to sell for {coin}")
            return None

        order = exchange.create_market_sell_order(coin, amount)
        print(f"SELL {coin} → {amount} units")
        return order
    except Exception as e:
        print(f"Sell failed for {coin}: {e}")
        return None

def execute_strategy(strategy_code, all_data, good_coins):
    if not good_coins:
        print("No approved coins to trade")
        return {}

    local_env = {}
    exec(strategy_code, local_env)
    get_signals = local_env['get_signals']

    inr_balance = get_balance()
    if inr_balance < 100:
        print("Balance too low to trade")
        return {}

    trade_amount = inr_balance * TRADE_PERCENT
    results = {}

    for coin in good_coins:
        try:
            df = all_data[coin]
            signals = get_signals(df)
            last_signal = signals.iloc[-1]

            if last_signal == 1:
                print(f"Signal: BUY {coin}")
                order = place_buy(coin, trade_amount)
                results[coin] = {'action': 'buy', 'order': order}

                # auto stop loss at 5% below entry
                ticker = exchange.fetch_ticker(coin)
                entry_price = ticker['last']
                stop_loss = round(entry_price * 0.95, 2)
                print(f"Stop loss set mentally at ₹{stop_loss}")
                results[coin]['stop_loss'] = stop_loss

            elif last_signal == -1:
                print(f"Signal: SELL {coin}")
                order = place_sell(coin)
                results[coin] = {'action': 'sell', 'order': order}

            else:
                print(f"Signal: HOLD {coin}")
                results[coin] = {'action': 'hold', 'order': None}

            time.sleep(1)

        except Exception as e:
            print(f"Trade execution failed for {coin}: {e}")

    return results
