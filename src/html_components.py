# html_components.py

def html_hop_explorer():
    return """
    <div id="hopPanel" style="position:fixed; top:560px; left:10px; z-index:1000; background:white; padding:10px; border-radius:5px; font-size:12px; width:360px; box-shadow: 0 2px 6px rgba(0,0,0,0.2);">
      <strong>Disease Hop Explorer</strong><br>
      <label><input type="checkbox" id="hopModeToggle"> Enable explorer</label><br>
      <label>n hops:
        <input type="number" id="hopDepth" value="1" min="1" max="5" style="width:40px; margin-left:6px;" />
      </label>
      <button id="resetGraphBtn" style="margin-left:10px;">Reset</button>
    </div>

    <script type="text/javascript">
    window.addEventListener("load", function () {
      if (typeof network === 'undefined') return;

      const allNodes = network.body.data.nodes.get();
      const allEdges = network.body.data.edges.get();

      const nodeMap = new Map(allNodes.map(n => [n.id, n]));
      const edgeMap = new Map();
      allEdges.forEach(edge => {
        if (!edgeMap.has(edge.from)) edgeMap.set(edge.from, []);
        if (!edgeMap.has(edge.to)) edgeMap.set(edge.to, []);
        edgeMap.get(edge.from).push(edge.to);
        edgeMap.get(edge.to).push(edge.from);  // undirected
      });

      const originalNodeStates = new Map(allNodes.map(n => [n.id, { hidden: n.hidden, color: n.color }]));

      function resetGraph() {
        const restoredNodes = allNodes.map(n => {
          const orig = originalNodeStates.get(n.id);
          return { id: n.id, hidden: orig.hidden, color: orig.color };
        });
        network.body.data.nodes.update(restoredNodes);
      }

      function bfsDiseaseHops(startId, maxHops) {
        const visited = new Set();
        const queue = [{ id: startId, depth: 0 }];
        const result = new Set();

        while (queue.length > 0) {
          const { id, depth } = queue.shift();
          if (visited.has(id)) continue;
          visited.add(id);
          result.add(id);

          if (depth >= maxHops) continue;

          const neighbors = edgeMap.get(id) || [];
          for (const neighbor of neighbors) {
            queue.push({ id: neighbor, depth: depth + 1 });
          }
        }

        return result;
      }

      network.on("click", function (params) {
        const hopEnabled = document.getElementById("hopModeToggle").checked;
        const hopDepth = parseInt(document.getElementById("hopDepth").value, 10);
        if (!hopEnabled || isNaN(hopDepth) || params.nodes.length === 0) return;

        const clickedNodeId = params.nodes[0];
        const node = nodeMap.get(clickedNodeId);
        if (!node || node.type !== "Indication") return;

        const visibleIds = bfsDiseaseHops(clickedNodeId, hopDepth * 2); // each hop includes both node types

        const updated = allNodes.map(n => ({
          id: n.id,
          hidden: !visibleIds.has(n.id)
        }));

        network.body.data.nodes.update(updated);
      });

      document.getElementById("resetGraphBtn").addEventListener("click", () => {
        resetGraph();
      });
    });
    </script>
    """


def html_cluster_legend():
    return """
    <div id="clusterPanel" style="position:fixed; top:180px; left:10px; z-index:1000; background:white; padding:10px; border-radius:5px; max-height:360px; overflow-y:auto; font-size:12px; width:360px; box-shadow: 0 2px 6px rgba(0,0,0,0.2);">
      <strong>Toggle Clusters</strong><br>
      <div id="clusterLegend" style="margin-top:8px;"></div>
    </div>

    <script type="text/javascript">
    window.addEventListener("load", function () {
      if (typeof network === 'undefined') return;

      const clusterColors = [
      "#e6194b", // red
      "#ffe119", // yellow
      "#4363d8", // blue
      "#f58231", // orange
      "#911eb4", // purple
      "#46f0f0", // cyan
      "#f032e6", // magenta
      "#fabebe", // light pink
      "#008080", // teal
      "#e6beff", // lavender
      "#9a6324", // brown
      "#fffac8", // pale yellow
      "#800000"  // maroon
    ];


      const allNodes = network.body.data.nodes.get();
      const clusterLegendContainer = document.getElementById("clusterLegend");

      let visibleClusters = new Set();

      function updateVisibilityAndColors() {
        const nodeUpdates = [];

        // Update medication nodes
        allNodes.forEach(node => {
          if (node.cluster_id !== undefined && node.cluster_id !== null) {
            const isVisible = visibleClusters.has(node.cluster_id);
            nodeUpdates.push({
              id: node.id,
              hidden: !isVisible,
              color: isVisible ? clusterColors[node.cluster_id % clusterColors.length] : '#ddd'
            });
          } else {
            // Non-clustered nodes visible by default
            nodeUpdates.push({ id: node.id, hidden: false, color: node.color || '#ccc' });
          }
        });

        network.body.data.nodes.update(nodeUpdates);

        // Hide disease nodes with no visible meds
        const diseaseUpdates = [];
        allNodes.forEach(node => {
          if (node.type === "Indication") {
            const neighbors = network.getConnectedNodes(node.id);
            const hasVisibleMed = neighbors.some(nid => {
              const medNode = network.body.data.nodes.get(nid);
              return medNode && !medNode.hidden && medNode.type === "Medication";
            });
            diseaseUpdates.push({ id: node.id, hidden: !hasVisibleMed });
          }
        });

        network.body.data.nodes.update(diseaseUpdates);
      }

      function buildClusterLegend() {
        clusterLegendContainer.innerHTML = "";
        const clusters = [...new Set(allNodes.map(n => n.cluster_id).filter(cid => cid !== undefined))].sort((a,b) => a - b);

        clusters.forEach(cid => {
          const color = clusterColors[cid % clusterColors.length];

          const label = document.createElement("label");
          label.style.display = "flex";
          label.style.alignItems = "center";
          label.style.marginTop = "4px";

          const checkbox = document.createElement("input");
          checkbox.type = "checkbox";
          checkbox.checked = true;
          checkbox.style.marginRight = "6px";
          checkbox.dataset.clusterId = cid;

          checkbox.addEventListener("change", (e) => {
            if (e.target.checked) {
              visibleClusters.add(cid);
            } else {
              visibleClusters.delete(cid);
            }
            updateVisibilityAndColors();
          });

          const colorBox = document.createElement("div");
          colorBox.style.width = "12px";
          colorBox.style.height = "12px";
          colorBox.style.backgroundColor = color;
          colorBox.style.border = "1px solid #ccc";
          colorBox.style.marginRight = "6px";

          label.appendChild(checkbox);
          label.appendChild(colorBox);
          const clusterName = (typeof clusterLabels !== 'undefined' && clusterLabels[cid]) ? clusterLabels[cid] : `Cluster ${cid}`;
          label.appendChild(document.createTextNode(clusterName));

          clusterLegendContainer.appendChild(label);
        });

        // Initially all clusters visible
        visibleClusters = new Set(clusters);
        updateVisibilityAndColors();
      }

      buildClusterLegend();
    });
    </script>
    """

def html_search_bar():
    return """
    <div style="position:fixed; top:20px; left:10px; z-index:1000; background:white; padding:10px; border-radius:5px; max-width: 280px;">
      <input type="text" id="nodeSearch" placeholder="Search for drug or disease" style="width:250px; padding:5px;" autocomplete="off"/>
      <button onclick="searchNode()">Search</button>
      <div id="autocompleteList" style="position: absolute; background: white; border: 1px solid #d4d4d4; max-height: 150px; overflow-y: auto; width: 250px; display: none; z-index: 1001;"></div>
    </div>

    <script type="text/javascript">
    window.addEventListener("load", function () {
      if (typeof network === 'undefined') return;

      const searchInput = document.getElementById("nodeSearch");
      const autocompleteList = document.getElementById("autocompleteList");

      const allNodes = network.body.data.nodes.get();
      const allNodeLabels = allNodes.map(n => n.label);

      // Autocomplete behavior
      searchInput.addEventListener("input", function () {
        const val = this.value.trim().toLowerCase();
        autocompleteList.innerHTML = "";
        if (!val) {
          autocompleteList.style.display = "none";
          return;
        }

        const matches = allNodeLabels.filter(label => label.toLowerCase().includes(val)).slice(0, 10);
        if (matches.length === 0) {
          autocompleteList.style.display = "none";
          return;
        }

        matches.forEach(match => {
          const item = document.createElement("div");
          item.style.padding = "6px";
          item.style.cursor = "pointer";
          const idx = match.toLowerCase().indexOf(val);
          item.innerHTML = `${match.substring(0, idx)}<strong>${match.substring(idx, idx + val.length)}</strong>${match.substring(idx + val.length)}`;
          item.addEventListener("click", () => {
            searchInput.value = match;
            autocompleteList.innerHTML = "";
            autocompleteList.style.display = "none";
            searchNode();
          });
          autocompleteList.appendChild(item);
        });

        autocompleteList.style.display = "block";
      });

      // Hide autocomplete on click away
      document.addEventListener("click", (e) => {
        if (e.target !== searchInput && e.target.parentNode !== autocompleteList) {
          autocompleteList.innerHTML = "";
          autocompleteList.style.display = "none";
        }
      });

      // Search node function
      window.searchNode = function () {
        const input = searchInput.value.toLowerCase();
        if (!input) return;
        const matches = allNodes.filter(n => n.label.toLowerCase().includes(input));
        if (matches.length === 0) {
          alert("No match found.");
          return;
        }
        const nodeId = matches[0].id;
        network.selectNodes([nodeId]);
        network.focus(nodeId, { scale: 1.5, animation: true });
      };
    });
    </script>
    """


def html_info_panel():
    return """
    <!-- Info panel -->
    <div id="infoPanel" style="
      position: fixed;
      top: 20px;
      right: 20px;
      width: 320px;
      padding: 20px;
      background: rgba(255,255,255,0.8);
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.2);
      font-family: Arial, sans-serif;
      z-index: 9999;
      display: none;
      margin-bottom: 8px; 
      line-height: 1.5;
      max-height: 600px;
      overflow-y: auto;
    ">
      <h2 id="panelTitle" style="margin: 0 0 10px 0; font-size: 24px; color: #000;"></h2>
      <div id="panelDetails" style="font-size: 14px; color: #333;"></div>
    </div>

    <script type="text/javascript">
      window.addEventListener("load", function () {
        if (typeof network === 'undefined') {
          console.error("Network object not found.");
          return;
        }

        network.on("click", function (params) {
          if (params.nodes.length === 0) {
            document.getElementById("infoPanel").style.display = "none";
            return;
          }

          const nodeId = params.nodes[0];
          const node = network.body.data.nodes.get(nodeId);
          if (!node || node.type !== "Medication") {
            document.getElementById("infoPanel").style.display = "none";
            return;
          }

          const title = typeof node.label === "string" ? node.label.replace(/^"|"$/g, "") : "Unnamed";
          const detailsHTML = node.panel_info || "<em>No additional details available.</em>";

          document.getElementById("panelTitle").innerText = title;
          document.getElementById("panelDetails").innerHTML = detailsHTML;
          document.getElementById("infoPanel").style.display = "block";
        });
      });
    </script>
    """
