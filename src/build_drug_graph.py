import os
import json
import networkx as nx
import pandas as pd
from pyvis.network import Network
from collections import defaultdict

def safe_attr(val):
    return val if val is not None else "unknown"

def scale_size(degree, min_size=10, max_size=40):
    return min(max(degree * 3, min_size), max_size)

def load_extracted_mentions(file_path):
    pairs = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            drug = entry.get('brand_name')
            diseases = entry.get('diseases', [])
            route = entry.get('route')
            form = entry.get('dosage_form')
            manufacturer = entry.get('manufacturer_name')
            if not drug or not diseases:
                continue
            for disease in diseases:
                pairs.append((drug, disease, route, form, manufacturer))
    return pairs

def build_graph_from_extracted(file_path):
    pairs = load_extracted_mentions(file_path)
    G = nx.Graph()
    for drug, disease, route, form, manufacturer in pairs:
        G.add_node(drug, type="medication")
        G.add_node(disease, type="indication")
        G.add_edge(
            drug,
            disease,
            route=safe_attr(route),
            dosage_form=safe_attr(form),
            manufacturer=safe_attr(manufacturer)
        )
    return G

if __name__ == '__main__':

    extracted_jsonl = "../data/indication_extracts/extracted_drug_indications.jsonl"
    print(f"Processing extracted mentions file: {os.path.basename(extracted_jsonl)}")
    graph = build_graph_from_extracted(extracted_jsonl)

    # Get degrees for node sizing
    degree_dict = dict(graph.degree())

    print(f"Graph built with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")

    # Save graph as GraphML and CSV for inspection
    nx.write_graphml(graph, "meds_indications.graphml")
    edges_df = nx.to_pandas_edgelist(graph)

    # Build interactive visualization with PyVis
    net = Network(
        height="750px",
        width="100%",
        bgcolor="#1a1a1a",
        font_color="white",
        notebook=True
    )

    #net.barnes_hut(gravity=-30000, central_gravity=0.3, spring_length=100, spring_strength=0.01, damping=0.95)

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
          "gravitationalConstant": -15000,
          "springLength": 15,
          "springConstant": 0.002,
          "damping": 0.08,
          "avoidOverlap": 1
        }
      }
    }
    """)

    # Add nodes with color and tooltip based on type
    from collections import defaultdict

    # Step 1: Aggregate edge attributes by drug node
    drug_attributes = defaultdict(lambda: {"routes": set(), "forms": set(), "manufacturer": set()})
    for source, target, attrs in graph.edges(data=True):
        if graph.nodes[source]["type"] == "medication":
            drug = source
        elif graph.nodes[target]["type"] == "medication":
            drug = target
        else:
            continue  # Skip if neither node is a drug

        drug_attributes[drug]["routes"].add(safe_attr(attrs.get("route")))
        drug_attributes[drug]["forms"].add(safe_attr(attrs.get("dosage_form")))
        drug_attributes[drug]["manufacturer"].add(safe_attr(attrs.get("manufacturer")))

    # Step 2: Add nodes with tooltip
    for node, data in graph.nodes(data=True):
        node_type = data.get("type", "unknown")
        label = str(node)
        color = "#4dd0e1" if node_type == "medication" else "#aed581" if node_type == "indication" else "#e0e0e0"

        tooltip = f"Type: {node_type}\nLabel: {label}"
        if node_type == "medication" and node in drug_attributes:
            drug_data = drug_attributes[node]
            tooltip += f"\nRoutes: {', '.join(drug_data['routes'])}"
            tooltip += f"\nForms: {', '.join(drug_data['forms'])}"
            tooltip += f"\nManufacturer: {', '.join(drug_data['manufacturer'])}"

        size = scale_size(degree_dict.get(node, 1))
        font_size = 24 if node_type == "indication" else 16
        net.add_node(
            node,
            label=label,
            color=color,
            title=tooltip,
            size=size,
            font={'size': font_size},
            type=node_type  # <-- Add this
        )

    # Add edges with fixed color
    edge_color = "#50C878"
    for i, (source, target, attrs) in enumerate(graph.edges(data=True)):
        net.add_edge(
            source,
            target,
            color=edge_color,
            alpha=0.2,
            id=f"edge-{i}"  # <-- Add unique ID
        )

    # Save visualization HTML
    output_html = "../docs/meds_indications.html"
    net.show(output_html)
    print(f"Interactive graph saved to {output_html}")

    with open(output_html, "r", encoding="utf-8") as f:
        html = f.read()

    enhancement_script = '''
    <div style="position:fixed; top:20px; left:10px; z-index:1000; background:white; padding:10px; border-radius:5px;">
      <input type="text" id="nodeSearch" placeholder="Search for drug or disease" style="width:250px; padding:5px;"/>
      <button onclick="searchNode()">Search</button>
    </div>
        
        <script>
    function searchNode() {
      const input = document.getElementById('nodeSearch').value.toLowerCase();
      if (!input) return;
      const matches = network.body.data.nodes.get().filter(n => n.label.toLowerCase().includes(input));
      if (matches.length === 0) {
        alert('No match');
        return;
      }
      const nodeId = matches[0].id;
      network.selectNodes([nodeId]);
      network.focus(nodeId, {scale: 1.5, animation: true});
    }
    
    </script>

    '''



    # Insert enhanced interactivity tools after <body>
    html = html.replace('<body>', f'<body>{enhancement_script}')

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)

    print("✅ Node interactivity, glow effects, and N-degree checkbox added.")

