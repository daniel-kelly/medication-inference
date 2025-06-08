import requests
import json
import time
import os
import yaml
from utils import get_field

# Load parameters from YAML
with open("params.yaml", "r") as f:
    config = yaml.safe_load(f)

API_KEY = config["api_key"]
BATCH_SIZE = config["batch_size"]
MAX_REQUESTS_PER_MIN = config["max_requests_per_min"]
CHECKPOINT_FILE = config["checkpoint_file"]
OUTPUT_DIR = config["output_dir"]
ESSENTIAL_FIELDS = set(config["essential_fields"])
ALLOWED_PRODUCT_TYPES = set(config.get("allowed_product_types", []))

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load or initialize checkpoint
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r") as f:
        checkpoint = json.load(f)
    skip = checkpoint.get("skip", 0)
else:
    skip = 0

# NDC cache and written set
ndc_cache = {}
written_ndcs = set()

ALL_NDC_PATH = os.path.join(OUTPUT_DIR, "all_ndcs.jsonl")

def fetch_ndc_data(product_ndc):
    """

    :param product_ndc:
    :return:
    """
    if product_ndc in ndc_cache:
        return ndc_cache[product_ndc]
    url = "https://api.fda.gov/drug/ndc.json"
    params = {
        "search": f"product_ndc:{product_ndc}",
        "limit": 1,
        "api_key": API_KEY
    }
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        results = res.json().get("results", [])
        if results:
            ndc_cache[product_ndc] = results[0]
            return results[0]
    except requests.exceptions.RequestException:
        pass
    ndc_cache[product_ndc] = None
    return None

def clean_and_merge(label_entry, ndc_entry):
    merged = {}
    for field in ESSENTIAL_FIELDS:
        val = get_field(label_entry, field)
        if val is None and ndc_entry:
            val = ndc_entry.get(field)
        if val is not None:
            # If indications_and_usage is a list, flatten it to a string
            if field in ["indications_and_usage", "purpose", "description", "clinical_pharmacology"] and isinstance(val, list):
                val = " ".join(val)
            merged[field] = val

    # Require at least one known name field
    name_fields = ['generic_name', 'brand_name', 'substance_name']
    has_valid_name = False
    for field in name_fields:
        value = merged.get(field)
        if value:
            values = value if isinstance(value, list) else [value]
            if any(str(v).strip().lower() != "unknown" for v in values):
                has_valid_name = True
                break

    return merged if has_valid_name else None


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

        saved_count = 0
        all_count = 0

        with open(ALL_NDC_PATH, "a", encoding="utf-8") as all_out:
            for entry in results:
                product_type = get_field(entry, "product_type")
                if isinstance(product_type, list):
                    product_type = product_type[0]
                if product_type not in ALLOWED_PRODUCT_TYPES:
                    continue

                product_ndc = get_field(entry, "product_ndc")
                product_ndcs = product_ndc if isinstance(product_ndc, list) else [product_ndc]

                ndc_metadata = []
                ndc_entry = None

                for ndc in product_ndcs:
                    if ndc:
                        ndc_data = fetch_ndc_data(ndc)
                        if ndc_data:
                            ndc_metadata.append(ndc_data)
                            if not ndc_entry:
                                ndc_entry = ndc_data

                merged = clean_and_merge(entry, ndc_entry)

                combined_entry = merged or {}
                if ndc_metadata:
                    combined_entry["ndc_metadata"] = ndc_metadata
                combined_entry["product_ndc"] = product_ndcs

                all_out.write(json.dumps(combined_entry) + "\n")
                all_count += 1

                if not merged:
                    continue

                # Check if we've already written this
                is_duplicate = any(ndc in written_ndcs for ndc in product_ndcs)
                if is_duplicate:
                    continue

                routes = get_field(entry, "route") or (ndc_entry.get("route") if ndc_entry else None)
                if not routes:
                    routes = ["unknown"]
                elif not isinstance(routes, list):
                    routes = [routes]

                for route in routes:
                    slug = route.lower().replace(" ", "_").replace("/", "_") if route else "unknown"
                    out_path = os.path.join(OUTPUT_DIR, f"{slug}.jsonl")
                    with open(out_path, "a", encoding="utf-8") as f_out:
                        f_out.write(json.dumps(combined_entry) + "\n")
                        saved_count += 1

                for ndc in product_ndcs:
                    if ndc:
                        written_ndcs.add(ndc)

        skip += BATCH_SIZE
        requests_made += 1

        # Save checkpoint
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump({"skip": skip}, f)

        print(f"Fetched {len(results)} label entries, saved {saved_count}, wrote {all_count} to all_ndcs. Total so far: {skip}")

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
