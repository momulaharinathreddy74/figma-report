import { SUPABASE_URL, SUPABASE_KEY } from "./config.local";

figma.showUI(__html__, {
  width: 600,
  height: 500,
});

let lastDesignData: any = null;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Safely read a paint array and return a serialisable version. */
function extractPaints(paints: readonly Paint[]): any[] {
  return paints.map((p) => {
    const base: any = { type: p.type, visible: p.visible ?? true, opacity: p.opacity ?? 1 };
    if (p.type === "SOLID") {
      base.color = p.color; // { r, g, b } 0-1 floats
    } else if (
      p.type === "GRADIENT_LINEAR" ||
      p.type === "GRADIENT_RADIAL" ||
      p.type === "GRADIENT_ANGULAR" ||
      p.type === "GRADIENT_DIAMOND"
    ) {
      base.gradientStops = p.gradientStops;
    } else if (p.type === "IMAGE") {
      base.scaleMode = p.scaleMode;
    }
    return base;
  });
}

/** Safely read fill / stroke / effect / style data from a node. */
function extractStyles(node: SceneNode): Record<string, any> {
  const styles: Record<string, any> = {};

  // opacity
  if ("opacity" in node) styles.opacity = (node as BlendMixin).opacity;

  // blendMode
  if ("blendMode" in node) styles.blendMode = (node as BlendMixin).blendMode;

  // visible
  styles.visible = node.visible;

  // fills
  if ("fills" in node) {
    const fills = (node as GeometryMixin).fills;
    if (fills !== figma.mixed && Array.isArray(fills)) {
      styles.fills = extractPaints(fills);
    }
  }

  // strokes
  if ("strokes" in node) {
    const strokes = (node as GeometryMixin).strokes;
    if (Array.isArray(strokes)) {
      styles.strokes = extractPaints(strokes);
    }
  }

  // strokeWeight
  if ("strokeWeight" in node) {
    const sw = (node as GeometryMixin).strokeWeight;
    if (sw !== figma.mixed) styles.strokeWeight = sw;
  }

  // corner radius
  if ("cornerRadius" in node) {
    const cr = (node as CornerMixin).cornerRadius;
    if (cr !== figma.mixed) styles.cornerRadius = cr;
  }

  // effects (shadows, blurs)
  if ("effects" in node) {
    styles.effects = (node as BlendMixin).effects;
  }

  return styles;
}

/** Safely read typography data from a TEXT node. */
function extractTextStyles(node: TextNode): Record<string, any> {
  const t: Record<string, any> = {};

  try { t.fontSize        = node.fontSize        === figma.mixed ? "mixed" : node.fontSize;        } catch (_) { /* skip */ }
  try { t.fontName        = node.fontName         === figma.mixed ? "mixed" : node.fontName;        } catch (_) { /* skip */ }
  try { t.fontWeight      = node.fontWeight       === figma.mixed ? "mixed" : node.fontWeight;      } catch (_) { /* skip */ }
  try { t.textAlignHorizontal = node.textAlignHorizontal; } catch (_) { /* skip */ }
  try { t.textAlignVertical   = node.textAlignVertical;   } catch (_) { /* skip */ }
  try { t.lineHeight      = node.lineHeight       === figma.mixed ? "mixed" : node.lineHeight;      } catch (_) { /* skip */ }
  try { t.letterSpacing   = node.letterSpacing    === figma.mixed ? "mixed" : node.letterSpacing;   } catch (_) { /* skip */ }
  try { t.textDecoration  = node.textDecoration   === figma.mixed ? "mixed" : node.textDecoration;  } catch (_) { /* skip */ }
  try { t.textCase        = node.textCase         === figma.mixed ? "mixed" : node.textCase;        } catch (_) { /* skip */ }

  return t;
}

// ---------------------------------------------------------------------------
// Core extractor — depth-limited to prevent stack overflow on very deep trees
// ---------------------------------------------------------------------------
const MAX_DEPTH = 50;

function extractNode(node: SceneNode, depth = 0): any {
  if (depth > MAX_DEPTH) {
    return { id: node.id, name: node.name, type: node.type, _truncated: true };
  }

  const data: any = {
    id: node.id,
    name: node.name,
    type: node.type,
  };

  // Layout
  if ("x" in node)      data.x      = (node as LayoutMixin).x;
  if ("y" in node)      data.y      = (node as LayoutMixin).y;
  if ("width" in node)  data.width  = (node as LayoutMixin).width;
  if ("height" in node) data.height = (node as LayoutMixin).height;

  // Auto-layout
  if ("layoutMode" in node) {
    const f = node as FrameNode;
    data.layoutMode        = f.layoutMode;
    data.primaryAxisAlignItems   = f.primaryAxisAlignItems;
    data.counterAxisAlignItems   = f.counterAxisAlignItems;
    data.paddingTop        = f.paddingTop;
    data.paddingBottom     = f.paddingBottom;
    data.paddingLeft       = f.paddingLeft;
    data.paddingRight      = f.paddingRight;
    data.itemSpacing       = f.itemSpacing;
  }

  // Styles (fills, strokes, opacity, effects, …)
  Object.assign(data, extractStyles(node));

  // TEXT — .characters can throw if the font isn't loaded
  if (node.type === "TEXT") {
    try {
      data.characters = node.characters;
    } catch (_e) {
      data.characters = "[font not loaded]";
    }
    Object.assign(data, extractTextStyles(node));
  }

  // CHILDREN — recurse with incremented depth
  if ("children" in node) {
    data.children = (node as ChildrenMixin).children.map((child) =>
      extractNode(child as SceneNode, depth + 1)
    );
  }

  return data;
}

// ---------------------------------------------------------------------------
// Message handler
// ---------------------------------------------------------------------------
figma.ui.onmessage = async (msg) => {
  console.log("Message received:", msg.type);

  // ── Extract ──────────────────────────────────────────────────────────────
  if (msg.type === "extract-design") {
    const selection = figma.currentPage.selection;

    if (selection.length === 0) {
      figma.ui.postMessage({ type: "error", message: "Please select a frame or element first." });
      return;
    }

    const selectedNode = selection[0];

    let designData: any;
    try {
      designData = extractNode(selectedNode);
    } catch (err) {
      console.error("Extraction failed:", err);
      figma.ui.postMessage({
        type: "error",
        message: "Extraction failed: " + (err instanceof Error ? err.message : String(err)),
      });
      return;
    }

    lastDesignData = designData;

    figma.ui.postMessage({ type: "design-data", data: designData });
  }

  // ── Save ─────────────────────────────────────────────────────────────────
  if (msg.type === "save-design") {

    if (!lastDesignData) {

      figma.ui.postMessage({
        type: "save-error",
        message: "No design data to save. Extract a design first.",
      });

      return;
    }

    figma.ui.postMessage({
      type: "perform-save",

      url: "http://127.0.0.1:8001/designs",

      body: {
        name: lastDesignData.name,
        figma_node_id: lastDesignData.id,
        design_json: lastDesignData,
      },
    });
  }

  // ── Cancel ────────────────────────────────────────────────────────────────
  if (msg.type === "cancel") {
    figma.closePlugin();
  }
};
