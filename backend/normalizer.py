def normalize_node(node):
    """
    Convert a raw Figma node into a richer normalized structure.
    """

    normalized = {
        "id": node.get("id"),
        "name": node.get("name"),
        "figma_type": node.get("type"),

        "position": {
            "x": node.get("x", 0),
            "y": node.get("y", 0)
        },

        "size": {
            "width": node.get("width", 0),
            "height": node.get("height", 0)
        },

        "texts": [],

        "layout": {
            "mode": node.get("layoutMode"),
            "item_spacing": node.get("itemSpacing"),
            "padding": {
                "top": node.get("paddingTop"),
                "right": node.get("paddingRight"),
                "bottom": node.get("paddingBottom"),
                "left": node.get("paddingLeft")
            }
        },

        "style": {
            "opacity": node.get("opacity"),
            "corner_radius": node.get("cornerRadius"),
            "fills": node.get("fills", []),
            "strokes": node.get("strokes", []),
            "stroke_weight": node.get("strokeWeight")
        },

        "children": []
    }

    # -------------------------------------------------------
    # TEXT NODE
    # -------------------------------------------------------

    if node.get("type") == "TEXT":

        characters = node.get("characters")

        if characters:

            normalized["texts"].append(
                characters
            )

        # Preserve useful text information
        normalized["text_style"] = {
            "font_size": (
                node.get("style", {})
                .get("fontSize")
            ),

            "font_family": (
                node.get("style", {})
                .get("fontFamily")
            ),

            "font_weight": (
                node.get("style", {})
                .get("fontWeight")
            ),

            "text_align": (
                node.get("style", {})
                .get("textAlignHorizontal")
            )
        }

    # -------------------------------------------------------
    # CHILDREN — recurse and bubble texts up (de-duplicated)
    # -------------------------------------------------------

    seen_texts = set(normalized["texts"])

    for child in node.get("children", []):

        child_normalized = normalize_node(child)
        normalized["children"].append(child_normalized)

        # Bubble up child texts, skipping duplicates
        for t in child_normalized["texts"]:
            if t not in seen_texts:
                seen_texts.add(t)
                normalized["texts"].append(t)

    return normalized