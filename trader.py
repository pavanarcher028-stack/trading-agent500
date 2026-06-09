import requests
import hmac
import hashlib
import time
import os
import json
import re
import threading

API_KEY = os.environ.get("COINDCX_API_KEY")
API_SECRET = os.environ.get("COINDCX_SECRET")

BASE_URL = "https://api.coindcx.com"

COIN_MAP = {
    "BTC": "BTCINR",
    "ETH": "ETHINR",
    "BNB": "BNBINR",
    "SOL": "SOLUSDT",
    "XRP": "XRPINR"
}

TRADE_PERCENT = 0.10
MIN_TRADE = 110
MAX_TRADE = 500

POSITIONS_FILE = "positions.json"
positions_lock = threading.Lock()
_balance_cache = {"value": None, "time": 0}
_balance_cache_lock = threading.Lock()

def sign_request(body_dict):
    if not API_KEY or not API_SECRET:
        raise ValueError("CoinDCX API keys not configured")
    json_body = json.dumps(body_dict, separators=(",", ":"))
    signature = hmac.new(
        bytes(API_SECRET, "utf-8"),
        msg=bytes(json_body, "utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-AUTH-APIKEY": API_KEY,
        "X-AUTH-SIGNATURE": signature
    }
    return json_body, headers

def load_positions():
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_positions(positions):
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2)

def get_balance():
    now = time.time()
    with _balance_cache_lock:
        if _balance_cache["value"] is not None and now - _balance_cache["time"] < 60:
            return _balance_cache["value"]
    try:
        timestamp = int(round(time.time() * 1000))
        json_body, headers = sign_request({"timestamp": timestamp})
        response = requests.post(
            BASE_URL + "/exchange/v1/users/balances",
            data=json_body,
            headers=headers,
            timeout=10
        )
        resp = response.json()
        if isinstance(resp, dict):
            balances = resp.get("data", resp.get("balances", []))
        else:
            balances = resp
        for b in balances:
            if not isinstance(b, dict):
                continue
            if b.get("currency") == "INR":
                inr = float(b.get("balance", 0))
                print("[TRADER] INR balance: Rs." + str(round(inr, 2)), flush=True)
                with _balance_cache_lock:
                    _balance_cache["value"] = inr
                    _balance_cache["time"] = now
                return inr
        print("[TRADER] No INR balance found in API response: " + json.dumps(balances)[:300], flush=True)
        with _balance_cache_lock:
            _balance_cache["value"] = 0
            _balance_cache["time"] = now
        return 0
    except Exception as e:
        print("[TRADER] Balance fetch failed: " + str(e), flush=True)
        with _balance_cache_lock:
            _balance_cache["value"] = 0
            _balance_cache["time"] = now
        return 0

def get_coin_balance(symbol):
    try:
        timestamp = int(round(time.time() * 1000))
        json_body, headers = sign_request({"timestamp": timestamp})
        response = requests.post(
            BASE_URL + "/exchange/v1/users/balances",
            data=json_body,
            headers=headers
        )
        resp = response.json()
        if isinstance(resp, dict):
            balances = resp.get("data", resp.get("balances", []))
        else:
            balances = resp
        for b in balances:
            if not isinstance(b, dict):
                continue
            if b.get("currency") == symbol:
                amount = float(b.get("balance", 0))
                print("[TRADER] " + symbol + " balance: " + str(amount), flush=True)
                return amount
        return 0
    except Exception as e:
        print("[TRADER] Coin balance fetch failed: " + str(e), flush=True)
        return 0

def place_order(side, coin_symbol, quantity):
    try:
        timestamp = int(round(time.time() * 1000))
        body = {
            "side": side,
            "order_type": "market_order",
            "market": coin_symbol,
            "quantity": quantity,
            "timestamp": timestamp
        }
        json_body, headers = sign_request(body)
        response = requests.post(
            BASE_URL + "/exchange/v1/orders/create",
            data=json_body,
            headers=headers
        )
        result = response.json()
        print("[TRADER] " + side.upper() + " " + coin_symbol + " qty=" + str(quantity) + " result=" + str(result), flush=True)
        return result
    except Exception as e:
        print("[TRADER] Order failed " + coin_symbol + ": " + str(e), flush=True)
        return None

def parse_sl_tp(strategy_code):
    sl_pct = 3.0
    tp_pct = 6.0
    sl_match = re.search(r'SL_PCT\s*=\s*([\d.]+)', strategy_code)
    tp_match = re.search(r'TP_PCT\s*=\s*([\d.]+)', strategy_code)
    if sl_match:
        sl_pct = float(sl_match.group(1))
    if tp_match:
        tp_pct = float(tp_match.group(1))
    print("[TRADER] SL=" + str(sl_pct) + "% TP=" + str(tp_pct) + "%", flush=True)
    return sl_pct, tp_pct

def check_and_close_positions(all_data):
    positions = load_positions()
    if not positions:
        return
    to_remove = []
    for coin, pos in positions.items():
        try:
            if coin not in all_data:
                continue
            current_price = float(all_data[coin]["close"].iloc[-1])
            entry = pos["entry_price"]
            sl_pct = pos["sl_pct"]
            tp_pct = pos["tp_pct"]
            pct_change = (current_price - entry) / entry * 100.0
            coin_symbol = COIN_MAP.get(coin)
            if pct_change <= -sl_pct:
                print("[TRADER] SL HIT " + coin + " (" + str(round(pct_change, 2)) + "%)", flush=True)
                if coin_symbol:
                    place_order("sell", coin_symbol, pos["quantity"])
                to_remove.append(coin)
                from monitor import record_trade
                record_trade(coin, "sell", entry, current_price, pos["quantity"])
            elif pct_change >= tp_pct:
                print("[TRADER] TP HIT " + coin + " (" + str(round(pct_change, 2)) + "%)", flush=True)
                if coin_symbol:
                    place_order("sell", coin_symbol, pos["quantity"])
                to_remove.append(coin)
                from monitor import record_trade
                record_trade(coin, "sell", entry, current_price, pos["quantity"])
            else:
                print("[TRADER] " + coin + " PnL: " + str(round(pct_change, 2)) + "% (SL:" + str(sl_pct) + "% TP:" + str(tp_pct) + "%)", flush=True)
        except Exception as e:
            print("[TRADER] Position check error " + coin + ": " + str(e), flush=True)
    if to_remove:
        with positions_lock:
            positions = load_positions()
            for c in to_remove:
                positions.pop(c, None)
            save_positions(positions)

def execute_strategy(strategy_code, all_data, good_coins):
    check_and_close_positions(all_data)
    if not good_coins:
        print("[TRADER] No approved coins to trade", flush=True)
        return {}
    local_env = {}
    exec(strategy_code, local_env)
    get_signals = local_env["get_signals"]
    sl_pct, tp_pct = parse_sl_tp(strategy_code)
    inr_balance = get_balance()
    if inr_balance < MIN_TRADE:
        print("[TRADER] Balance too low - need at least Rs." + str(MIN_TRADE), flush=True)
        return {}
    trade_amount = inr_balance * TRADE_PERCENT
    if trade_amount < MIN_TRADE:
        trade_amount = MIN_TRADE
    if trade_amount > MAX_TRADE:
        trade_amount = MAX_TRADE
    print("[TRADER] Trade amount: Rs." + str(round(trade_amount, 2)), flush=True)
    results = {}
    for coin in good_coins:
        try:
            df = all_data[coin]
            signals = get_signals(df)
            last_signal = int(signals.iloc[-1])
            coin_symbol = COIN_MAP.get(coin)
            if not coin_symbol:
                print("[TRADER] No pair for " + coin, flush=True)
                continue
            current_price = float(df["close"].iloc[-1])
            positions = load_positions()
            if last_signal == 1 and coin not in positions:
                quantity = round(trade_amount / current_price, 6)
                print("[TRADER] BUY " + coin + " qty=" + str(quantity) + " at Rs." + str(round(current_price, 2)), flush=True)
                order = place_order("buy", coin_symbol, quantity)
                if order and "id" in order:
                    with positions_lock:
                        pos = load_positions()
                        pos[coin] = {
                            "entry_price": current_price,
                            "quantity": quantity,
                            "sl_pct": sl_pct,
                            "tp_pct": tp_pct,
                            "entry_time": time.time()
                        }
                        save_positions(pos)
                    print("[TRADER] Position opened for " + coin + " @ Rs." + str(round(current_price, 2)) + " SL:" + str(sl_pct) + "% TP:" + str(tp_pct) + "%", flush=True)
                results[coin] = {"action": "buy", "order": order, "price": current_price, "quantity": quantity}
            elif coin in positions:
                print("[TRADER] HOLD " + coin + " (position open, waiting for SL/TP)", flush=True)
                results[coin] = {"action": "hold", "order": None}
            else:
                print("[TRADER] HOLD " + coin, flush=True)
                results[coin] = {"action": "hold", "order": None}
            time.sleep(1)
        except Exception as e:
            print("[TRADER] Error for " + coin + ": " + str(e), flush=True)
    return results