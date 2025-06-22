import os
import yaml
import json
import time
import requests
import re


def load_yaml_config(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def ensure_output_dir(path):
    os.makedirs(path, exist_ok=True)


def load_checkpoint(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {"last_offset": 0}


def save_checkpoint(path, checkpoint_data):
    with open(path, 'w') as f:
        json.dump(checkpoint_data, f, indent=2)


def rate_limited_request(session, url, params=None, max_retries=3):
    for _ in range(max_retries):
        try:
            response = session.get(url, params=params)
            if response.status_code == 429:
                time.sleep(1)
                continue
            return response
        except requests.RequestException:
            time.sleep(1)
    return None



def sanitize_label_fields(entry, required_fields):
    """
    Extract values from entry dict for given required_fields,
    supporting nested keys separated by dots.

    Args:
        entry (dict): Raw label entry.
        required_fields (list of str): Fields to extract; may include nested keys like 'openfda.route'.

    Returns:
        dict: {field_name: extracted_value or 'unknown'}
    """
    sanitized = {}
    for field in required_fields:
        parts = field.split('.')
        value = entry
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                value = "unknown"
                break
        sanitized[field] = value if value is not None else "unknown"
    return sanitized


def flatten_disease_dict(nested_dict):
    flat_list = []
    for category, diseases in nested_dict.items():
        for name, pattern in diseases.items():
            flat_list.append({
                "category": category,
                "name": name,
                "pattern": pattern
            })
    return flat_list



def safe_attr(val):
    if val is None:
        return "unknown"
    if isinstance(val, (list, dict)):
        return json.dumps(val)  # Convert list/dict to JSON string
    return val


def scale_size(degree, min_size=10, max_size=40):
    return min(max(degree * 3, min_size), max_size)


def truncate_string(s, l):
    s = str(s)
    return s if len(s) <= l else s[:l] + "..."


def sanitize_title(text):
    if not text:
        return ""
    return json.dumps(text)[1:-1]


def find_disease_category(disease_name):
    with open('../data/reference/diseases.json', 'r') as f:
        disease_categories = json.load(f)

    disease_name_lower = disease_name.lower()
    for category, diseases in disease_categories.items():
        for disease, pattern in diseases.items():
            if re.search(pattern, disease_name_lower, re.IGNORECASE):
                return category
    return "Other"


def group_diseases_by_category(disease_list):
    grouped = {}
    for disease in disease_list:
        category = find_disease_category(disease)
        grouped.setdefault(category, []).append(disease)
    return grouped


def load_extracted_mentions(file_path, extra_fields=None):
    if extra_fields is None:
        extra_fields = []

    pairs = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            drug = entry.get('brand_name')
            diseases = [m["disease"] for m in entry.get('disease_mentions', [])]

            if not drug or not diseases:
                continue

            extra_info = {field: entry.get(field) for field in extra_fields}
            for disease in diseases:
                pairs.append((drug, disease, extra_info))

    return pairs