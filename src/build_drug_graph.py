import os
import re
import json
import networkx as nx
from pyvis.network import Network
from html_components import html_search_bar, html_info_panel
from collections import defaultdict
from jinja2 import Environment, FileSystemLoader
import pyvis


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


def build_graph_from_extracted(file_path, extra_fields):
    pairs = load_extracted_mentions(file_path, extra_fields)
    G = nx.Graph()

    for drug, disease, attr_dict in pairs:
        G.add_node(drug, type="Medication")
        G.add_node(disease, type="Indication")
        clean_attrs = {k: safe_attr(v) for k, v in attr_dict.items()}
        G.add_edge(drug, disease, **clean_attrs)

    return G


def aggregate_drug_attributes(graph, fields_to_aggregate):
    drug_attributes = defaultdict(lambda: {field: set() for field in fields_to_aggregate})

    for source, target, attrs in graph.edges(data=True):
        if graph.nodes[source].get("type") == "Medication":
            drug = source
        elif graph.nodes[target].get("type") == "Medication":
            drug = target
        else:
            continue

        for field in fields_to_aggregate:
            value = safe_attr(attrs.get(field))
            drug_attributes[drug][field].add(value)

    return drug_attributes


if __name__ == '__main__':
    extracted_jsonl = "../data/extracted_disease_terms/label_disease_terms/label_extracted_with_diseases.jsonl"
    extra_fields = ['ndc', 'brand_name', 'generic_name', 'generic_indication',
                    'substance_name', 'route', 'dosage_form', 'manufacturer_name']

    print(f"Processing extracted mentions file: {os.path.basename(extracted_jsonl)}")
    graph = build_graph_from_extracted(extracted_jsonl, extra_fields)
    degree_dict = dict(graph.degree())

    print(f"Graph built with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")

    # Debugging: print problematic attributes
    for u, v, d in graph.edges(data=True):
        for k, v_ in d.items():
            if isinstance(v_, (list, dict)):
                print(f"⚠️ Problematic edge attribute: ({u}, {v}) -> {k}: {type(v_)}")

    # Safe to write after converting attributes
    nx.write_graphml(graph, "meds_indications2.graphml")

    edges_df = nx.to_pandas_edgelist(graph)

    net = Network(
        height="750px",
        width="100%",
        bgcolor="#1a1a1a",
        font_color="white",
        notebook=False,
        cdn_resources="in_line"
    )

    net.set_options("""
    {
    "nodes": {
        "font": {
                "size": 30,
                "face": "arial"
                    },
            "scaling": 
                {
                "min": 10,
                "max": 30
                    }
            },
      "physics": {
        "stabilization": {
          "enabled": true,
          "iterations": 500,
          "updateInterval": 25,
          "onlyDynamicEdges": false,
          "fit": true
        },
        "solver": "barnesHut",
        "barnesHut": {
          "gravitationalConstant": -25000,
          "centrality": 0.01,
          "springLength": 100,
          "springConstant": 0.001,
          "damping": 0.08,
          "avoidOverlap": 1
        }
      }
    }
    """)

    drug_attributes = aggregate_drug_attributes(graph, extra_fields)

    for node, data in graph.nodes(data=True):
        node_type = data.get("type", "unknown")
        label = str(node)
        color = "#4dd0e1" if node_type == "Medication" else "#aed581" if node_type == "Indication" else "#e0e0e0"

        tooltip_lines = [f"<strong>Type:</strong> {node_type}", f"<strong>Label:</strong> {truncate_string(label, 50)}"]

        if node_type == "Medication":
            if node in drug_attributes:
                drug_data = drug_attributes[node]
                for field, values in drug_data.items():
                    truncated_vals = [truncate_string(v, 50) for v in values if v]
                    field_display = field.replace('_', ' ').title().replace('Ndc', 'NDC')
                    tooltip_lines.append(f"<strong>{field_display}:</strong> {', '.join(truncated_vals)}")

            disease_neighbors = [
                n for n in graph.neighbors(node)
                if graph.nodes[n].get("type") == "Indication"
            ]
            if disease_neighbors:
                grouped = group_diseases_by_category(disease_neighbors)
                category_html_lines = []
                for category, diseases in grouped.items():
                    diseases = sorted(diseases)
                    disease_list_html = "<ul>" + "".join(f"<li>{d}</li>" for d in diseases) + "</ul>"
                    category_html_lines.append(f"<strong>{category}:</strong>{disease_list_html}")
                tooltip_lines.append("<br><strong>Associated Diseases:</strong><br>" + "<br>".join(category_html_lines))

        tooltip = "\n".join(tooltip_lines)
        panel_info_html = "<br>".join(tooltip_lines)
        size = scale_size(degree_dict.get(node, 1))
        font_size = 24 if node_type == "Indication" else 16

        net.add_node(
            node,
            label=label,
            color=color,
            size=size,
            font={'size': font_size},
            type=node_type,
            panel_info=panel_info_html
        )

    edge_color = "#50C878"
    for i, (source, target, attrs) in enumerate(graph.edges(data=True)):
        net.add_edge(
            source,
            target,
            color=edge_color,
            alpha=0.2,
            id=f"edge-{i}"
        )

    template_path = os.path.join(pyvis.__path__[0], 'templates')
    Network.template_env = Environment(loader=FileSystemLoader(template_path))

    output_html = "../docs/meds_indications2.html"
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(net.generate_html())

    print(f"Interactive graph saved to {output_html}")

    with open(output_html, "r", encoding="utf-8") as f:
        html = f.read()

    search_bar_script = html_search_bar()
    info_panel_script = html_info_panel()
    html = html.replace('<body>', '<body>\n' + search_bar_script + info_panel_script)

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)
