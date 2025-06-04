import os
import json
import re
import networkx as nx
import pandas as pd
from pyvis.network import Network

def safe_attr(val):
    return val if val is not None else "unknown"

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
    for field in fields:
        val = entry.get(field)
        if isinstance(val, list) and val:
            return val[0]
        elif isinstance(val, str):
            return val
    openfda = entry.get('openfda', {})
    for field in fields:
        val = openfda.get(field)
        if isinstance(val, list) and val:
            return val[0]
        elif isinstance(val, str):
            return val
    return None

def get_route(entry):
    openfda = entry.get('openfda', {})
    val = openfda.get('route')
    return val[0] if isinstance(val, list) and val else val

def get_dosage_form(entry):
    openfda = entry.get('openfda', {})
    val = openfda.get('dosage_form')
    return val[0] if isinstance(val, list) and val else val

def process_fda_file(input_path, disease_terms):
    pairs = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            usage = entry.get('indications_and_usage')
            if not usage:
                continue
            usage_text = usage[0] if isinstance(usage, list) else usage
            diseases = extract_mentions(usage_text, disease_terms)
            if diseases:
                drug = get_drug_name(entry)
                if not drug:
                    continue
                route = get_route(entry)
                form = get_dosage_form(entry)
                for disease in diseases:
                    pairs.append((drug, disease, route, form))
    return pairs

def build_graph_from_directory(directory_path, disease_terms_path):
    disease_terms = load_disease_terms(disease_terms_path)
    G = nx.Graph()
    for fname in os.listdir(directory_path):
        if not fname.endswith('.jsonl'):
            continue
        full_path = os.path.join(directory_path, fname)
        print(f"Processing: {fname}")
        pairs = process_fda_file(full_path, disease_terms)
        for drug, disease, route, form in pairs:
            G.add_node(drug, type="medication")
            G.add_node(disease, type="indication")
            G.add_edge(
                drug,
                disease,
                route=safe_attr(route),
                dosage_form=safe_attr(form),
                source_file=fname
            )
    return G

if __name__ == '__main__':
    directory = "../data/raw"  # update if needed
    disease_terms_file = "../data/reference/diseases.txt"
    graph = build_graph_from_directory(directory, disease_terms_file)

    print(f"Graph built with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")

    # Example: output to GraphML for inspection
    nx.write_graphml(graph, "meds_indications.graphml")

    edges_df = nx.to_pandas_edgelist(graph)
    edges_df.to_csv("meds_indications_edges.csv", index=False)

    net = Network(
        height="750px",
        width="100%",
        bgcolor="#1a1a1a",
        font_color="white",
        notebook=True,
    )

    # Optional: Reduce shaking by tweaking physics
    net.barnes_hut(gravity=-30000, central_gravity=0.3, spring_length=100, spring_strength=0.01, damping=0.95)

    # Add nodes with color based on type
    for node, data in graph.nodes(data=True):
        node_type = data.get("type", "unknown")
        label = str(node)
        color = "#4dd0e1" if node_type == "medication" else "#aed581" if node_type == "indication" else "#e0e0e0"
        net.add_node(node, label=label, color=color)

    # Add edges
    for source, target in graph.edges():
        net.add_edge(source, target)

    # Save to and display in browser
    net.show("../docs/meds_indications.html")