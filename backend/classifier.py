import re


# ---------------------------------------------------------
# 1. Collect all text inside a node
# ---------------------------------------------------------

def collect_text(node):
    texts = []

    for text in node.get("texts", []):
        if text:
            texts.append(str(text))

    for child in node.get("children", []):
        texts.extend(collect_text(child))

    return texts


def get_all_text(node):
    return " ".join(collect_text(node)).strip()


# ---------------------------------------------------------
# 2. Basic helpers
# ---------------------------------------------------------

def contains_number(text):
    return bool(re.search(r"\d", text))


def contains_percentage(text):
    return bool(re.search(r"\d+(\.\d+)?\s*%", text))


def is_number_or_value(text):
    """
    Detect values such as:
    15%
    120k
    $50k
    1.2M
    500
    """
    text = text.strip()

    pattern = r"""
        ^\s*
        [\$€£₹]?
        \d+(?:\.\d+)?
        [kKmMbB%]?
        \s*
        $
    """

    return bool(re.match(pattern, text, re.VERBOSE))


def word_exists(text, word):
    return bool(
        re.search(
            rf"\b{re.escape(word)}\b",
            text.lower()
        )
    )


# ---------------------------------------------------------
# 3. Ignore visual-only nodes
# ---------------------------------------------------------

def is_visual_node(node):

    name = (node.get("name") or "").lower()
    figma_type = (node.get("figma_type") or "").upper()

    ignored_names = [
        "vector",
        "rectangle",
        "ellipse",
        "line",
        "icon",
        "avatar",
        "divider",
        "background"
    ]

    if any(word in name for word in ignored_names):
        return True

    if figma_type in [
        "VECTOR",
        "ELLIPSE",
        "RECTANGLE",
        "LINE"
    ]:
        return True

    return False


# ---------------------------------------------------------
# 4. KPI detection
# ---------------------------------------------------------

def kpi_score(node):

    name = (node.get("name") or "").lower()

    text = get_all_text(node)
    text_lower = text.lower()

    score = 0

    # Strong Figma/component names
    if "big number" in name:
        score += 10

    if "kpi" in name:
        score += 10

    if "metric" in name:
        score += 8

    if "card" in name:
        score += 5

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
        "visitors"
    ]

    for keyword in kpi_keywords:
        if word_exists(text_lower, keyword):
            score += 3
            break

    # KPI normally contains a number
    if contains_number(text):
        score += 3

    # Percentage is a strong KPI signal
    if contains_percentage(text):
        score += 3

    return score


# ---------------------------------------------------------
# 5. Chart detection
# ---------------------------------------------------------

def chart_score(node):

    name = (node.get("name") or "").lower()
    text = get_all_text(node)
    text_lower = text.lower()

    score = 0

    # Strong component names
    if word_exists(name, "chart"):
        score += 10

    if word_exists(name, "graph"):
        score += 10

    if "plot" in name:
        score += 8

    # Explicit chart-related words
    chart_keywords = [
        "trend",
        "analytics",
        "statistics",
        "monthly",
        "weekly",
        "yearly",
        "timeline",
        "distribution",
        "comparison",
        "growth by",
        "sales by",
        "revenue by"
    ]

    for keyword in chart_keywords:
        if keyword in text_lower:
            score += 3

    # Repeated children often indicate chart structure
    children = node.get("children", [])

    if len(children) >= 5:
        score += 2

    # Names such as Top states often represent
    # ranking/bar-chart components
    if "top states" in name:
        score += 10

    if "top products" in name:
        score += 8

    if "top customers" in name:
        score += 8

    if "top regions" in name:
        score += 8

    return score


# ---------------------------------------------------------
# 6. Table detection
# ---------------------------------------------------------

def table_score(node):

    name = (node.get("name") or "").lower()
    text = get_all_text(node)
    text_lower = text.lower()

    score = 0

    if word_exists(name, "table"):
        score += 10

    if word_exists(name, "grid"):
        score += 8

    table_keywords = [
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

    matches = 0

    for keyword in table_keywords:
        if word_exists(text_lower, keyword):
            matches += 1

    if matches >= 2:
        score += 6

    if len(node.get("children", [])) >= 8:
        score += 2

    return score


# ---------------------------------------------------------
# 7. Classify component
# ---------------------------------------------------------

def classify_component(node):

    if is_visual_node(node):
        return "OTHER"

    scores = {
        "KPI": kpi_score(node),
        "CHART": chart_score(node),
        "TABLE": table_score(node)
    }

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    # If there is not enough evidence
    if best_score < 4:
        return "OTHER"

    return best_type


# ---------------------------------------------------------
# 8. Extract KPI information
# ---------------------------------------------------------

def extract_kpi(node):

    texts = collect_text(node)

    title = None
    value = None
    description = None

    # First identify numeric-looking text
    numeric_texts = []

    for text in texts:

        text = text.strip()

        if not text:
            continue

        if is_number_or_value(text):
            numeric_texts.append(text)

    # -----------------------------------------------------
    # Value
    # -----------------------------------------------------

    if numeric_texts:
        value = numeric_texts[0]

    # -----------------------------------------------------
    # Description
    # -----------------------------------------------------

    description_keywords = [
        "increase",
        "decrease",
        "compared",
        "last week",
        "last month",
        "last year",
        "previous",
        "change",
        "growth"
    ]

    for text in texts:

        text_lower = text.lower()

        if any(
            keyword in text_lower
            for keyword in description_keywords
        ):
            description = text
            break

    # -----------------------------------------------------
    # Title
    # -----------------------------------------------------

    for text in texts:

        text = text.strip()

        if not text:
            continue

        if text == value:
            continue

        if text == description:
            continue

        if not contains_number(text):
            title = text
            break

    return {
        "title": title,
        "value": value,
        "description": description
    }


# ---------------------------------------------------------
# 9. Detect chart type
# ---------------------------------------------------------

def detect_chart_type(node):

    name = (node.get("name") or "").lower()
    text = get_all_text(node).lower()

    # Explicit names
    if "line chart" in name or "line graph" in name:
        return "LINE"

    if "bar chart" in name or "bar graph" in name:
        return "BAR"

    if "pie chart" in name:
        return "PIE"

    if "area chart" in name:
        return "AREA"

    # Top/ranking components are usually bars
    if (
        "top states" in name
        or "top products" in name
        or "top customers" in name
        or "top regions" in name
    ):
        return "BAR"

    # Look for line/bar related words
    if "line" in text:
        return "LINE"

    if "bar" in text:
        return "BAR"

    if "pie" in text:
        return "PIE"

    if "area" in text:
        return "AREA"

    # If we have many repeated children,
    # BAR is a reasonable structural guess
    children = node.get("children", [])

    if len(children) >= 5:
        return "BAR"

    return "UNKNOWN"


# ---------------------------------------------------------
# 10. Extract chart information
# ---------------------------------------------------------

def extract_chart(node):

    texts = collect_text(node)

    title = None

    name = node.get("name")

    # If component name itself is meaningful
    if name and name.lower() not in [
        "chart",
        "graph",
        "line chart",
        "bar chart"
    ]:
        title = name

    # Otherwise find a text title
    if title is None:

        for text in texts:

            text = text.strip()

            if not text:
                continue

            if is_number_or_value(text):
                continue

            if len(text) > 1:
                title = text
                break

    return {
        "title": title,
        "chart_type": detect_chart_type(node)
    }


# ---------------------------------------------------------
# 11. Extract table information
# ---------------------------------------------------------

def extract_table(node):

    texts = collect_text(node)

    title = node.get("name")

    if title and title.lower() in ["table", "data table", "grid"]:
        title = None

    if title is None:

        for text in texts:

            text = text.strip()

            if text:
                title = text
                break

    return {
        "title": title,
        "columns": [],
        "rows": []
    }


# ---------------------------------------------------------
# 12. Build classified component
# ---------------------------------------------------------

def build_component(node):

    component_type = classify_component(node)

    component = {
        "id": node.get("id"),
        "name": node.get("name"),
        "type": component_type,
        "position": node.get("position", {
            "x": 0,
            "y": 0
        }),
        "size": node.get("size", {
            "width": 0,
            "height": 0
        })
    }

    # KPI
    if component_type == "KPI":

        kpi_data = extract_kpi(node)

        component.update({
            "title": kpi_data["title"],
            "value": kpi_data["value"],
            "description": kpi_data["description"]
        })

    # CHART
    elif component_type == "CHART":

        chart_data = extract_chart(node)

        component.update({
            "title": chart_data["title"],
            "chart_type": chart_data["chart_type"]
        })

    # TABLE
    elif component_type == "TABLE":

        table_data = extract_table(node)

        component.update({
            "title": table_data["title"],
            "columns": table_data["columns"],
            "rows": table_data["rows"]
        })

    return component


# ---------------------------------------------------------
# 13. Find actual dashboard components
# ---------------------------------------------------------

def find_components(node, components):

    component_type = classify_component(node)

    # Only add meaningful components
    if component_type in ["KPI", "CHART", "TABLE"]:

        components.append(
            build_component(node)
        )

        # Important:
        # Do not recursively add every child of a detected
        # component as another dashboard component.
        return

    # Otherwise inspect children
    for child in node.get("children", []):

        find_components(
            child,
            components
        )


# ---------------------------------------------------------
# 14. Main classification function
# ---------------------------------------------------------

def classify_tree(node):

    components = []

    find_components(
        node,
        components
    )

    return {
        "dashboard": {
            "id": node.get("id"),
            "name": node.get("name"),
            "position": node.get("position", {
                "x": 0,
                "y": 0
            }),
            "size": node.get("size", {
                "width": 0,
                "height": 0
            })
        },
        "components": components,
        "component_count": len(components)
    }