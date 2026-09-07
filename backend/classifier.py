import re


# --------------------------------------------------
# FIGMA → CLASSIFIER SHAPE TRANSFORMER
# Converts raw Figma JSON (x/y/width/height/characters)
# into the shape the classifier expects
# (position/size/texts)
# --------------------------------------------------

def transform_node(node: dict) -> dict:
    """Recursively reshape a raw Figma node into classifier-friendly shape."""

    # Collect all text strings from TEXT nodes in the subtree
    texts = _collect_characters(node)

    transformed = {
        "id":       node.get("id"),
        "name":     node.get("name"),
        "type":     node.get("type"),
        "position": {
            "x": node.get("x", 0),
            "y": node.get("y", 0),
        },
        "size": {
            "width":  node.get("width", 0),
            "height": node.get("height", 0),
        },
        "texts": texts,
        "children": [
            transform_node(child)
            for child in node.get("children", [])
        ],
    }

    return transformed


def _collect_characters(node: dict) -> list[str]:
    """Walk a raw Figma node tree and collect all non-empty characters values."""
    results = []

    if node.get("type") == "TEXT" and node.get("characters"):
        chars = node["characters"]
        if chars and chars != "[font not loaded]":
            results.append(chars)

    for child in node.get("children", []):
        results.extend(_collect_characters(child))

    return results


# --------------------------------------------------
# TEXT HELPERS
# --------------------------------------------------

def collect_text(node):
    """Collect texts from classifier-shaped node (has 'texts' field)."""
    texts = []

    for text in node.get("texts", []):
        if text:
            texts.append(str(text))

    for child in node.get("children", []):
        texts.extend(collect_text(child))

    return texts


def get_all_text(node):
    return " ".join(collect_text(node)).strip()


# --------------------------------------------------
# BASIC HELPERS
# --------------------------------------------------

def contains_number(text):
    return bool(re.search(r"\d", text))


def contains_percentage(text):
    return bool(re.search(r"\d+(\.\d+)?\s*%", text))


def word_exists(text, word):
    """
    Check complete words instead of substrings.

    Example:
    'table' in 'tabler.io' -> False
    'table' in 'sales table' -> True
    """
    return bool(
        re.search(
            rf"\b{re.escape(word)}\b",
            text.lower()
        )
    )


# --------------------------------------------------
# KPI
# --------------------------------------------------

def kpi_score(node, text):

    score = 0

    name = (node.get("name") or "").lower()
    text_lower = text.lower()

    kpi_keywords = [
        "revenue",
        "sales",
        "profit",
        "income",
        "users",
        "customers",
        "orders",
        "growth",
        "conversion",
        "rate",
        "deals",
        "target",
        "performance",
        "goal",
        "total",
        "average",
        "amount",
        "cost",
        "expenses",
        "visitors"
    ]

    for keyword in kpi_keywords:
        if word_exists(text_lower, keyword):
            score += 3
            break

    if contains_number(text):
        score += 2

    if contains_percentage(text):
        score += 3

    if any(
        word in name
        for word in [
            "widget",
            "card",
            "kpi",
            "metric",
            "big number"
        ]
    ):
        score += 2

    return score


# --------------------------------------------------
# CHART
# --------------------------------------------------

def chart_score(node, text):

    score = 0

    name = (node.get("name") or "").lower()
    text_lower = text.lower()

    chart_keywords = [
        "chart",
        "graph",
        "trend",
        "analytics",
        "statistics",
        "monthly",
        "weekly",
        "yearly",
        "timeline",
        "distribution",
        "comparison"
    ]

    for keyword in chart_keywords:

        if word_exists(text_lower, keyword):
            score += 3

    if word_exists(name, "chart"):
        score += 5

    if word_exists(name, "graph"):
        score += 5

    if len(node.get("children", [])) >= 5:
        score += 1

    return score


# --------------------------------------------------
# TABLE
# --------------------------------------------------

def table_score(node, text):

    score = 0

    name = (node.get("name") or "").lower()
    text_lower = text.lower()

    table_keywords = [
        "table",
        "transactions",
        "records",
        "employees",
        "products",
        "customers",
        "orders",
        "invoice",
        "status",
        "category",
        "description"
    ]

    for keyword in table_keywords:

        if word_exists(text_lower, keyword):
            score += 3
            break

    if word_exists(name, "table"):
        score += 5

    if word_exists(name, "grid"):
        score += 5

    return score


# --------------------------------------------------
# CLASSIFY COMPONENT
# --------------------------------------------------

def classify_component(node):

    name = (node.get("name") or "").lower()

    # ----------------------------------------------
    # Ignore obvious visual primitives
    # ----------------------------------------------

    ignored_names = [
        "vector",
        "ellipse",
        "rectangle",
        "line",
        "mask group",
        "icon",
        "avatar"
    ]

    for ignored in ignored_names:

        if ignored in name:
            return "OTHER"

    # ----------------------------------------------
    # Get all text inside component
    # ----------------------------------------------

    text = get_all_text(node)

    # ----------------------------------------------
    # Score
    # ----------------------------------------------

    scores = {
        "KPI": kpi_score(node, text),
        "CHART": chart_score(node, text),
        "TABLE": table_score(node, text)
    }

    best_type = max(
        scores,
        key=scores.get
    )

    best_score = scores[best_type]

    # ----------------------------------------------
    # Minimum confidence
    # ----------------------------------------------

    if best_score < 4:
        return "OTHER"

    return best_type


# --------------------------------------------------
# TREE CLASSIFICATION
# --------------------------------------------------

def classify_tree(node: dict, _already_transformed: bool = False) -> dict:
    """
    Classify a node tree.
    Accepts either raw Figma JSON or pre-transformed nodes.
    Pass raw Figma JSON directly — it will be transformed automatically.
    """

    # Transform raw Figma shape into classifier shape on first call
    if not _already_transformed:
        node = transform_node(node)

    component_type = classify_component(node)

    result = {
        "id":       node.get("id"),
        "name":     node.get("name"),
        "type":     component_type,
        "position": node.get("position"),
        "size":     node.get("size"),
        "texts":    node.get("texts", []),
        "children": [],
    }

    for child in node.get("children", []):
        result["children"].append(
            classify_tree(child, _already_transformed=True)
        )

    return result