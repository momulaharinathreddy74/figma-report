import re
from typing import Any, Dict, List, Tuple


KEYWORDS = {
    "KPI": [
        "revenue", "sales", "profit", "income", "expense",
        "orders", "customers", "users", "growth", "conversion",
        "sessions", "downloads", "transactions", "balance",
        "budget", "target", "total", "average", "avg"
    ],
    "CHART": [
        "chart", "graph", "analytics", "trend", "statistics",
        "performance", "overview"
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
    ],
    "REVIEW": [
        "review", "reviews", "rating", "testimonial", "feedback"
    ]
}

# Layer names that are Figma auto-generated placeholders, never a real
# design-given title ("Group 184", "Frame 47", "Rectangle 12", ...).
GENERIC_NAME_RE = re.compile(
    r"^(group|frame|rectangle|vector|ellipse|component|instance|line|polygon|star)\s*\d*$",
    re.IGNORECASE
)

# Prefixes designers commonly tack onto a layer name that aren't part of
# the human-readable title ("card_total_revenue" -> "Total Revenue").
GENERIC_NAME_PREFIXES = {
    "card", "btn", "button", "ic", "icon", "img", "image",
    "group", "frame", "comp", "component"
}

DAY_ABBREVS = {"sun", "mon", "tue", "wed", "thu", "fri", "sat"}
MONTH_ABBREVS = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}

MIN_SCORE = 5
MIN_MARGIN = 2


def get_name(node):
    return str(node.get("name", "")).strip()


def get_type(node):
    return str(node.get("figma_type") or node.get("type") or "").upper()


def get_texts(node):
    texts = node.get("texts", [])
    if isinstance(texts, str):
        return [texts]
    if not isinstance(texts, list):
        return []
    result = []
    for item in texts:
        if isinstance(item, dict):
            text = (item.get("characters") or item.get("text") or item.get("value") or item.get("content"))
            if text:
                result.append(str(text))
        elif item:
            result.append(str(item))
    if node.get("characters"):
        result.append(str(node["characters"]))
    if node.get("text"):
        result.append(str(node["text"]))
    return result


def get_all_text(node):
    return " ".join(get_texts(node)).lower().strip()


def get_children(node):
    children = node.get("children", [])
    if not isinstance(children, list):
        return []
    return [child for child in children if isinstance(child, dict)]


def get_position(node):
    position = node.get("position", {})
    if not isinstance(position, dict):
        position = {}
    try:
        x = float(position.get("x", node.get("x", 0)) or 0)
        y = float(position.get("y", node.get("y", 0)) or 0)
        return x, y
    except (TypeError, ValueError):
        return 0.0, 0.0


def get_size(node):
    size = node.get("size", {})
    if not isinstance(size, dict):
        size = {}
    try:
        width = float(size.get("width", node.get("width", 0)) or 0)
        height = float(size.get("height", node.get("height", 0)) or 0)
        return width, height
    except (TypeError, ValueError):
        return 0.0, 0.0


# Cache compiled patterns across calls — calculate_scores runs this for
# every node in the tree, once per label.
_KEYWORD_PATTERNS: Dict[str, "re.Pattern"] = {}


def _keyword_pattern(keyword):
    pattern = _KEYWORD_PATTERNS.get(keyword)
    if pattern is None:
        # Alnum-only "word boundary": underscores/hyphens still count as
        # separators (so "total" matches inside "card_total_revenue"),
        # but a keyword must not be glued to another letter/digit (so
        # "menu" does NOT match inside "+Add Menus").
        pattern = re.compile(
            r"(?<![a-z0-9])" + re.escape(keyword.lower()) + r"(?![a-z0-9])"
        )
        _KEYWORD_PATTERNS[keyword] = pattern
    return pattern


def contains_keyword(text, keywords):
    text = text.lower()
    return any(_keyword_pattern(keyword).search(text) for keyword in keywords)


def matched_keywords(text, keywords):
    text = text.lower()
    return [keyword for keyword in keywords if _keyword_pattern(keyword).search(text)]


def is_day_or_month(text):
    token = text.strip().lower()[:3]
    return token in DAY_ABBREVS or token in MONTH_ABBREVS


def is_generic_name(name):
    return bool(GENERIC_NAME_RE.match(name.strip()))


def humanize_name(name):
    """'card_chart_order' -> 'Chart Order', 'pieChart' -> 'Pie Chart'."""
    s = re.sub(r"[_\-]+", " ", name)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
    tokens = [t for t in s.split() if t]
    if tokens and tokens[0].lower() in GENERIC_NAME_PREFIXES:
        tokens = tokens[1:]
    if not tokens:
        return name.strip()
    return " ".join(tokens).title()


def has_image_fill(node, depth=2):
    """True if this node or a shallow descendant has an image fill —
    a strong signal for an avatar/photo, used by the REVIEW rules."""
    fills = (node.get("style") or {}).get("fills") or []
    if isinstance(fills, list):
        for fill in fills:
            if isinstance(fill, dict) and str(fill.get("type", "")).upper() == "IMAGE":
                return True
    if depth <= 0:
        return False
    return any(has_image_fill(child, depth - 1) for child in get_children(node))


def is_numeric(text):
    text = text.strip().replace(",", "")
    return bool(re.fullmatch(r"[₹$€£]?\s*-?\d+(\.\d+)?[KMBkmb%]?", text))


def is_percentage(text):
    return bool(re.search(r"[-+]?\d+(\.\d+)?\s*%", text))


def is_money(text):
    return bool(re.search(r"[₹$€£]\s*\d+|\d+\s*(usd|inr|eur|gbp)", text.lower()))


def is_date(text):
    return bool(re.search(
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
        r"|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b"
        r"|\b(today|yesterday|tomorrow)\b",
        text.lower()
    ))


def is_visual_only(node):
    visual_types = {"RECTANGLE", "ELLIPSE", "LINE", "VECTOR", "POLYGON", "STAR"}
    return get_type(node) in visual_types and len(get_texts(node)) == 0


def is_dashboard_root(node):
    name = get_name(node).lower()
    root_words = ["dashboard", "report", "analytics", "admin panel", "admin dashboard", "main frame", "screen", "canvas"]
    return any(word in name for word in root_words) and len(get_children(node)) > 0


def calculate_scores(node):
    name = get_name(node).lower()
    text = get_all_text(node)
    children = get_children(node)
    texts = get_texts(node)
    width, height = get_size(node)

    scores = {label: 0 for label in KEYWORDS}

    for label, words in KEYWORDS.items():
        if contains_keyword(name, words):
            scores[label] += 6
        if contains_keyword(text, words):
            scores[label] += 2

    numeric_values = sum(is_numeric(t) or is_percentage(t) or is_money(t) for t in texts)
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
    if width > 700 or height > 350:
        scores["KPI"] -= 8
    # A real KPI card is never icon-badge sized — this kills the false
    # positives on tiny notification/nav-icon badges that carry a lone
    # number (e.g. an unread-count bubble) and would otherwise land
    # right at MIN_SCORE.
    if 0 < width < 60 or 0 < height < 60:
        scores["KPI"] -= 10
    if len(texts) > 10:
        scores["KPI"] -= 6
    elif len(texts) > 6:
        scores["KPI"] -= 3

    # Compute chart evidence BEFORE the structural bonuses below, so a
    # plain wide/multi-child container (e.g. a list of 5 rows) can't
    # earn chart points on shape alone — it needs at least one real
    # chart signal (a month/day axis label, a numeric trend, or a
    # cluster of percentages) first.
    month_count = sum(1 for t in texts if t.strip().lower()[:3] in {"jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"})
    day_count = sum(1 for t in texts if t.strip().lower()[:3] in {"sun","mon","tue","wed","thu","fri","sat"})
    pct_count = sum(1 for t in texts if is_percentage(t))

    has_chart_evidence = (
        month_count >= 1
        or day_count >= 1
        or numeric_values >= 2
        or pct_count >= 1
    )

    if has_chart_evidence:
        if len(children) >= 5:
            scores["CHART"] += 3
        if len(children) >= 10:
            scores["CHART"] += 2
        if width > 0 and height > 0 and width / height > 1.2:
            scores["CHART"] += 2

    if month_count >= 6:
        scores["CHART"] += 8
    elif month_count >= 3:
        scores["CHART"] += 5
    elif month_count >= 1:
        scores["CHART"] += 2

    if day_count >= 5:
        scores["CHART"] += 7
    elif day_count >= 3:
        scores["CHART"] += 4

    if numeric_values >= 4 and (width > 300 or height > 200):
        scores["CHART"] += 4

    if pct_count >= 3:
        scores["CHART"] += 6

    table_header_words = {"name","price","status","options","date","amount","quantity","total","description","category","id","type","email","phone","tracking","order","orders","product","products","in stock","action","actions"}
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
    if width >= 500 and height >= 150:
        scores["TABLE"] += 3

    if len(children) >= 3:
        scores["SIDEBAR"] += 2
    if width > 0 and height > 0 and width / height < 0.45:
        scores["SIDEBAR"] += 3

    if len(children) >= 2:
        scores["NAV"] += 2
    if width > 0 and height > 0 and width / height > 2:
        scores["NAV"] += 2

    if len(children) >= 1:
        scores["HEADER"] += 1
    if width > 0 and height > 0 and width / height > 2:
        scores["HEADER"] += 2

    if 1 <= len(children) <= 10:
        scores["FILTER"] += 2
    if any(is_date(t) for t in texts):
        scores["FILTER"] += 2

    if len(children) >= 3:
        scores["LIST"] += 2
    if len(children) >= 8:
        scores["LIST"] += 2

    # --------------------------------------------------------
    # Review/testimonial-specific signals
    # --------------------------------------------------------

    if re.search(
        r"\b\d+\s*(day|days|hour|hours|week|weeks|month|months|year|years)\s*ago\b",
        text
    ):
        scores["REVIEW"] += 7

    rating_like = sum(1 for t in texts if re.fullmatch(r"[0-5](\.\d)?", t.strip()))
    if rating_like >= 1:
        scores["REVIEW"] += 3

    if has_image_fill(node):
        scores["REVIEW"] += 3

    if 2 <= len(texts) <= 8:
        scores["REVIEW"] += 1

    # A single testimonial card is compact (~500x270 in this design).
    # A much wider/taller node is almost always a ROW of several cards
    # whose combined child text trips these same signals — reject it
    # here so find_components descends into the individual cards
    # instead of swallowing them into one merged, data-losing component.
    if width > 700 or height > 400:
        scores["REVIEW"] -= 20

    return scores


def classify_node(node):
    if not isinstance(node, dict):
        return {"label": "OTHER", "confidence": 0.0, "score": 0, "scores": {}}
    if is_visual_only(node):
        return {"label": "OTHER", "confidence": 0.0, "score": 0, "scores": {}, "reason": "visual_only"}

    scores = calculate_scores(node)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_label, best_score = ranked[0]
    second_score = ranked[1][1]

    if best_score < MIN_SCORE:
        return {"label": "OTHER", "confidence": 0.0, "score": best_score, "scores": scores, "reason": "low_score"}
    if best_score - second_score < MIN_MARGIN:
        return {"label": "OTHER", "confidence": 0.0, "score": best_score, "scores": scores, "reason": "ambiguous"}

    max_score = max(scores.values()) or 1
    confidence = round(min(0.99, (best_score / max_score) * 0.7 + ((best_score - second_score) / 10) * 0.3), 3)

    return {
        "label": best_label,
        "confidence": confidence,
        "score": best_score,
        "scores": scores,
        "keywords": matched_keywords(get_name(node) + " " + get_all_text(node), KEYWORDS[best_label])
    }


def extract_kpi_fields(node):
    texts = get_texts(node)
    value = None
    title = None
    description = None
    for text in texts:
        text = text.strip()
        if not text:
            continue
        if value is None and (is_numeric(text) or is_percentage(text) or is_money(text)):
            value = text
        elif title is None:
            title = text
        elif description is None:
            description = text
    return {"title": title, "value": value, "description": description}


def extract_chart_fields(node):
    raw_name = get_name(node)
    combined = (raw_name + " " + get_all_text(node)).lower()
    chart_type = "UNKNOWN"
    if "line" in combined:
        chart_type = "LINE"
    elif "bar" in combined:
        chart_type = "BAR"
    elif "pie" in combined or "donut" in combined:
        chart_type = "PIE"
    elif "area" in combined:
        chart_type = "AREA"

    # A meaningful layer name ("card_chart_order", "pieChart") is a far
    # more reliable title than picking the first bubbled-up text — that
    # text list is in tree-traversal order, not visual/reading order, so
    # an axis label (a day or month name) nested earlier in the subtree
    # can land ahead of the card's actual heading. Only fall back to
    # text-picking when the layer itself has an auto-generated name.
    if raw_name and not is_generic_name(raw_name):
        title = humanize_name(raw_name)
    else:
        title = None
        for text in get_texts(node):
            stripped = text.strip()
            if not stripped:
                continue
            if is_numeric(stripped) or is_percentage(stripped) or is_date(stripped):
                continue
            if is_day_or_month(stripped):
                continue
            title = stripped
            break

    return {"title": title, "chart_type": chart_type}


def extract_table_fields(node):
    texts = get_texts(node)
    title = texts[0] if texts else get_name(node)
    return {"title": title, "columns": [], "rows": []}


def extract_review_fields(node):
    reviewer = None
    rating = None
    time_ago = None
    body = None
    for text in get_texts(node):
        stripped = text.strip()
        if not stripped:
            continue
        if rating is None and re.fullmatch(r"[0-5](\.\d)?", stripped):
            rating = stripped
        elif time_ago is None and re.search(r"\bago\b", stripped.lower()):
            time_ago = stripped
        elif reviewer is None and not re.search(r"\d", stripped) and len(stripped.split()) <= 4:
            reviewer = stripped
        elif body is None and len(stripped) > 20:
            body = stripped
    return {"reviewer": reviewer, "rating": rating, "time_ago": time_ago, "body": body}


def extract_generic_fields(node, label):
    texts = get_texts(node)
    if label in ["SIDEBAR", "NAV", "LIST"]:
        return {"title": get_name(node), "items": texts}
    if label == "HEADER":
        return {"title": texts[0] if texts else get_name(node), "texts": texts}
    if label == "FILTER":
        return {"label": get_name(node), "options": texts}
    return {}


def extract_fields(node, label):
    if label == "KPI":
        return extract_kpi_fields(node)
    if label == "CHART":
        return extract_chart_fields(node)
    if label == "TABLE":
        return extract_table_fields(node)
    if label == "REVIEW":
        return extract_review_fields(node)
    return extract_generic_fields(node, label)


def build_component(node, classification):
    label = classification["label"]
    x, y = get_position(node)
    width, height = get_size(node)
    return {
        "id": node.get("id"),
        "name": get_name(node),
        "type": label,
        "figma_type": get_type(node),
        "position": {"x": x, "y": y},
        "size": {"width": width, "height": height},
        "confidence": classification["confidence"],
        "score": classification["score"],
        "signals": classification.get("keywords", []),
        "fields": extract_fields(node, label)
    }


def find_components(node, components, orphan_texts):
    if not isinstance(node, dict):
        return
    if is_dashboard_root(node):
        for child in get_children(node):
            find_components(child, components, orphan_texts)
        return
    classification = classify_node(node)
    label = classification["label"]
    if label == "OTHER":
        children = get_children(node)
        if children:
            for child in children:
                find_components(child, components, orphan_texts)
        else:
            # A leaf node with no strong enough label to become a
            # component — but if it carries text, it might still be
            # exactly what a nearby flagged component is missing (e.g.
            # a lone "Customer Map" heading that doesn't score as
            # HEADER but is sitting right above an untitled chart).
            # Previously this was silently dropped entirely; keep it
            # as a candidate instead so the orchestrator stage has a
            # chance to use it.
            texts = get_texts(node)
            if texts:
                x, y = get_position(node)
                width, height = get_size(node)
                orphan_texts.append({
                    "id": node.get("id"),
                    "name": get_name(node),
                    "text": " ".join(t.strip() for t in texts if t.strip()),
                    "position": {"x": x, "y": y},
                    "size": {"width": width, "height": height},
                })
        return
    components.append(build_component(node, classification))


def classify_tree(root):
    components = []
    orphan_texts = []
    find_components(root, components, orphan_texts)
    components.sort(key=lambda item: (item["position"]["y"], item["position"]["x"]))
    return {
        "dashboard_name": get_name(root) or "Untitled Dashboard",
        "component_count": len(components),
        "components": components,
        # Lone low-confidence text nodes that didn't score as any
        # label but were never used by anything else either — free
        # material for the orchestrator's gap-resolution step.
        "orphan_texts": orphan_texts,
    }