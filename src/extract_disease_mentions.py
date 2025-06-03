import json
import re

def load_disease_terms(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip().lower() for line in f if line.strip()]

def extract_mentions(text, disease_terms):
    text = text.lower()
    mentions = set()
    for term in disease_terms:
        if re.search(rf'\b{re.escape(term)}\b', text):
            mentions.add(term)
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
    openfda = entry.get('openfda', {})
    val = openfda.get('route')
    if isinstance(val, list) and val:
        return val[0]
    elif isinstance(val, str):
        return val
    return None

def get_dosage_form(entry):
    openfda = entry.get('openfda', {})
    val = openfda.get('dosage_form')
    if isinstance(val, list) and val:
        return val[0]
    elif isinstance(val, str):
        return val
    return None



def process_fda_file(input_path, disease_terms):
    results = []
    with open(input_path, 'r', encoding='utf-8') as f:
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

                results.append({
                    'drug': name,
                    'diseases': diseases,
                    'route': route,
                    'dosage_form': form
                })
    return results

if __name__ == '__main__':
    disease_terms = load_disease_terms('../data/diseases.txt')
    data = process_fda_file('../data/raw_fda_labels.jsonl', disease_terms)

    for entry in data[:15]:
        print(json.dumps(entry, indent=2))
