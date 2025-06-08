# import json
#
# input_file = "../data/raw_fda_labels.jsonl"
# count_total = 0
# count_with_indications = 0
# sample = []
#
# with open(input_file, "r", encoding="utf-8") as f:
#     for line in f:
#         count_total += 1
#         try:
#             record = json.loads(line)
#             usage = record.get("indications_and_usage", [])
#             if usage and isinstance(usage, list) and any(usage):
#                 count_with_indications += 1
#                 if len(sample) < 5:
#                     sample.append({
#                         "generic_name": record.get("openfda", {}).get("generic_name", ["[Unknown]"])[0],
#                         "indications": usage[0][:500]  # First 500 characters
#                     })
#         except json.JSONDecodeError:
#             continue  # skip malformed lines
#
# print(f"Total records: {count_total}")
# print(f"Records with 'indications_and_usage': {count_with_indications}")
# print("\nSample entries:\n")
#
# for i, s in enumerate(sample, 1):
#     print(f"{i}. {s['generic_name']}")
#     print("-" * 40)
#     print(s['indications'], "\n")

from collections import Counter
import json

def check_openfda_fields(jsonl_file):
    fields = Counter()
    with open(jsonl_file, 'r') as f:
        for line in f:
            entry = json.loads(line)
            openfda = entry.get('openfda', {})
            for key in openfda.keys():
                fields[key] += 1
    return fields

print(check_openfda_fields('../data/indication_extracts/fda_extracted_disease_mentions.jsonl'))
