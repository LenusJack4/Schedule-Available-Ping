import time
import json
import os
import re
from dotenv import load_dotenv
from datetime import datetime

import requests
from playwright.sync_api import sync_playwright

# =========== Configuration ===========

SIGNUP_URL = "https://signup.com/mobileweb/2.0/vspot.html?activitykey=117003059258628037#choose_event_page"

CHECK_INTERVAL_SECONDS = 60  # Check every 1 minute

load_dotenv()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

STATE_FILE = "month_list_state.json"

MONTH_PATTERN = re.compile(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b')

# =========== Helper Functions ===========

def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "visible_months": [],   # months currently visible on the page
            "alerted_months": []    # months for which alerts have been sent
        }
    with open(STATE_FILE, "r") as f:
        return json.load(f)
    
def save_state(state):
    with open(STATE_FILE, "w") as f:
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

def prune_alerted_months(alerted_months):
    # Keep only months within the last 2 years to prevent infinite growth.
    current_year = datetime.now().year
    pruned = []
    for m in alerted_months:
        # month labels look like "January 2026"
        try:
            month_name, year_str = m.split()
            year = int(year_str)
            if year >= current_year - 2:
                pruned.append(m)
        except:
            # if parsing fails, keep it to be safe
            pruned.append(m)
    return sorted(set(pruned))

# =========== Main Logic ===========

def extract_month_labels(page_text: str):
    return sorted({m.group(0) for m in MONTH_PATTERN.finditer(page_text)})

def check_for_new_months(page, state):
    page.goto(SIGNUP_URL)
    page_text = page.inner_text("body")

    current_months = extract_month_labels(page_text)
    if not current_months:
        print(f"[{datetime.now()}] No month labels found on the page.")
        return
    
    current_months_set = set(current_months)
    print(f"[{datetime.now()}] Current months found: {current_months}")

    visible_months = set(state.get("visible_months", []))
    alerted_months = set(state.get("alerted_months", []))

    # First time run, initialize known months with no alert
    if not visible_months and not alerted_months:
        state["visible_months"] = current_months
        state["alerted_months"] = []    # No alerts sent yet
        save_state(state)
        print(f"[{datetime.now()}] Initialized visible months: {current_months}. No alert.")
        return
    
    # Months that are newly visible *and* have never been alerted
    new_months = current_months_set - alerted_months

    if new_months:
        print(f"[{datetime.now()}] New month detected: {new_months}")
        send_discord_notification(new_months)
        
        # Add them to alerted history
        alerted_months |= new_months
        alerted_months = prune_alerted_months(alerted_months)

        # Update state. Visible months are always current months. Alerted months keeps all months we've alerted on.
        state["visible_months"] = sorted(current_months_set)
        state["alerted_months"] = sorted(alerted_months)
        save_state(state)
    else:
        print(f"[{datetime.now()}] No new months detected.")

def main():
    state = load_state()

    print(f"[{datetime.now()}] Starting month list watch bot...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
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