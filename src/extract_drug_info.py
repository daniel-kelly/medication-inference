import os
import json
import requests
import time
from typing import Optional, Dict, Any
from utils import (
    load_yaml_config,
    ensure_output_dir,
    load_checkpoint,
    save_checkpoint,
    rate_limited_request,
)

API_NDC = "https://api.fda.gov/drug/ndc.json"

class NDCExtractor:
    def __init__(self, config_path):
        self.config = load_yaml_config(config_path)
        self.session = requests.Session()
        self.api_key = self.config.get("api_key")
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

        self.batch_size = self.config.get("batch_size", 100)
        self.checkpoint_file = self.config.get("checkpoint_file")
        self.output_dir = self.config.get("output_dir")
        self.essential_fields = self.config.get("essential_ndc_fields", [])
        self.allowed_product_types = set(t.upper() for t in self.config.get("allowed_product_types", []))
        self.excluded_product_classes = [c.upper() for c in self.config.get("excluded_product_classes", [])]

        ensure_output_dir(self.output_dir)
        self.checkpoint = load_checkpoint(self.checkpoint_file)
        self.offset = self.checkpoint.get("last_offset", 0)
        self.output_path = os.path.join(self.output_dir, "ndc_extracted.jsonl")

    def build_query_url(self, skip):
        has_nested = any("." in f for f in self.essential_fields)
        if has_nested:
            return f"{API_NDC}?skip={skip}&limit={self.batch_size}"
        else:
            select_fields = ",".join(self.essential_fields)
            return f"{API_NDC}?skip={skip}&limit={self.batch_size}&select={select_fields}"

    def filter_entry(self, entry):
        pt = entry.get("product_type", "").upper()
        pc = entry.get("product_class", "").upper()
        if pt not in self.allowed_product_types:
            return False
        if any(exc in pc for exc in self.excluded_product_classes):
            return False
        return True

    def extract_fields(self, entry):
        extracted = {}
        for f in self.essential_fields:
            if '.' in f:
                parts = f.split('.')
                val = entry
                for p in parts:
                    val = val.get(p, {})
                if val == {}:
                    val = None
                extracted[f] = val
            else:
                extracted[f] = entry.get(f)
        extracted["product_type"] = entry.get("product_type")
        extracted["product_class"] = entry.get("product_class")
        return extracted

    def fetch_batch(self, skip):
        url = self.build_query_url(skip)
        response = rate_limited_request(self.session, url, max_retries=5)
        return response.json()

    def save_results(self, entries):
        with open(self.output_path, "a", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    def update_checkpoint(self, offset):
        self.checkpoint["last_offset"] = offset
        save_checkpoint(self.checkpoint_file, self.checkpoint)

    def run(self):
        total = None
        records_fetched = 0
        while True:
            data = self.fetch_batch(self.offset)
            if total is None:
                total = data.get("meta", {}).get("results", {}).get("total", 0)
                print(f"Total records to process: {total}")

            results = data.get("results", [])
            if not results:
                print("No more results, extraction complete.")
                break

            filtered = [self.extract_fields(e) for e in results if self.filter_entry(e)]
            self.save_results(filtered)

            records_fetched += len(results)
            self.offset += len(results)
            self.update_checkpoint(self.offset)
            print(f"Fetched {records_fetched} / {total} records...")

            if self.offset >= total:
                print("Extraction finished successfully.")
                break


API_LABEL = "https://api.fda.gov/drug/label.json"


class LabelExtractor:
    def __init__(self, config_path):
        self.config = load_yaml_config(config_path)
        self.session = requests.Session()
        self.api_key = self.config.get("api_key")
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

        self.batch_size = self.config.get("batch_size", 100)
        self.checkpoint_file = self.config.get("label_checkpoint_file")
        self.output_dir = self.config.get("label_output_dir")
        self.ndc_input_file = self.config.get("ndc_input_file")
        self.essential_fields = self.config.get("essential_label_fields", [])

        ensure_output_dir(self.output_dir)
        self.checkpoint = load_checkpoint(self.checkpoint_file)
        self.offset = self.checkpoint.get("last_offset", 0)
        self.output_path = os.path.join(self.output_dir, "label_extracted.jsonl")

        with open(self.ndc_input_file, "r", encoding="utf-8") as f:
            self.ndc_entries = [json.loads(line) for line in f.readlines()]

    def get_nested_field(self, data, field_path):
        keys = field_path.split(".")
        val = data
        for k in keys:
            if not isinstance(val, dict):
                return None
            val = val.get(k)
        return val

    def fetch_label(self, spl_id: Optional[str], spl_set_id: Optional[str]) -> Optional[Dict[str, Any]]:
        url = API_LABEL

        if spl_set_id:
            params = {"search": f'set_id:"{spl_set_id}"', "limit": 1}
            try:
                response = rate_limited_request(self.session, url, params=params, max_retries=3)
                data = response.json()
                if "results" in data and data["results"]:
                    return data["results"][0]
            except Exception as e:
                print(f"Error fetching label for SPL Set ID {spl_set_id}: {e}")

        if spl_id:
            params = {"search": f'spl_id:"{spl_id}"', "limit": 1}
            try:
                response = rate_limited_request(self.session, url, params=params, max_retries=3)
                data = response.json()
                if "results" in data and data["results"]:
                    return data["results"][0]
            except Exception as e:
                print(f"Error fetching label for SPL ID {spl_id}: {e}")

        return None

    def run(self):
        total = len(self.ndc_entries)
        while self.offset < total:
            end = min(self.offset + self.batch_size, total)
            batch = self.ndc_entries[self.offset:end]
            extracted = []

            for entry in batch:
                flat_entry = {
                    (k[len("openfda."):]) if k.startswith("openfda.") else k: v
                    for k, v in entry.items()
                }

                spl_id = flat_entry.get("spl_id")
                spl_set_id = flat_entry.get("spl_set_id", [None])[0] if isinstance(flat_entry.get("spl_set_id"),
                                                                                   list) else flat_entry.get(
                    "spl_set_id")

                label_data = self.fetch_label(spl_id, spl_set_id)

                if label_data:
                    filtered_label_data = {
                        k: self.get_nested_field(label_data, k)
                        for k in self.essential_fields
                    }

                    combined = {
                        "product_ndc": flat_entry.get("product_ndc"),
                        "spl_id": spl_id,
                        "label_data": filtered_label_data
                    }
                    extracted.append(combined)

                time.sleep(0.1)

            with open(self.output_path, "a", encoding="utf-8") as f:
                for item in extracted:
                    f.write(json.dumps(item) + "\n")

            self.offset = end
            self.checkpoint["last_offset"] = self.offset
            save_checkpoint(self.checkpoint_file, self.checkpoint)

            print(
                f"Extracted labels for {len(extracted)} of {len(batch)} entries from offset {self.offset - len(batch)} to {self.offset}")

        print("Label extraction complete.")


def main():
    # Uncomment to run NDC extraction
    # ndc_extractor = NDCExtractor("../params.yaml")
    # ndc_extractor.run()

    label_extractor = LabelExtractor("../params.yaml")
    label_extractor.run()


if __name__ == "__main__":
    main()
