def html_search_bar():
    return """
    <!-- Search bar -->
    <div style="position:fixed; top:20px; left:10px; z-index:1000; background:white; padding:10px; border-radius:5px;">
      <input type="text" id="nodeSearch" placeholder="Search for drug or disease" style="width:250px; padding:5px;" autocomplete="off"/>
      <button onclick="searchNode()">Search</button>
      <div id="autocompleteList" style="
        position: absolute;
        background: white;
        border: 1px solid #d4d4d4;
        max-height: 150px;
        overflow-y: auto;
        width: 250px;
        display: none;
        z-index: 1001;
      "></div>
    </div>

    <script type="text/javascript">
    window.addEventListener("load", function () {
      if (typeof network === 'undefined') {
        console.error("Network object not found.");
        return;
      }

      const searchInput = document.getElementById("nodeSearch");
      const autocompleteList = document.getElementById("autocompleteList");

      const allNodes = network.body.data.nodes.get();
      const allNodeLabels = allNodes.map(n => n.label);

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
            searchNode();  // Trigger search with exact match
          });

          autocompleteList.appendChild(item);
        });

        autocompleteList.style.display = "block";
      });

      document.addEventListener("click", (e) => {
        if (e.target !== searchInput && e.target.parentNode !== autocompleteList) {
          autocompleteList.innerHTML = "";
          autocompleteList.style.display = "none";
        }
      });

      window.searchNode = function () {
        const input = searchInput.value.toLowerCase();
        if (!input) return;

        const matches = allNodes.filter(n => n.label.toLowerCase().includes(input));
        if (matches.length === 0) {
          alert("No match");
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
