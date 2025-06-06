import json
import re
import os

def load_disease_terms(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def flatten_disease_dict(nested_dict):
    flat_dict = {}
    for category, diseases in nested_dict.items():
        for disease_name, pattern in diseases.items():
            flat_dict[disease_name] = pattern
    return flat_dict

def extract_mentions(text, disease_terms):
    text = text.lower()
    mentions = set()
    for disease_name, pattern in disease_terms.items():
        if re.search(pattern, text):
            mentions.add(disease_name)
    return list(mentions)

def get_drug_name(entry):
    fields = ['generic_name', 'brand_name', 'substance_name']

    # Try top-level fields
    for field in fields:
        val = entry.get(field)
        if isinstance(val, list) and val:
            return val[0]
        elif isinstance(val, str):
            return val

    # Try openfda subfields
    openfda = entry.get('openfda', {})
    for field in fields:
        val = openfda.get(field)
        if isinstance(val, list) and val:
            return val[0]
        elif isinstance(val, str):
            return val

    return '[Unknown]'

def get_route(entry):

    val = entry.get('route')
    if isinstance(val, list) and val:
        return val[0]
    elif isinstance(val, str):
        return val

    openfda = entry.get('openfda', {})
    val = openfda.get('route')
    if isinstance(val, list) and val:
        return val[0]
    elif isinstance(val, str):
        return val

    return None

def get_dosage_form(entry):

    val = entry.get('dosage_form')
    if isinstance(val, list) and val:
        return val[0]
    elif isinstance(val, str):
        return val

    openfda = entry.get('openfda', {})
    val = openfda.get('dosage_form')
    if isinstance(val, list) and val:
        return val[0]
    elif isinstance(val, str):
        return val
    return None

def get_manufacturer(entry):

    val = entry.get('manufacturer_name')
    if isinstance(val, list) and val:
        return val[0]
    elif isinstance(val, str):
        return val

    openfda = entry.get('openfda', {})
    val = openfda.get('manufacturer_name')
    if isinstance(val, list) and val:
        return val[0]
    elif isinstance(val, str):
        return val
    return None

def process_fda_files(input_dir, disease_terms):
    results = []
    print(f"Reading files from: {input_dir}")
    files = [f for f in os.listdir(input_dir) if f.endswith('.jsonl')]

    for filename in files:
        filepath = os.path.join(input_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                entry = json.loads(line)
                usage = entry.get('indications_and_usage')
                if not usage:
                    continue

                usage_text = usage[0] if isinstance(usage, list) else usage
                diseases = extract_mentions(usage_text, disease_terms)
                if diseases:
                    name = get_drug_name(entry)
                    route = get_route(entry)
                    form = get_dosage_form(entry)
                    manufacturer = get_manufacturer(entry)

                    results.append({
                        'drug': name,
                        'diseases': diseases,
                        'route': route,
                        'dosage_form': form,
                        'manufacturer_name': manufacturer,
                        'indications_text': usage_text[:80]  # first 80 chars for reference
                    })
    return results


if __name__ == '__main__':
    disease_dict_path = '../data/reference/diseases.json'
    input_dir = '../data/fda_output'
    output_path = '../data/indication_extracts/fda_extracted_disease_mentions.jsonl'

    # Load and flatten disease regex dictionary
    nested_diseases = load_disease_terms(disease_dict_path)
    disease_terms = flatten_disease_dict(nested_diseases)

    # Process all JSONL files in the target directory
    extracted_data = process_fda_files(input_dir, disease_terms)

    # Save results to JSONL file
    with open(output_path, 'w', encoding='utf-8') as f_out:
        for entry in extracted_data:
            f_out.write(json.dumps(entry) + '\n')

    print(f"Saved {len(extracted_data)} extracted entries to {output_path}")
