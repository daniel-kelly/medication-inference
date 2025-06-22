import os
import re
import json
import networkx as nx
from pyvis.network import Network
from utils import load_extracted_mentions, safe_attr, scale_size, truncate_string, group_diseases_by_category
from html_components import html_search_bar, html_info_panel, html_cluster_legend
from graph_utils import assign_clusters_greedy, assign_clusters_louvain, generate_cluster_labels

from collections import defaultdict


from jinja2 import Environment, FileSystemLoader
import pyvis



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
    extra_fields = ['product_ndc', 'brand_name', 'generic_name', 'route', 'dosage_form', 'labeler_name']

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
    #assign_clusters(graph, node_type="Medication")  # or "Indication" if you prefer

    cluster_map = assign_clusters_louvain(graph, node_type="Medication", resolution=0.8)
    cluster_labels = generate_cluster_labels(graph, cluster_map)
    cluster_labels_json = json.dumps(cluster_labels)

    for node, data in graph.nodes(data=True):
        node_type = data.get("type", "unknown")
        label = str(node)
        color = "#4dd0e1" if node_type == "Medication" else "#79db60" if node_type == "Indication" else "#e0e0e0"

        tooltip_lines = [f"<strong>Type:</strong> {node_type}", f"<strong>Label:</strong> {truncate_string(label, 50)}"]

        if node_type == "Medication":
            if node in drug_attributes:
                drug_data = drug_attributes[node]
                for field, values in drug_data.items():
                    truncated_vals = [truncate_string(v, 50) for v in values if v]
                    field_display = field.replace('_', ' ').title().replace('product_ndc', 'NDC')
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
            panel_info=panel_info_html,
            cluster_id = data.get("cluster_id", -1)
        )

    edge_color = "#79db60"
    for i, (source, target, attrs) in enumerate(graph.edges(data=True)):
        net.add_edge(
            source,
            target,
            color=edge_color,
            alpha=0.01,
            id=f"edge-{i}"
        )

    template_path = os.path.join(pyvis.__path__[0], 'templates')
    Network.template_env = Environment(loader=FileSystemLoader(template_path))

    output_html = "../docs/meds_indications.html"
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(net.generate_html())

    print(f"Interactive graph saved to {output_html}")

    with open(output_html, "r", encoding="utf-8") as f:
        html = f.read()

    search_bar_script = html_search_bar()
    info_panel_script = html_info_panel()
    cluster_panel_script = html_cluster_legend()
    cluster_names = f'<script>const clusterLabels = {cluster_labels_json};</script>\n'


    html = html.replace('<body>', '<body>\n' + search_bar_script + info_panel_script +
                        cluster_panel_script + cluster_names)

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)
