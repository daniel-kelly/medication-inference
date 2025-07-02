import json
import re
import os
import time
from fuzzywuzzy import fuzz
import medspacy
import spacy

from utils import (
    flatten_disease_dict,
    load_yaml_config,
    load_checkpoint,
    save_checkpoint,
    ensure_output_dir,
)

nlp = medspacy.load(enable=["ner"])


def uppercase_all_text_values(obj):
    if isinstance(obj, str):
        return obj.upper()
    elif isinstance(obj, list):
        return [uppercase_all_text_values(v) for v in obj]
    elif isinstance(obj, dict):
        return {k: uppercase_all_text_values(v) for k, v in obj.items()}
    else:
        return obj


def reorder_fields(entry, desired_order):
    reordered = {k: entry.get(k) for k in desired_order if k in entry}
    # Add the remaining keys that weren't in the desired order
    remaining = {k: v for k, v in entry.items() if k not in reordered}
    reordered.update(remaining)
    return reordered


def extract_diseases_from_text(text, flat_diseases, fuzzy_threshold):
    mentions = []

    # Regex matching
    for d in flat_diseases:
        if re.search(d['pattern'], text, flags=re.IGNORECASE):
            mentions.append({
                "disease": d['name'],
                "method": "regex",
                "confidence": 1.0,
                "category": d.get('category')
            })

    # Fuzzy matching
    for d in flat_diseases:
        score = fuzz.partial_ratio(d['name'].lower(), text.lower())
        if score >= fuzzy_threshold:
            mentions.append({
                "disease": d['name'],
                "method": "fuzzy",
                "confidence": score / 100,
                "category": d.get('category')
            })

    # NER matching
    doc = nlp(text)
    for ent in doc.ents:
        if "disease" in ent.text.lower() or ent.label_.lower() in ("problem", "disorder", "diagnosis"):
            # Adjust if your model differs
            mentions.append({
                "disease": ent.text,
                "method": "ner",
                "confidence": 1.0,
                "category": None
            })

    # Deduplicate mentions, keep highest confidence per (disease, method)
    seen = {}
    for m in mentions:
        key = (m['disease'].lower(), m['method'])
        if key not in seen or m['confidence'] > seen[key]['confidence']:
            seen[key] = m
    return list(seen.values())

def extract_text_from_nested(value):
    if isinstance(value, str):
        return value
    elif isinstance(value, list):
        return " ".join(extract_text_from_nested(v) for v in value)
    elif isinstance(value, dict):
        texts = []
        for v in value.values():
            texts.append(extract_text_from_nested(v))
        return " ".join(texts)
    else:
        return ""

class LabelExtractor:
    def __init__(self, config_path):
        self.config = load_yaml_config(config_path)

        self.batch_size = self.config.get("batch_size", 100)
        self.checkpoint_file = self.config.get("label_checkpoint_file")
        self.output_dir = self.config.get("label_output_dir")
        self.ndc_input_file = self.config.get("ndc_input_file")
        self.label_input_file = self.config.get("label_input_file")

        disease_pattern_path = self.config.get("disease_pattern_path")
        with open(disease_pattern_path, "r") as f:
            disease_dict = json.load(f)
        self.flat_diseases = flatten_disease_dict(disease_dict)

        self.fuzzy_threshold = self.config.get("fuzzy_threshold", 90)
        self.essential_label_fields = self.config.get("essential_label_fields", [])

        ensure_output_dir(self.output_dir)
        self.checkpoint = load_checkpoint(self.checkpoint_file)
        self.offset = self.checkpoint.get("last_offset", 0)

        # Load base NDC entries
        with open(self.ndc_input_file, "r", encoding="utf-8") as f:
            self.ndc_entries = [json.loads(line) for line in f]

        # Load label entries
        with open(self.label_input_file, "r", encoding="utf-8") as f:
            self.label_entries = [json.loads(line) for line in f]

        # Load enriched NDC entries (flattened)
        self.enriched_ndc_map = {}
        if self.ndc_input_file and os.path.exists(self.ndc_input_file):
            with open(self.ndc_input_file, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    product_ndc = entry.get("product_ndc")
                    if product_ndc:
                        # Store entire enriched NDC entry except product_ndc key (optional)
                        ndc_flat = dict(entry)
                        ndc_flat.pop("product_ndc", None)
                        self.enriched_ndc_map[product_ndc] = ndc_flat

        # Build a map from spl_id to label data for quick lookup
        self.label_map = {}
        for entry in self.label_entries:
            spl_id = entry.get("spl_id")
            if spl_id:
                self.label_map[spl_id] = entry.get("label_data", {})

        self.output_path = os.path.join(self.output_dir, "label_extracted_with_diseases.jsonl")

    def extract_disease_mentions_from_label(self, label_data):
        mentions = []

        section_blacklist = [
            "limitations of use",
            "warnings",
            "precautions",
            "not recommended",
            "contraindicated",
            "use in specific populations"
        ]

        for field in self.essential_label_fields:
            raw_value = label_data.get(field)
            if not raw_value:
                continue
            text = extract_text_from_nested(raw_value)

            if not text.strip():
                continue

            # ✨ Check for known cautionary sections in this chunk of text
            lowered = text.lower()
            if any(bad_section in lowered for bad_section in section_blacklist):
                continue  # ❌ Skip this field entirely if it's likely a caution or exclusion section

            # ✅ Proceed with disease extraction
            mentions.extend(extract_diseases_from_text(text, self.flat_diseases, self.fuzzy_threshold))

        # Deduplicate across fields
        seen = {}
        for m in mentions:
            key = (m['disease'].strip().lower(), m['method'])
            if key not in seen or m['confidence'] > seen[key]['confidence']:
                seen[key] = m

        return list(seen.values())

    def run(self):
        while self.offset < len(self.ndc_entries):
            end = min(self.offset + self.batch_size, len(self.ndc_entries))
            batch = self.ndc_entries[self.offset:end]
            extracted = []

            for entry in batch:
                spl_id = entry.get("spl_id")
                product_ndc = entry.get("product_ndc")
                label_data = self.label_map.get(spl_id, {})

                if label_data:
                    disease_mentions = self.extract_disease_mentions_from_label(label_data)
                else:
                    disease_mentions = []

                ndc_info = self.enriched_ndc_map.get(product_ndc, {})

                combined = {
                    "spl_id": spl_id,
                    "product_ndc": product_ndc,
                    "disease_mentions": disease_mentions,
                    **ndc_info
                }

                # Uppercase all values
                combined = uppercase_all_text_values(combined)

                # Reorder keys before writing
                desired_key_order = ["spl_id", "product_ndc", "brand_name", "generic_name", "disease_mentions",
                                     "route", "dosage_form", "labeler_name", "product_type"]
                combined = reorder_fields(combined, desired_key_order)

                extracted.append(combined)
                time.sleep(0.05)

            with open(self.output_path, "a", encoding="utf-8") as f:
                for item in extracted:
                    f.write(json.dumps(item) + "\n")

            self.offset = end
            self.checkpoint["last_offset"] = self.offset
            save_checkpoint(self.checkpoint_file, self.checkpoint)

            print(f"Processed entries {self.offset - self.batch_size} to {self.offset} of {len(self.ndc_entries)}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python extract_diseases_from_labels.py path/to/params.yaml")
        sys.exit(1)

    extractor = LabelExtractor(sys.argv[1])
    extractor.run()
