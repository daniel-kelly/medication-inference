import requests
import json
import time
import os
import yaml

# Load parameters from YAML
with open("params.yaml", "r") as f:
    config = yaml.safe_load(f)

API_KEY = config["api_key"]
BATCH_SIZE = config["batch_size"]
MAX_REQUESTS_PER_MIN = config["max_requests_per_min"]
CHECKPOINT_FILE = config["checkpoint_file"]
OUTPUT_DIR = config["output_dir"]
ESSENTIAL_FIELDS = set(config["essential_fields"])

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load or initialize checkpoint
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r") as f:
        checkpoint = json.load(f)
    skip = checkpoint.get("skip", 0)
else:
    skip = 0

requests_made = 0

def get_field(entry, field):
    # Try top-level field, then openfda subfield
    value = entry.get(field)
    if value is None and "openfda" in entry:
        value = entry["openfda"].get(field)
    return value

def clean_entry(entry):
    # Pull all essential fields from top-level and openfda
    cleaned = {}
    for field in ESSENTIAL_FIELDS:
        value = get_field(entry, field)
        if value is not None:
            cleaned[field] = value

    # Require at least one known name field
    name_fields = ['generic_name', 'brand_name', 'substance_name']
    has_valid_name = False
    for field in name_fields:
        value = get_field(entry, field)
        if value:
            values = value if isinstance(value, list) else [value]
            if any(str(v).strip().lower() != "unknown" for v in values):
                has_valid_name = True
                break

    if not has_valid_name:
        return None

    return cleaned

# Main loop
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

        saved_count = 0

        for entry in results:
            cleaned = clean_entry(entry)
            if not cleaned:
                continue

            routes = get_field(entry, "route") or ["unknown"]
            if not isinstance(routes, list):
                routes = [routes]

            for route in routes:
                route = route.lower().replace("/", "_").replace(" ", "_")
                output_path = os.path.join(OUTPUT_DIR, f"{route}.jsonl")
                with open(output_path, "a", encoding="utf-8") as f_out:
                    f_out.write(json.dumps(cleaned) + "\n")
                saved_count += 1

        skip += BATCH_SIZE
        requests_made += 1

        # Save checkpoint
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump({"skip": skip}, f)

        print(f"Fetched {len(results)} items, saved {saved_count}. Total so far: {skip}")

        if requests_made % MAX_REQUESTS_PER_MIN == 0:
            print("Rate limit hit. Sleeping 60 seconds...")
            time.sleep(60)

    except requests.exceptions.HTTPError as e:
        if res.status_code == 400:
            print("Reached end of available data (400 error). Exiting.")
            break
        print("HTTP error occurred:", e)
        print("Sleeping 30 seconds and retrying...")
        time.sleep(30)
