def normalize_node(node):
    """
    Convert a raw Figma node into a simpler structure.
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
        "children": []
    }

    # If this node contains text
    if node.get("type") == "TEXT":

        characters = node.get("characters")

        if characters:
            normalized["texts"].append(characters)

    # Process children recursively
    for child in node.get("children", []):

        child_normalized = normalize_node(child)

        normalized["children"].append(
            child_normalized
        )

        # Collect text from children
        normalized["texts"].extend(
            child_normalized.get("texts", [])
        )

    return normalized