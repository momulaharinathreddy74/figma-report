import re


# ============================================================
# BASIC HELPERS
# ============================================================

def get_name(node):
    return str(node.get("name") or "").strip()


def get_lower_name(node):
    return get_name(node).lower()


def get_texts(node):
    """
    Get text directly stored in this normalized node.
    """
    texts = node.get("texts", [])

    if not isinstance(texts, list):
        return []

    return [
        str(text).strip()
        for text in texts
        if text and str(text).strip()
    ]


def get_all_text(node):
    """
    Collect text from this node and all descendants.
    """
    texts = []

    texts.extend(get_texts(node))

    for child in node.get("children", []):
        texts.extend(get_all_text(child))

    return texts


def get_combined_text(node):
    return " ".join(get_all_text(node)).strip()


def get_position(node):
    return node.get(
        "position",
        {
            "x": 0,
            "y": 0
        }
    )


def get_size(node):
    return node.get(
        "size",
        {
            "width": 0,
            "height": 0
        }
    )


def get_width(node):
    return get_size(node).get("width", 0) or 0


def get_height(node):
    return get_size(node).get("height", 0) or 0


def word_exists(text, word):
    return bool(
        re.search(
            rf"\b{re.escape(word.lower())}\b",
            text.lower()
        )
    )


def contains_number(text):
    return bool(
        re.search(
            r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?",
            text
        )
    )


def contains_percentage(text):
    return bool(
        re.search(
            r"[-+]?\d+(?:\.\d+)?\s*%",
            text
        )
    )


def contains_currency(text):
    return bool(
        re.search(
            r"[$₹€£]\s*[-+]?\d",
            text
        )
    )


# ============================================================
# LOW LEVEL NODE DETECTION
# ============================================================

def is_low_level_node(node):

    name = get_lower_name(node)

    figma_type = str(
        node.get("figma_type") or ""
    ).upper()

    low_level_names = [
        "vector",
        "ellipse",
        "rectangle",
        "line",
        "icon",
        "avatar",
        "logo",
        "divider",
        "background",
        "mask"
    ]

    for word in low_level_names:
        if word in name:
            return True

    low_level_types = [
        "VECTOR",
        "ELLIPSE",
        "LINE",
        "STAR",
        "POLYGON",
        "BOOLEAN_OPERATION"
    ]

    if figma_type in low_level_types:
        return True

    return False


# ============================================================
# COMPONENT NAME HINTS
# ============================================================

def has_kpi_name(node):

    name = get_lower_name(node)

    keywords = [
        "kpi",
        "metric",
        "big number",
        "big_number",
        "stat",
        "statistic",
        "metric card",
        "summary card",
        "number card"
    ]

    return any(
        keyword in name
        for keyword in keywords
    )


def has_chart_name(node):

    name = get_lower_name(node)

    keywords = [
        "chart",
        "graph",
        "plot",
        "bar chart",
        "line chart",
        "pie chart",
        "donut chart",
        "area chart",
        "scatter"
    ]

    return any(
        keyword in name
        for keyword in keywords
    )


def has_table_name(node):

    name = get_lower_name(node)

    keywords = [
        "table",
        "data table",
        "grid",
        "data grid"
    ]

    return any(
        keyword in name
        for keyword in keywords
    )


# ============================================================
# KPI CLASSIFICATION
# ============================================================

def kpi_score(node, text):

    score = 0
    name = get_lower_name(node)
    text_lower = text.lower()

    # Very strong Figma naming clue
    if has_kpi_name(node):
        score += 7

    # KPI-related words
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
        "visitors",
        "retention"
    ]

    keyword_found = False

    for keyword in kpi_keywords:
        if word_exists(text_lower, keyword):
            keyword_found = True
            break

    if keyword_found:
        score += 3

    # Numeric value is important
    if contains_number(text):
        score += 3

    # Percentage is especially strong
    if contains_percentage(text):
        score += 3

    # Currency is strong KPI evidence
    if contains_currency(text):
        score += 2

    # Cards/widgets are common KPI containers
    if "card" in name or "widget" in name:
        score += 2

    # KPI is normally not huge
    width = get_width(node)
    height = get_height(node)

    if width > 0 and height > 0:

        if width <= 500 and height <= 300:
            score += 2

        if width > 800 or height > 600:
            score -= 2

    return score


# ============================================================
# CHART CLASSIFICATION
# ============================================================

def chart_score(node, text):

    score = 0
    text_lower = text.lower()

    # Very strong name
    if has_chart_name(node):
        score += 8

    chart_keywords = [
        "trend",
        "monthly",
        "weekly",
        "yearly",
        "analytics",
        "statistics",
        "timeline",
        "distribution",
        "comparison",
        "sales by",
        "revenue by",
        "growth by",
        "performance by"
    ]

    keyword_count = 0

    for keyword in chart_keywords:
        if word_exists(text_lower, keyword):
            keyword_count += 1

    if keyword_count >= 1:
        score += 3

    if keyword_count >= 2:
        score += 2

    # Charts usually contain several graphical children
    child_count = len(node.get("children", []))

    if child_count >= 5:
        score += 2

    if child_count >= 10:
        score += 2

    # Charts are normally larger than KPI cards
    width = get_width(node)
    height = get_height(node)

    if width >= 400 and height >= 200:
        score += 2

    if width >= 500 and height >= 250:
        score += 2

    return score


# ============================================================
# TABLE CLASSIFICATION
# ============================================================

def table_score(node, text):

    score = 0
    text_lower = text.lower()

    # Strong name
    if has_table_name(node):
        score += 8

    table_keywords = [
        "customer",
        "customers",
        "transaction",
        "transactions",
        "record",
        "records",
        "employee",
        "employees",
        "product",
        "products",
        "order",
        "orders",
        "invoice",
        "invoices",
        "status",
        "category",
        "description"
    ]

    keyword_count = 0

    for keyword in table_keywords:
        if word_exists(text_lower, keyword):
            keyword_count += 1

    if keyword_count >= 1:
        score += 3

    if keyword_count >= 2:
        score += 2

    # Tables usually have many children
    child_count = len(node.get("children", []))

    if child_count >= 8:
        score += 2

    if child_count >= 15:
        score += 3

    # Tables are usually wide
    width = get_width(node)

    if width >= 500:
        score += 1

    if width >= 700:
        score += 1

    return score


# ============================================================
# COMPONENT CLASSIFICATION
# ============================================================

def classify_component(node):

    if is_low_level_node(node):
        return "OTHER"

    name = get_name(node)
    text = get_combined_text(node)

    # --------------------------------------------------------
    # Strong explicit names should take priority
    # --------------------------------------------------------

    if has_kpi_name(node):
        return "KPI"

    if has_chart_name(node):
        return "CHART"

    if has_table_name(node):
        return "TABLE"

    # --------------------------------------------------------
    # Otherwise use scores
    # --------------------------------------------------------

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

    # Require reasonable evidence
    if best_score < 5:
        return "OTHER"

    return best_type


# ============================================================
# EXTRACT KPI INFORMATION
# ============================================================

def extract_kpi(node):

    texts = get_all_text(node)

    title = None
    value = None
    description_parts = []

    # --------------------------------------------------------
    # Find value
    # --------------------------------------------------------

    for text in texts:

        if contains_percentage(text):
            value = text
            break

        if contains_currency(text):
            value = text
            break

    # If no percentage/currency, look for numeric value
    if value is None:

        for text in texts:

            if contains_number(text):
                value = text
                break

    # --------------------------------------------------------
    # Find title
    # --------------------------------------------------------

    for text in texts:

        if text == value:
            continue

        # Avoid using long sentences as title
        if len(text.split()) <= 8:
            title = text
            break

    # --------------------------------------------------------
    # Remaining text = description
    # --------------------------------------------------------

    for text in texts:

        if text == value:
            continue

        if text == title:
            continue

        description_parts.append(text)

    description = (
        " ".join(description_parts)
        if description_parts
        else None
    )

    return {
        "title": title,
        "value": value,
        "description": description
    }


# ============================================================
# EXTRACT CHART INFORMATION
# ============================================================

def extract_chart(node):

    texts = get_all_text(node)

    title = None

    if texts:
        title = texts[0]

    chart_type = detect_chart_type(node)

    return {
        "title": title,
        "chart_type": chart_type
    }


def detect_chart_type(node):

    name = get_lower_name(node)
    text = get_combined_text(node).lower()

    combined = name + " " + text

    if "bar" in combined:
        return "BAR"

    if "line" in combined:
        return "LINE"

    if "pie" in combined:
        return "PIE"

    if "donut" in combined:
        return "DONUT"

    if "area" in combined:
        return "AREA"

    if "scatter" in combined:
        return "SCATTER"

    return "UNKNOWN"


# ============================================================
# EXTRACT TABLE INFORMATION
# ============================================================

def extract_table(node):

    texts = get_all_text(node)

    title = None

    if texts:
        title = texts[0]

    return {
        "title": title
    }


# ============================================================
# BUILD COMPONENT
# ============================================================

def build_component(node, component_type):

    component = {
        "id": node.get("id"),
        "name": get_name(node),
        "type": component_type,

        "position": get_position(node),
        "size": get_size(node)
    }

    # --------------------------------------------------------
    # KPI
    # --------------------------------------------------------

    if component_type == "KPI":

        kpi = extract_kpi(node)

        component.update({
            "title": kpi["title"],
            "value": kpi["value"],
            "description": kpi["description"]
        })

    # --------------------------------------------------------
    # CHART
    # --------------------------------------------------------

    elif component_type == "CHART":

        chart = extract_chart(node)

        component.update({
            "title": chart["title"],
            "chart_type": chart["chart_type"]
        })

    # --------------------------------------------------------
    # TABLE
    # --------------------------------------------------------

    elif component_type == "TABLE":

        table = extract_table(node)

        component.update({
            "title": table["title"]
        })

    return component


# ============================================================
# COMPONENT TREE TRAVERSAL
# ============================================================

def find_components(node, components=None):

    if components is None:
        components = []

    if is_low_level_node(node):
        return components

    component_type = classify_component(node)

    # --------------------------------------------------------
    # If this is a real dashboard component,
    # treat the entire subtree as ONE component.
    # --------------------------------------------------------

    if component_type in [
        "KPI",
        "CHART",
        "TABLE"
    ]:

        component = build_component(
            node,
            component_type
        )

        components.append(component)

        # IMPORTANT:
        #
        # Don't recursively classify children.
        #
        # Example:
        #
        # Big number
        #   ├── Revenue
        #   ├── $25,000
        #   └── +12%
        #
        # should produce ONE KPI.
        #

        return components

    # --------------------------------------------------------
    # If current node isn't a component,
    # search its children.
    # --------------------------------------------------------

    for child in node.get("children", []):

        find_components(
            child,
            components
        )

    return components


# ============================================================
# FINAL CLASSIFIER
# ============================================================

def classify_tree(normalized_data):

    components = find_components(normalized_data)

    return {
        "dashboard": {
            "id": normalized_data.get("id"),
            "name": normalized_data.get("name"),
            "position": get_position(normalized_data),
            "size": get_size(normalized_data)
        },

        "components": components,

        "component_count": len(components)
    }