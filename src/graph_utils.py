import networkx as nx
from networkx.algorithms.community import greedy_modularity_communities
from networkx.algorithms import bipartite

import community as community_louvain

from collections import Counter
from utils import find_disease_category

def assign_clusters_greedy(G, node_type="Medication"):
    # Get all nodes of the specified type
    nodes_of_type = [n for n, d in G.nodes(data=True) if d.get("type") == node_type]

    # Project bipartite graph onto these nodes to create edges between nodes sharing neighbors
    projected_graph = bipartite.projected_graph(G, nodes_of_type)

    # Run community detection on the projected graph
    communities = list(greedy_modularity_communities(projected_graph))

    # Map each node to its cluster ID
    cluster_map = {}
    for i, community in enumerate(communities):
        for node in community:
            cluster_map[node] = i

    # Assign cluster IDs back to the original graph nodes
    nx.set_node_attributes(G, cluster_map, "cluster_id")

    unique_clusters = set(cluster_map.values())
    print(f"Number of clusters: {len(unique_clusters)}")

    return cluster_map


def assign_clusters_louvain(G, node_type="Medication", resolution=1.0):

    # Project bipartite graph if needed
    if node_type:
        nodes = [n for n, d in G.nodes(data=True) if d.get("type") == node_type]
        G_proj = bipartite.projected_graph(G, nodes)
    else:
        G_proj = G

    # Louvain clustering
    partition = community_louvain.best_partition(G_proj, resolution=resolution)
    nx.set_node_attributes(G, partition, "cluster_id")

    print(f"Number of clusters: {len(set(partition.values()))}")
    return partition



def generate_cluster_labels(G, cluster_map):
    cluster_to_drugs = {}
    for node, cid in cluster_map.items():
        cluster_to_drugs.setdefault(cid, []).append(node)

    cluster_labels = {}
    for cid, drugs in cluster_to_drugs.items():
        disease_categories = []

        for drug in drugs:
            neighbors = [n for n in G.neighbors(drug) if G.nodes[n].get("type") == "Indication"]
            for disease in neighbors:
                category = find_disease_category(disease)
                if category:
                    disease_categories.append(category)

        if disease_categories:
            counter = Counter(disease_categories)
            most_common = [cat for cat, _ in counter.most_common(3)]
            label = "-".join(most_common) + " Medications"
        else:
            label = "Unknown Cluster"

        cluster_labels[cid] = label

    return cluster_labels

