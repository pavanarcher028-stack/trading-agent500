import os
import json
import requests

RAILWAY_TOKEN = os.environ.get("RAILWAY_TOKEN")
RAILWAY_PROJECT_ID = os.environ.get("RAILWAY_PROJECT_ID")
RAILWAY_ENV_ID = os.environ.get("RAILWAY_ENV_ID")
RAILWAY_SERVICE_ID = os.environ.get("RAILWAY_SERVICE_ID")
STORE_FILE = "strategy_store.json"


def save_to_file(data):
    try:
        with open(STORE_FILE, "w") as f:
            json.dump(data, f)
        print("[STORE] Saved to file", flush=True)
    except Exception as e:
        print("[STORE] File save failed: " + str(e), flush=True)


def load_from_file():
    try:
        if os.path.exists(STORE_FILE):
            with open(STORE_FILE, "r") as f:
                data = json.load(f)
            return data
    except Exception as e:
        print("[STORE] File load failed: " + str(e), flush=True)
    return None


def save_to_env(data):
    try:
        if not RAILWAY_TOKEN or not RAILWAY_PROJECT_ID:
            return False
        strategy_json = json.dumps(data)
        query = """
        mutation {
            variableUpsert(input: {
                projectId: \"""" + RAILWAY_PROJECT_ID + """\"
                environmentId: \"""" + RAILWAY_ENV_ID + """\"
                serviceId: \"""" + RAILWAY_SERVICE_ID + """\"
                name: "SAVED_STRATEGY"
                value: """ + json.dumps(strategy_json) + """
            })
        }
        """
        r = requests.post(
            "https://backboard.railway.app/graphql/v2",
            headers={
                "Authorization": "Bearer " + RAILWAY_TOKEN,
                "Content-Type": "application/json"
            },
            json={"query": query},
            timeout=10
        )
        if r.status_code == 200:
            print("[STORE] Saved to Railway env vars", flush=True)
            return True
        return False
    except Exception as e:
        print("[STORE] Env save failed: " + str(e), flush=True)
        return False


def load_from_env():
    try:
        saved = os.environ.get("SAVED_STRATEGY")
        if saved:
            data = json.loads(saved)
            print("[STORE] Loaded from Railway env vars", flush=True)
            return data
    except Exception as e:
        print("[STORE] Env load failed: " + str(e), flush=True)
    return None


def save_strategy(strategy_code, good_coins):
    data = {
        "strategy_code": strategy_code,
        "good_coins": good_coins
    }
    save_to_file(data)
    save_to_env(data)
    print("[STORE] Strategy saved for coins: " + str(good_coins), flush=True)


def load_strategy():
    data = load_from_env()
    if not data:
        data = load_from_file()
    if data:
        print("[STORE] Loaded strategy for coins: " + str(data.get("good_coins", [])), flush=True)
        return data["strategy_code"], data["good_coins"]
    print("[STORE] No saved strategy found", flush=True)
    return None, []


def clear_strategy():
    if os.path.exists(STORE_FILE):
        os.remove(STORE_FILE)
    print("[STORE] Strategy cleared", flush=True)
