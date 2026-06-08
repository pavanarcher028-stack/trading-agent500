import sys
import os
import time
import threading
import random
import log_capture; log_capture.install()
from api import start_api
from strategy_store import save_strategy, load_strategy
from data import get_top5_ohlcv, get_market_summary
from backtest import run_backtest, is_strategy_good, get_metric_statistics
from trader import execute_strategy
from monitor import needs_regeneration, bump_strategy_version, get_performance_summary
from ai_improver import (
    batch_improve_and_validate_strategies, generate_html_report,
    call_gemini, call_nvidia_for_improvement,
    generate_unique_strategy, build_generation_prompt,
    improve_strategy_with_google_ai
)
from data import get_market_summary

print("TRADING AGENT STARTED", flush=True)

active_strategy = None
active_good_coins = []
lock = threading.Lock()
trade_count = 0
revalidate_every = random.randint(10, 20)

def generate_ai_strategy(coin, all_data, market_summary):
    print("[AI] Generating strategy for " + coin + " with Gemini...", flush=True)
    prompt = build_generation_prompt(market_summary, [coin])
    code = generate_unique_strategy(call_gemini, prompt, coin, None, max_retries=3)
    if code:
        return code
    print("[AI] Gemini failed for " + coin + " - trying NVIDIA...", flush=True)
    nvidia_code = generate_unique_strategy(call_nvidia_for_improvement, prompt, coin, None, max_retries=3)
    if nvidia_code:
        return nvidia_code
    return None


def search_strategy(all_data, coins):
    global active_strategy, active_good_coins
    market_summary = get_market_summary(all_data)
    print("[SEARCH] Generating AI strategies for: " + str(coins), flush=True)
    for coin in coins:
        try:
            if coin in active_good_coins:
                continue
            print("[SEARCH] Generating strategy for " + coin + "...", flush=True)
            code = generate_ai_strategy(coin, all_data, market_summary)
            if not code:
                print("[SEARCH] AI failed to generate for " + coin + " - skipping", flush=True)
                continue
            subset = {coin: all_data[coin]} if coin in all_data else {}
            if not subset:
                continue
            results = run_backtest(code, subset)
            good_coins, partial_fails = is_strategy_good(results)
            if coin in good_coins:
                with lock:
                    active_good_coins.append(coin)
                    active_strategy = code
                    save_strategy(code, active_good_coins)
                print("[SEARCH] AI strategy approved for " + coin, flush=True)
            elif partial_fails:
                print("[SEARCH] " + coin + " partially passed - improving with AI...", flush=True)
                improved = batch_improve_and_validate_strategies(partial_fails, code, all_data)
                if improved and coin in improved:
                    with lock:
                        if coin not in active_good_coins:
                            active_good_coins.append(coin)
                            active_strategy = improved[coin]
                            save_strategy(improved[coin], active_good_coins)
                    print("[SEARCH] AI improved strategy approved for " + coin, flush=True)
            else:
                print("[SEARCH] AI strategy failed all metrics for " + coin, flush=True)
        except Exception as e:
            print("[SEARCH] Error for " + coin + ": " + str(e), flush=True)
    remaining = [c for c in coins if c not in active_good_coins]
    if remaining:
        print("[SEARCH] No passing strategy for: " + str(remaining), flush=True)
    print("[SEARCH] Done. Active: " + str(active_good_coins), flush=True)


def revalidate(all_data):
    global active_strategy, active_good_coins, trade_count, revalidate_every
    print("[REVALIDATE] Re-testing strategy...", flush=True)
    with lock:
        strat = active_strategy
        coins = list(active_good_coins)
    if not strat or not coins:
        return
    subset_data = {c: all_data[c] for c in coins if c in all_data}
    results = run_backtest(strat, subset_data)
    still_good, partial_fails = is_strategy_good(results)
    failed_coins = [c for c in coins if c not in still_good]
    if failed_coins:
        print("[REVALIDATE] " + str(failed_coins) + " failed searching new strategy", flush=True)
        with lock:
            for c in failed_coins:
                if c in active_good_coins:
                    active_good_coins.remove(c)
            save_strategy(active_strategy, active_good_coins)
        threading.Thread(
            target=search_strategy,
            args=(all_data, failed_coins),
            daemon=True
        ).start()
    else:
        print("[REVALIDATE] All coins still passing", flush=True)
    trade_count = 0
    revalidate_every = random.randint(10, 20)
    print("[REVALIDATE] Next check in " + str(revalidate_every) + " trades", flush=True)


def trading_loop(all_data):
    global trade_count
    while True:
        try:
            with lock:
                strat = active_strategy
                coins = list(active_good_coins)
            if strat and coins:
                print("[TRADER] Trading: " + str(coins), flush=True)
                execute_strategy(strat, all_data, coins)
                trade_count += 1
                get_performance_summary()
                print("[TRADER] Trade " + str(trade_count) + " done. Revalidate at " + str(revalidate_every), flush=True)
                if trade_count >= revalidate_every:
                    revalidate(all_data)
                time.sleep(3600)
            else:
                print("[TRADER] Waiting for approved coins...", flush=True)
                time.sleep(300)
        except Exception as e:
            print("[TRADER] Error: " + str(e), flush=True)
            time.sleep(300)


def run_agent():
    global active_strategy, active_good_coins
    threading.Thread(target=start_api, daemon=True).start()
    if not os.environ.get("COINDCX_API_KEY") or not os.environ.get("COINDCX_SECRET"):
        print("[AGENT] CoinDCX API keys not set - website mode only. Trading disabled.", flush=True)
        while True:
            time.sleep(3600)
        return
    print("[AGENT] All keys found", flush=True)
    print("[AGENT] AI Providers: Google Gemini (Code Gen) + NVIDIA NIM (Validation)", flush=True)
    loop_count = 0
    while True:
        try:
            loop_count += 1
            print("[AGENT] Loop " + str(loop_count), flush=True)
            all_data = get_top5_ohlcv()
            if not all_data:
                print("[AGENT] No data, waiting 10 mins", flush=True)
                time.sleep(600)
                continue
            get_metric_statistics()
            saved_code, saved_coins = load_strategy()
            if saved_code and saved_coins:
                with lock:
                    active_strategy = saved_code
                    active_good_coins = saved_coins
                print("[AGENT] Resuming saved strategy for: " + str(saved_coins), flush=True)
                remaining = [c for c in ["BTC", "ETH", "BNB", "SOL", "XRP"] if c not in saved_coins]
                if remaining:
                    search_thread = threading.Thread(
                        target=search_strategy,
                        args=(all_data, remaining),
                        daemon=True
                    )
                    search_thread.start()
                else:
                    search_thread = None
            else:
                bump_strategy_version()
                active_good_coins = []
                active_strategy = None
                search_thread = threading.Thread(
                    target=search_strategy,
                    args=(all_data, ["BTC", "ETH", "BNB", "SOL", "XRP"]),
                    daemon=True
                )
                search_thread.start()
            threading.Thread(
                target=trading_loop,
                args=(all_data,),
                daemon=True
            ).start()
            if search_thread:
                search_thread.join()
            print("[AGENT] Search done. Sleeping 5 mins", flush=True)
            time.sleep(300)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("[AGENT] Error: " + str(e), flush=True)
            time.sleep(900)


if __name__ == "__main__":
    run_agent()
