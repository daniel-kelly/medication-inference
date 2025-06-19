import os
import yaml
import json
import time
import requests


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
