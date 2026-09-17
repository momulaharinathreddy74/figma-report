import re
from typing import Any, Dict, List, Tuple


# ============================================================
# KEYWORDS
# ============================================================

KEYWORDS = {
    "KPI": [
        "revenue", "sales", "profit", "income", "expense",
        "orders", "customers", "users", "growth", "conversion",
        "sessions", "downloads", "transactions", "balance",
        "budget", "target", "total", "average", "avg"
    ],

    "CHART": [
        "chart", "graph", "analytics", "trend", "statistics",
        "performance", "overview", "activity"
    ],

    "TABLE": [
        "table", "records", "transactions", "transaction history",
        "recent orders", "recent transactions", "customer list",
        "user list"
    ],

    "SIDEBAR": [
        "sidebar", "side bar", "side menu", "left menu",
        "navigation panel"
    ],

    "NAV": [
        "navbar", "navigation", "menu", "breadcrumb"
    ],

    "HEADER": [
        "header", "topbar", "top bar", "toolbar",
        "page title", "welcome", "greeting"
    ],

    "FILTER": [
        "filter", "filters", "search", "sort", "dropdown",
        "select", "date picker", "calendar", "date range"
    ],

    "LIST": [
        "list", "activity", "notifications", "messages",
        "recent", "items", "tasks", "events"
    ]
}


MIN_SCORE = 5
MIN_MARGIN = 2


# ============================================================
# BASIC HELPERS
# ============================================================

def get_name(node: Dict[str, Any]) -> str:
    return str(node.get("name", "")).strip()


def get_type(node: Dict[str, Any]) -> str:
    return str(
        node.get("figma_type") or node.get("type") or ""
    ).upper()


def get_texts(node: Dict[str, Any]) -> List[str]:
    texts = node.get("texts", [])

    if isinstance(texts, str):
        return [texts]

    if not isinstance(texts, list):
        return []

    result = []

    for item in texts:
        if isinstance(item, dict):
            text = (
                item.get("characters")
                or item.get("text")
                or item.get("value")
                or item.get("content")
            )
            if text:
                result.append(str(text))
        elif item:
            result.append(str(item))

    if node.get("characters"):
        result.append(str(node["characters"]))

    if node.get("text"):
        result.append(str(node["text"]))

    return result


def get_all_text(node: Dict[str, Any]) -> str:
    return " ".join(get_texts(node)).lower().strip()


def get_children(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    children = node.get("children", [])

    if not isinstance(children, list):
        return []

    return [
        child for child in children
        if isinstance(child, dict)
    ]


def get_position(node: Dict[str, Any]) -> Tuple[float, float]:
    position = node.get("position", {})

    if not isinstance(position, dict):
        position = {}

    try:
        x = float(position.get("x", node.get("x", 0)) or 0)
        y = float(position.get("y", node.get("y", 0)) or 0)
        return x, y
    except (TypeError, ValueError):
        return 0.0, 0.0


def get_size(node: Dict[str, Any]) -> Tuple[float, float]:
    size = node.get("size", {})

    if not isinstance(size, dict):
        size = {}

    try:
        width = float(size.get("width", node.get("width", 0)) or 0)
        height = float(size.get("height", node.get("height", 0)) or 0)
        return width, height
    except (TypeError, ValueError):
        return 0.0, 0.0


def contains_keyword(text: str, keywords: List[str]) -> bool:
    text = text.lower()

    return any(keyword in text for keyword in keywords)


def matched_keywords(text: str, keywords: List[str]) -> List[str]:
    text = text.lower()

    return [
        keyword for keyword in keywords
        if keyword in text
    ]


def is_numeric(text: str) -> bool:
    text = text.strip().replace(",", "")

    return bool(
        re.fullmatch(
            r"[₹$€£]?\s*-?\d+(\.\d+)?[KMBkmb%]?",
            text
        )
    )


def is_percentage(text: str) -> bool:
    return bool(
        re.search(r"[-+]?\d+(\.\d+)?\s*%", text)
    )


def is_money(text: str) -> bool:
    return bool(
        re.search(
            r"[₹$€£]\s*\d+|\d+\s*(usd|inr|eur|gbp)",
            text.lower()
        )
    )


def is_date(text: str) -> bool:
    return bool(
        re.search(
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
            r"|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b"
            r"|\b(today|yesterday|tomorrow)\b",
            text.lower()
        )
    )


def is_visual_only(node: Dict[str, Any]) -> bool:
    visual_types = {
        "RECTANGLE",
        "ELLIPSE",
        "LINE",
        "VECTOR",
        "POLYGON",
        "STAR"
    }

    return (
        get_type(node) in visual_types
        and len(get_texts(node)) == 0
    )


# ============================================================
# DASHBOARD ROOT DETECTION
# ============================================================

def is_dashboard_root(node: Dict[str, Any]) -> bool:
    name = get_name(node).lower()

    root_words = [
        "dashboard",
        "report",
        "analytics",
        "admin panel",
        "admin dashboard",
        "main frame",
        "screen",
        "canvas"
    ]

    return (
        any(word in name for word in root_words)
        and len(get_children(node)) > 0
    )


# ============================================================
# COMPONENT SCORING
# ============================================================

def calculate_scores(node: Dict[str, Any]) -> Dict[str, int]:
    name = get_name(node).lower()
    text = get_all_text(node)
    combined = f"{name} {text}"

    children = get_children(node)
    texts = get_texts(node)

    width, height = get_size(node)

    scores = {label: 0 for label in KEYWORDS}

    # --------------------------------------------------------
    # Keyword-based scoring
    # --------------------------------------------------------

    for label, words in KEYWORDS.items():

        if contains_keyword(name, words):
            scores[label] += 6

        if contains_keyword(text, words):
            scores[label] += 2

    # --------------------------------------------------------
    # KPI-specific signals
    # --------------------------------------------------------

    numeric_values = sum(
        is_numeric(t) or is_percentage(t) or is_money(t)
        for t in texts
    )

    if numeric_values >= 1:
        scores["KPI"] += 4

    if numeric_values >= 2:
        scores["KPI"] += 2

    if any(is_percentage(t) for t in texts):
        scores["KPI"] += 2

    if any(is_money(t) for t in texts):
        scores["KPI"] += 2

    if 0 < len(texts) <= 6:
        scores["KPI"] += 1

    # KPI cards are compact — large nodes are not KPIs
    if width > 700 or height > 350:
        scores["KPI"] -= 8

    # KPI cards have few texts — too many means it's a chart/table
    if len(texts) > 10:
        scores["KPI"] -= 6
    elif len(texts) > 6:
        scores["KPI"] -= 3

    # --------------------------------------------------------
    # Chart-specific signals
    # --------------------------------------------------------

    if len(children) >= 5:
        scores["CHART"] += 3

    if len(children) >= 10:
        scores["CHART"] += 2

    if width > 0 and height > 0 and width / height > 1.2:
        scores["CHART"] += 2

    month_count = sum(
        1 for t in texts
        if t.strip().lower()[:3] in {
            "jan", "feb", "mar", "apr", "may", "jun",
            "jul", "aug", "sep", "oct", "nov", "dec"
        }
    )

    if month_count >= 6:
        scores["CHART"] += 8
    elif month_count >= 3:
        scores["CHART"] += 5
    elif month_count >= 1:
        scores["CHART"] += 2

    day_count = sum(
        1 for t in texts
        if t.strip().lower()[:3] in {
            "sun", "mon", "tue", "wed", "thu", "fri", "sat"
        }
    )

    if day_count >= 5:
        scores["CHART"] += 7
    elif day_count >= 3:
        scores["CHART"] += 4

    # Many money/numeric values in a large node → chart axes
    if numeric_values >= 4 and (width > 300 or height > 200):
        scores["CHART"] += 4

    pct_count = sum(1 for t in texts if is_percentage(t))
    if pct_count >= 3:
        scores["CHART"] += 6

    # --------------------------------------------------------
    # Table-specific signals
    # --------------------------------------------------------

    table_header_words = {
        "name", "price", "status", "options", "date", "amount",
        "quantity", "total", "description", "category", "id",
        "type", "email", "phone", "tracking", "order", "orders",
        "product", "products", "in stock", "action", "actions"
    }
    header_hits = sum(1 for t in texts if t.lower().strip() in table_header_words)
    if header_hits >= 4:
        scores["TABLE"] += 10
    elif header_hits >= 2:
        scores["TABLE"] += 5

    if len(texts) >= 6:
        scores["TABLE"] += 2

    if len(children) >= 8:
        scores["TABLE"] += 3

    if sum(is_date(t) for t in texts) >= 2:
        scores["TABLE"] += 2

    # Wide and tall → likely table
    if width >= 500 and height >= 150:
        scores["TABLE"] += 3

    # --------------------------------------------------------
    # Sidebar-specific signals
    # --------------------------------------------------------

    if len(children) >= 3:
        scores["SIDEBAR"] += 2

    if width > 0 and height > 0 and width / height < 0.45:
        scores["SIDEBAR"] += 3

    # --------------------------------------------------------
    # Navigation-specific signals
    # --------------------------------------------------------

    if len(children) >= 2:
        scores["NAV"] += 2

    if width > 0 and height > 0 and width / height > 2:
        scores["NAV"] += 2

    # --------------------------------------------------------
    # Header-specific signals
    # --------------------------------------------------------

    if len(children) >= 1:
        scores["HEADER"] += 1

    if width > 0 and height > 0 and width / height > 2:
        scores["HEADER"] += 2

    # --------------------------------------------------------
    # Filter-specific signals
    # --------------------------------------------------------

    if 1 <= len(children) <= 10:
        scores["FILTER"] += 2

    if any(is_date(t) for t in texts):
        scores["FILTER"] += 2

    # --------------------------------------------------------
    # List-specific signals
    # --------------------------------------------------------

    if len(children) >= 3:
        scores["LIST"] += 2

    if len(children) >= 8:
        scores["LIST"] += 2

    return scores


# ============================================================
# CLASSIFICATION
# ============================================================

def classify_node(node: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(node, dict):
        return {
            "label": "OTHER",
            "confidence": 0.0,
            "score": 0,
            "scores": {}
        }

    if is_visual_only(node):
        return {
            "label": "OTHER",
            "confidence": 0.0,
            "score": 0,
            "scores": {},
            "reason": "visual_only"
        }

    scores = calculate_scores(node)

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True
    )

    best_label, best_score = ranked[0]
    second_score = ranked[1][1]

    if best_score < MIN_SCORE:
        return {
            "label": "OTHER",
            "confidence": 0.0,
            "score": best_score,
            "scores": scores,
            "reason": "low_score"
        }

    if best_score - second_score < MIN_MARGIN:
        return {
            "label": "OTHER",
            "confidence": 0.0,
            "score": best_score,
            "scores": scores,
            "reason": "ambiguous"
        }

    max_score = max(scores.values()) or 1

    confidence = round(
        min(
            0.99,
            (best_score / max_score) * 0.7
            + ((best_score - second_score) / 10) * 0.3
        ),
        3
    )

    return {
        "label": best_label,
        "confidence": confidence,
        "score": best_score,
        "scores": scores,
        "keywords": matched_keywords(
            get_name(node) + " " + get_all_text(node),
            KEYWORDS[best_label]
        )
    }


# ============================================================
# FIELD EXTRACTION
# ============================================================

def extract_kpi_fields(node: Dict[str, Any]) -> Dict[str, Any]:
    texts = get_texts(node)

    value = None
    title = None
    description = None

    for text in texts:
        text = text.strip()

        if not text:
            continue

        if value is None and (
            is_numeric(text)
            or is_percentage(text)
            or is_money(text)
        ):
            value = text

        elif title is None:
            title = text

        elif description is None:
            description = text

    return {
        "title": title,
        "value": value,
        "description": description
    }


def extract_chart_fields(node: Dict[str, Any]) -> Dict[str, Any]:
    name = (
        get_name(node) + " " + get_all_text(node)
    ).lower()

    chart_type = "UNKNOWN"

    if "line" in name:
        chart_type = "LINE"
    elif "bar" in name:
        chart_type = "BAR"
    elif "pie" in name or "donut" in name:
        chart_type = "PIE"
    elif "area" in name:
        chart_type = "AREA"

    title = None

    for text in get_texts(node):
        if (
            not is_numeric(text)
            and not is_percentage(text)
            and not is_date(text)
        ):
            title = text.strip()
            break

    return {
        "title": title,
        "chart_type": chart_type
    }


def extract_table_fields(node: Dict[str, Any]) -> Dict[str, Any]:
    texts = get_texts(node)

    title = texts[0] if texts else get_name(node)

    return {
        "title": title,
        "columns": [],
        "rows": []
    }


def extract_generic_fields(
    node: Dict[str, Any],
    label: str
) -> Dict[str, Any]:

    texts = get_texts(node)

    if label in ["SIDEBAR", "NAV", "LIST"]:
        return {
            "title": get_name(node),
            "items": texts
        }

    if label == "HEADER":
        return {
            "title": texts[0] if texts else get_name(node),
            "texts": texts
        }

    if label == "FILTER":
        return {
            "label": get_name(node),
            "options": texts
        }

    return {}


def extract_fields(
    node: Dict[str, Any],
    label: str
) -> Dict[str, Any]:

    if label == "KPI":
        return extract_kpi_fields(node)

    if label == "CHART":
        return extract_chart_fields(node)

    if label == "TABLE":
        return extract_table_fields(node)

    return extract_generic_fields(node, label)


# ============================================================
# COMPONENT CREATION
# ============================================================

def build_component(
    node: Dict[str, Any],
    classification: Dict[str, Any]
) -> Dict[str, Any]:

    label = classification["label"]
    x, y = get_position(node)
    width, height = get_size(node)

    return {
        "id": node.get("id"),
        "name": get_name(node),
        "type": label,
        "figma_type": get_type(node),
        "position": {
            "x": x,
            "y": y
        },
        "size": {
            "width": width,
            "height": height
        },
        "confidence": classification["confidence"],
        "score": classification["score"],
        "signals": classification.get("keywords", []),
        "fields": extract_fields(node, label)
    }


# ============================================================
# RECURSIVE TREE CLASSIFICATION
# ============================================================

def find_components(
    node: Dict[str, Any],
    components: List[Dict[str, Any]]
) -> None:

    if not isinstance(node, dict):
        return

    # Skip dashboard root and inspect its children
    if is_dashboard_root(node):
        for child in get_children(node):
            find_components(child, components)
        return

    classification = classify_node(node)
    label = classification["label"]

    # If classified as OTHER, continue searching children
    if label == "OTHER":
        for child in get_children(node):
            find_components(child, components)
        return

    # Add detected component
    components.append(
        build_component(node, classification)
    )


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def classify_tree(root: Dict[str, Any]) -> Dict[str, Any]:
    components = []

    find_components(root, components)

    components.sort(
        key=lambda item: (
            item["position"]["y"],
            item["position"]["x"]
        )
    )

    return {
        "dashboard_name": get_name(root) or "Untitled Dashboard",
        "component_count": len(components),
        "components": components
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    sample_data = {
        "id": "root",
        "name": "Sales Dashboard",
        "figma_type": "FRAME",
        "position": {"x": 0, "y": 0},
        "size": {"width": 1440, "height": 900},
        "children": [
            {
                "id": "kpi1",
                "name": "Total Revenue",
                "figma_type": "FRAME",
                "position": {"x": 50, "y": 50},
                "size": {"width": 250, "height": 120},
                "texts": [
                    "Total Revenue",
                    "$125,000",
                    "+12.4%",
                    "vs last month"
                ],
                "children": []
            },
            {
                "id": "chart1",
                "name": "Revenue Overview",
                "figma_type": "FRAME",
                "position": {"x": 50, "y": 220},
                "size": {"width": 700, "height": 350},
                "texts": [
                    "Revenue Overview",
                    "Jan",
                    "Feb",
                    "Mar",
                    "Apr",
                    "May"
                ],
                "children": [
                    {"id": "line1", "name": "Line", "type": "VECTOR"}
                ]
            },
            {
                "id": "table1",
                "name": "Recent Transactions",
                "figma_type": "FRAME",
                "position": {"x": 800, "y": 220},
                "size": {"width": 550, "height": 350},
                "texts": [
                    "Recent Transactions",
                    "ID",
                    "Customer",
                    "Amount",
                    "Date",
                    "1001",
                    "Rahul",
                    "$500",
                    "12/01/2026"
                ],
                "children": []
            }
        ]
    }

    import json

    result = classify_tree(sample_data)

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )
