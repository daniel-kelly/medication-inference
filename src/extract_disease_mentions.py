import json
import re
import os
import yaml
from utils import get_field, get_first_available_field


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
            mentions.add(disease_name.upper())
    return list(mentions)


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
                    name = get_first_available_field(entry, ['generic_name', 'brand_name', 'substance_name'])
                    generic_name = get_field(entry, 'generic_name')
                    brand_name = get_field(entry, 'brand_name')
                    if generic_name and brand_name:
                        generic_indication = 'G' if generic_name.strip().lower() == brand_name.strip().lower() else 'B'
                    else:
                        generic_indication = 'U'  # U for Unknown or Unclassified
                    substance_name = get_field(entry, 'substance_name')
                    route = get_field(entry, 'route')
                    form = get_field(entry, 'dosage_form')
                    manufacturer = get_field(entry, 'manufacturer_name')
                    ndc = get_field(entry, 'product_ndc')

                    results.append({
                        'drug': name,
                        'diseases': diseases,
                        'ndc': ndc,
                        'generic_name': generic_name,
                        'brand_name': brand_name,
                        'generic_indication': generic_indication,
                        'substance_name': substance_name,
                        'route': route,
                        'dosage_form': form,
                        'manufacturer_name': manufacturer,
                        'indications_text': usage_text[:80]  # first 80 chars for reference
                    })
    return results


if __name__ == '__main__':

    # Load parameters from YAML
    with open("params.yaml", "r") as f:
        config = yaml.safe_load(f)

    disease_dict_path = config['disease_dict_path']
    label_input_dir = config['label_input_dir']
    drug_indication_output_dir = config['drug_indication_output_dir']

    # Load and flatten disease regex dictionary
    nested_diseases = load_disease_terms(disease_dict_path)
    disease_terms = flatten_disease_dict(nested_diseases)

    # Process all JSONL files in the target directory
    extracted_data = process_fda_files(label_input_dir, disease_terms)

    # Save results to JSONL file
    with open(f'{drug_indication_output_dir}/extracted_drug_indications.jsonl', 'w', encoding='utf-8') as f_out:
        for entry in extracted_data:
            f_out.write(json.dumps(entry) + '\n')

    print(
        f"Saved {len(extracted_data)} extracted entries to {drug_indication_output_dir}/extracted_drug_indications.jsonl")
