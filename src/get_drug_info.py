import requests
import json
import time
import os

API_KEY = "niBOH6xHMCgaizNvXzBuEXWXnkAT3kWcheuKgoht"
BATCH_SIZE = 100
MAX_REQUESTS_PER_MIN = 240
CHECKPOINT_FILE = "../data/checkpoint.json"
OUTPUT_FILE = "../data/raw_fda_labels.jsonl"

# Load or initialize checkpoint
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r") as f:
        checkpoint = json.load(f)
    skip = checkpoint.get("skip", 0)
else:
    skip = 0

requests_made = 0

while True:
    params = {
        "limit": BATCH_SIZE,
        "skip": skip,
        "api_key": API_KEY
    }
    try:
        res = requests.get("https://api.fda.gov/drug/label.json", params=params)
        res.raise_for_status()
        results = res.json().get("results", [])
        if not results:
            print("No more results. Finished.")
            break

        # Write each entry to .jsonl
        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            for item in results:
                f.write(json.dumps(item) + "\n")

        skip += BATCH_SIZE
        requests_made += 1

        # Save checkpoint
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump({"skip": skip}, f)

        print(f"Fetched {len(results)} items. Total so far: {skip}")

        if requests_made % MAX_REQUESTS_PER_MIN == 0:
            print("Rate limit hit. Sleeping 60 seconds...")
            time.sleep(60)


    except requests.exceptions.HTTPError as e:

        if res.status_code == 400:
            print("Reached end of available data (400 error). Exiting.")
            break

        else:

            print("HTTP error occurred:", e)
            print("Sleeping 30 seconds and retrying...")
            time.sleep(30)
