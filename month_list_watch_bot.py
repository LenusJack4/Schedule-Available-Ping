import time
import json
import os
import re
from datetime import datetime

import requests
from playwright.sync_api import sync_playwright

# =========== Configuration ===========

SIGNUP_URL = "https://signup.com/mobileweb/2.0/vspot.html?activitykey=117003059258628037#choose_event_page"

CHECK_INTERVAL_SECONDS = 5  # Check every 1 minute (TODO: change back to 60)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1442580508537258014/VQQy_KNI3nzFbivuZpR3E47RZgF2ZDGBfNwJQv1kuHowt6zYWDK-ShBuDAn7obVXwG-j"

STATE_FILE = "month_list_state.json"

MONTH_PATTERN = re.compile(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\b')

# =========== Helper Functions ===========

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"known_months": []}
    with open(STATE_FILE, "r") as f:
        return json.load(f)
    
def save_state(state):
    with open(STATE_FILE, "r") as f:
        json.dump(state, f)

def send_discord_notification(new_months):
    month_list = ", ".join(sorted(new_months))
    message = f"New month available for sign-up: {month_list}"
    payload = {"content": message}
    response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    try:
        response.raise_for_status()
    except Exception as e:
        print(f"[{datetime.now()}] Failed to send Discord notification: {e}")
    else:
        print(f"[{datetime.now()}] Sent Discord notification: {month_list}")

# =========== Main Logic ===========

def extract_month_labels(page_text: str):
    matches = MONTH_PATTERN.findall(page_text)
    return sorted(set(matches))

def check_for_new_months(page, state):
    page.goto(SIGNUP_URL)
    page_text = page.content()

    current_months = extract_month_labels(page_text)
    if not current_months:
        print(f"[{datetime.now()}] No month labels found on the page.")
        return
    
    print(f"[{datetime.now()}] Current months found: {current_months}")

    known_months = set(state.get("known_months", []))

    # First time run, initialize known months with no alert
    if not known_months:
        state["known_months"] = current_months
        save_state(state)
        print(f"[{datetime.now()}] Initialized known months: {current_months}. No alert.")
        return
    
    current_months_set = set(current_months)
    new_months = current_months_set - known_months

    if new_months:
        print(f"[{datetime.now()}] New month detected: {new_months}")
        send_discord_notification(new_months)
        state["known_months"] = sorted(known_months.union(new_months))
        save_state(state)
    else:
        print(f"[{datetime.now()}] No new months detected.")

def main():
    state = load_state()

    print(f"[{datetime.now()}] Starting month list watch bot...")
    print(f"[{datetime.now()}] Known months: {state.get('known_months', [])}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            while True:
                try:
                    check_for_new_months(page, state)
                except Exception as e:
                    print(f"[{datetime.now()}] Error during check: {e}")
                time.sleep(CHECK_INTERVAL_SECONDS)
        finally:
            browser.close()


if __name__ == "__main__":
    main()