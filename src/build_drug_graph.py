import os
import json
import networkx as nx
from pyvis.network import Network


def safe_attr(val):
    return val if val is not None else "unknown"


def scale_size(degree, min_size=10, max_size=40):
    return min(max(degree * 3, min_size), max_size)


def truncate_string(s, l):
    s = str(s)
    return s if len(s) <= l else s[:l] + "..."


def load_extracted_mentions(file_path, extra_fields=None):
    """
    Load extracted mentions from a JSONL file.

    :param file_path: Path to the JSONL file.
    :param extra_fields: List of optional fields to extract (excluding 'brand_name' and 'diseases').
    :return: List of tuples like (drug, disease, extra_info_dict)
    """
    if extra_fields is None:
        extra_fields = []

    pairs = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            drug = entry.get('brand_name')
            diseases = entry.get('diseases', [])

            if not drug or not diseases:
                continue

            # Extract optional fields
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

        # Sanitize attributes before adding to edge
        clean_attrs = {k: safe_attr(v) for k, v in attr_dict.items()}
        G.add_edge(drug, disease, **clean_attrs)

    return G



def aggregate_drug_attributes(graph, fields_to_aggregate):
    """
    Aggregate selected edge attributes by drug node.

    :param graph: NetworkX graph with node types and edge attributes.
    :param fields_to_aggregate: List of edge attributes to aggregate for each drug node.
    :return: Dictionary of drug -> {field -> set of values}
    """
    drug_attributes = defaultdict(lambda: {field: set() for field in fields_to_aggregate})

    for source, target, attrs in graph.edges(data=True):
        # Identify which node is the drug
        if graph.nodes[source].get("type") == "Medication":
            drug = source
        elif graph.nodes[target].get("type") == "Medication":
            drug = target
        else:
            continue  # Skip if neither node is a medication

        for field in fields_to_aggregate:
            value = safe_attr(attrs.get(field))
            drug_attributes[drug][field].add(value)

    return drug_attributes


if __name__ == '__main__':

    extracted_jsonl = "../data/indication_extracts/extracted_drug_indications.jsonl"
    extra_fields = ['ndc', 'brand_name', 'generic_name', 'generic_indication',
                    'substance_name', 'route', 'dosage_form', 'manufacturer_name']

    print(f"Processing extracted mentions file: {os.path.basename(extracted_jsonl)}")
    graph = build_graph_from_extracted(extracted_jsonl, extra_fields)

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

    # net.barnes_hut(gravity=-30000, central_gravity=0.3, spring_length=100, spring_strength=0.01, damping=0.95)

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
    drug_attributes = aggregate_drug_attributes(graph, extra_fields)

    # Step 2: Add nodes with tooltip
    for node, data in graph.nodes(data=True):
        node_type = data.get("type", "unknown")
        label = str(node)

        # Color by node type
        color = (
            "#4dd0e1" if node_type == "Medication"
            else "#aed581" if node_type == "Indication"
            else "#e0e0e0"
        )

        # Start tooltip with basic info
        tooltip_lines = [f"Type: {node_type}", f"Label: {truncate_string(label, 50)}"]

        # Add dynamic attributes for drug nodes
        if node_type == "Medication":
            # Attribute aggregation
            if node in drug_attributes:
                drug_data = drug_attributes[node]
                for field, values in drug_data.items():
                    truncated_vals = [truncate_string(v, 50) for v in values if v]
                    tooltip_lines.append(f"{field.replace('_', ' ').title()}: {', '.join(truncated_vals)}")

            # Get connected disease nodes
            disease_neighbors = [
                n for n in graph.neighbors(node)
                if graph.nodes[n].get("type") == "Indication"
            ]
            if disease_neighbors:
                truncated_diseases = [truncate_string(d, 50) for d in disease_neighbors[:3]]
                extra_count = len(disease_neighbors) - 3
                if extra_count > 0:
                    truncated_diseases.append(f"...(+{extra_count} more)")
                tooltip_lines.append(f"Associated Diseases: {', '.join(truncated_diseases)}")

        tooltip = "\n".join(tooltip_lines)

        size = scale_size(degree_dict.get(node, 1))
        font_size = 24 if node_type == "Indication" else 16

        net.add_node(
            node,
            label=label,
            color=color,
            title=tooltip,
            size=size,
            font={'size': font_size},
            type=node_type
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
    <div id="infoPanel" style="
        position: fixed;
        top: 20px;
        right: 20px;
        width: 320px;
        max-height: 90vh;
        overflow-y: auto;
        padding: 15px;
        background: white;
        border-radius: 8px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        font-family: Arial, sans-serif;
        z-index: 9999;
        display: none;
    ">
      <h3 id="panelTitle" style="margin-top: 0;"></h3>
      <div id="panelContent"></div>
      <button onclick="document.getElementById('infoPanel').style.display='none'"
        style="position: absolute; top: 5px; right: 10px; background: transparent; border: none; font-size: 18px; cursor: pointer;">
        ✖
      </button>
    </div>

    <div style="position:fixed; top:20px; left:10px; z-index:1000; background:white; padding:10px; border-radius:5px;">
      <input type="text" id="nodeSearch" placeholder="Search for drug or disease" style="width:250px; padding:5px;"/>
      <button onclick="searchNode()">Search</button>
    </div>

    <script type="text/javascript">
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

      // When a node is clicked, show info in panel
      network.on("click", function (params) {
        if (params.nodes.length === 0) {
          // Hide panel if clicking on empty space
          document.getElementById("infoPanel").style.display = "none";
          return;
        }

        const nodeId = params.nodes[0];
        const node = network.body.data.nodes.get(nodeId);

        if (!node) return;

        // Build panel content
        const title = node.label || "Unnamed node";
        const type = node.type || "unknown";

        let content = `<strong>Type:</strong> ${type}<br/><br/>`;

        if (node.title) {
          const lines = node.title.split("\\n");
          lines.forEach(line => {
            const parts = line.split(":");
            if (parts.length > 1) {
              content += `<strong>${parts[0].trim()}:</strong> ${parts.slice(1).join(":").trim()}<br/>`;
            } else {
              content += `${line}<br/>`;
            }
          });
        }

        document.getElementById("panelTitle").innerText = title;
        document.getElementById("panelContent").innerHTML = content;
        document.getElementById("infoPanel").style.display = "block";
      });
    </script>
    '''

    # Insert enhanced interactivity tools after <body>
    html = html.replace('<body>', f'<body>{enhancement_script}')

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)

