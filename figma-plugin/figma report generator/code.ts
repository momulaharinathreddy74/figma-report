import { SUPABASE_URL, SUPABASE_KEY } from "./config.local";

figma.showUI(__html__, {
  width: 600,
  height: 500,
});

let lastDesignData: any = null;

function extractNode(node: SceneNode): any {
  const data: any = {
    id: node.id,
    name: node.name,
    type: node.type,
    x: node.x,
    y: node.y,
    width: node.width,
    height: node.height,
  };

  // TEXT
  if (node.type === "TEXT") {
    data.characters = node.characters;
  }

  // CHILDREN
  if ("children" in node) {
    data.children = node.children.map((child) => extractNode(child));
  }

  return data;
}

figma.ui.onmessage = async (msg) => {
  console.log("Message received:", msg);

  if (msg.type === "extract-design") {
    const selection = figma.currentPage.selection;

    console.log("Selected nodes:", selection);

    if (selection.length === 0) {
      figma.ui.postMessage({
        type: "error",
        message: "NO SELECTION",
      });
      return;
    }

    const selectedNode = selection[0];
    const designData = extractNode(selectedNode);

    console.log("Extracted data:", designData);

    lastDesignData = designData;

    figma.ui.postMessage({
      type: "design-data",
      data: designData,
    });
  }

  if (msg.type === "save-design") {
    if (!lastDesignData) {
      figma.ui.postMessage({
        type: "save-error",
        message: "No design data to save. Extract a design first.",
      });
      return;
    }

    // Delegate the fetch to the UI iframe.
    // The plugin main sandbox has unreliable fetch support; the UI runs
    // in a real browser iframe with full, unrestricted fetch access.
    figma.ui.postMessage({
      type: "perform-save",
      url: `${SUPABASE_URL}/rest/v1/designs`,
      apikey: SUPABASE_KEY,
      body: {
        name: lastDesignData.name,
        figma_node_id: lastDesignData.id,
        design_json: lastDesignData,
      },
    });
  }

  if (msg.type === "cancel") {
    figma.closePlugin();
  }
};
