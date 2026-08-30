figma.showUI(__html__, {
  width: 600,
  height: 500
});


function extractNode(node: SceneNode): any {

  const data: any = {
    id: node.id,
    name: node.name,
    type: node.type,
    x: node.x,
    y: node.y,
    width: node.width,
    height: node.height
  };


  // TEXT
  if (node.type === "TEXT") {

    data.characters = node.characters;

  }


  // CHILDREN
  if ("children" in node) {

    data.children = node.children.map(
      child => extractNode(child)
    );

  }


  return data;
}


figma.ui.onmessage = (msg) => {

  console.log("Message received:", msg);


  if (msg.type === "extract-design") {

    const selection = figma.currentPage.selection;


    console.log(
      "Selected nodes:",
      selection
    );


    if (selection.length === 0) {

      figma.ui.postMessage({
        type: "error",
        message: "NO SELECTION"
      });

      return;
    }


    const selectedNode = selection[0];


    const designData = extractNode(
      selectedNode
    );


    console.log(
      "Extracted data:",
      designData
    );


    figma.ui.postMessage({

      type: "design-data",

      data: designData

    });

  }


  if (msg.type === "cancel") {

    figma.closePlugin();

  }

};