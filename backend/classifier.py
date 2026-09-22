import re
from typing import Any, Dict, List, Optional, Tuple


# --------------------------------------------------------------------
# Company direction (this pass): focus only on KPI, CHART, and TABLE.
# Everything else — sidebars, nav, headers, filters, lists, reviews,
# anything — is OTHER. This is not "OTHER because we couldn't figure
# it out" — it's OTHER by design; those categories no longer exist as
# classifier outputs at all.
# --------------------------------------------------------------------

KEYWORDS = {
    "KPI": [
        "revenue", "sales", "profit", "income", "expense",
        "orders", "customers", "users", "growth", "conversion",
        "sessions", "session", "duration", "downloads", "transactions",
        "balance", "budget", "target", "total", "average", "avg"
    ],
    "CHART": [
        # generic chart-ish words
        "chart", "graph", "analytics", "trend", "statistics",
        "performance", "overview",
        # explicit chart-type words — a layer literally named "Donut" or
        # "Funnel" with no other keyword should still register as CHART
        "bar", "column", "line", "area", "pie", "donut", "scatter",
        "histogram", "funnel", "radar", "gauge", "waterfall", "combo",
        "heatmap", "treemap"
    ],
    "TABLE": [
        "table", "records", "transactions", "transaction history",
        "recent orders", "recent transactions", "customer list",
        "user list"
    ],
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
        # "bar" does NOT match inside "Sidebar", "menu" does NOT match
        # inside "+Add Menus").
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


def _camel_split(s):
    """Insert a space at camelCase boundaries so keyword matching sees
    'pie Chart' instead of 'piechart' — without this, a layer literally
    named 'pieChart' or 'donutChart' never matches 'pie'/'donut'/even
    'chart' at all, since the alnum-boundary keyword matcher requires a
    non-alnum character on both sides of a match."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)


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


def is_numeric(text):
    text = text.strip().replace(",", "")
    return bool(re.fullmatch(r"[₹$€£]?\s*-?\d+(\.\d+)?[KMBkmb%]?", text))


def is_percentage(text):
    return bool(re.search(r"[-+]?\d+(\.\d+)?\s*%", text))


def is_money(text):
    return bool(re.search(r"[₹$€£]\s*\d+|\d+\s*(usd|inr|eur|gbp)", text.lower()))


def is_ratio(text):
    """'27/80', '3 of 10' — a single 'X out of Y' reading. Counted
    separately from is_numeric so a genuine ratio-style KPI value
    isn't mistaken for two independent readings."""
    t = text.strip()
    return bool(re.fullmatch(r"\d+\s*/\s*\d+", t)) or bool(re.fullmatch(r"\d+\s+of\s+\d+", t, re.IGNORECASE))


def is_duration(text):
    """'2m 34s', '1h 20m', '12:34', '1:02:03' — time-duration KPI
    values. Distinct from is_date: these are elapsed-time formats, not
    calendar dates, and none of is_numeric/is_percentage/is_money
    recognize them — a KPI card whose value is a duration ('Av. Session
    Length: 2m 34s') would otherwise score as having no value at all."""
    t = text.strip().lower()
    if re.fullmatch(r"\d+\s*h\s*\d+\s*m", t) or re.fullmatch(r"\d+\s*m\s*\d+\s*s", t):
        return True
    if re.fullmatch(r"\d+\s*(h|hr|hrs|m|min|mins|s|sec|secs)", t):
        return True
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", t):
        return True
    return False


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
    name = _camel_split(get_name(node)).lower()
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

    # An explicit chart-TYPE word in the name (not just generic "chart"/
    # "graph"/"overview") is a stronger, more specific signal than a
    # KPI keyword riding along in the same name (e.g. "revenue_line_
    # chart" names a KPI-sounding metric AND a chart type at once —
    # the explicit type word should decide it).
    _STRONG_CHART_TYPE_WORDS = (
        "bar", "column", "line", "area", "pie", "donut", "scatter",
        "histogram", "funnel", "radar", "gauge", "waterfall", "combo",
        "heatmap", "treemap"
    )
    strong_type_matched = any(_keyword_pattern(w).search(name) for w in _STRONG_CHART_TYPE_WORDS)
    if strong_type_matched:
        scores["CHART"] += 4

    # --------------------------------------------------------
    # Structural guards — geometry, not naming conventions.
    #
    # These exist because chart-type words ("bar", "line", "pie", ...)
    # are common English words that show up in UI-control and icon
    # names for reasons that have nothing to do with data
    # visualization ("progress bar", an icon named "*-line" per a
    # library's own style-variant convention, etc.). Naming
    # conventions are specific to whichever design system produced a
    # given file and will never be fully enumerable — a phrase list
    # tuned to one design's vocabulary just breaks on the next one.
    # Shape does not have that problem: an icon is small in EVERY
    # design, a progress/loading indicator is a thin strip in EVERY
    # design system, and a sidebar or navbar rail has an extreme
    # aspect ratio in EVERY dashboard, regardless of what anyone
    # named it. These guards generalize; a naming list does not.
    # --------------------------------------------------------

    # Icon-sized elements can never be a chart, whatever they're named.
    if 0 < width < 40 and 0 < height < 40:
        scores["CHART"] -= 25

    # A thin strip (a progress bar, a loading indicator, a divider, a
    # slim rail) is not a chart shape, whatever keyword it happens to
    # contain in its name.
    if width > 0 and height > 0:
        if height / width > 3:
            scores["CHART"] -= 10
        if width / height > 8:
            scores["CHART"] -= 6

    # A generic chart-ish word ("overview", "analytics", "performance",
    # "trend", "chart", "graph") is common English that can bubble up
    # from anywhere in a subtree's text for reasons unrelated to a
    # chart being present. On a SMALL element that's a plausible
    # mini-chart/sparkline annotation. On a LARGE section, it's not
    # nearly enough on its own — a real, reportable chart either names
    # its specific type (a strong-type-word match, handled above) or
    # shows real axis evidence (checked below); a big section winning
    # CHART from one vague word floating in its bubbled text, with
    # neither, is exactly the false-positive pattern worth blocking.
    # Area, not any specific design's naming convention, is what
    # distinguishes "small annotation" from "substantial section" in
    # every design.
    area = width * height
    if not strong_type_matched and area > 20000:
        scores["CHART"] -= 8

    # --------------------------------------------------------
    # KPI-specific signals
    # --------------------------------------------------------

    month_count = sum(1 for t in texts if t.strip().lower()[:3] in MONTH_ABBREVS)
    day_count = sum(1 for t in texts if t.strip().lower()[:3] in DAY_ABBREVS)

    numeric_values = sum(
        is_numeric(t) or is_percentage(t) or is_money(t) or is_duration(t)
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
    if any(is_duration(t) for t in texts):
        scores["KPI"] += 2
    if 0 < len(texts) <= 6:
        scores["KPI"] += 1
    if width > 700 or height > 350:
        scores["KPI"] -= 8
    # A real KPI card is never icon-badge sized — kills false positives
    # on tiny notification/nav-icon badges carrying a lone number.
    if 0 < width < 60 or 0 < height < 60:
        scores["KPI"] -= 10
    if len(texts) > 10:
        scores["KPI"] -= 6
    elif len(texts) > 6:
        scores["KPI"] -= 3
    # Several month/day labels is a chart-axis signature, not a KPI
    # card — without this, a name like "revenue_line_chart" (KPI
    # keyword "revenue" + a real trend axis) can outscore CHART on
    # keyword strength alone.
    if month_count >= 2 or day_count >= 2:
        scores["KPI"] -= 6
    # A relative-time phrase ("2 days ago") is a testimonial/review
    # signature, not a KPI card. Without SIDEBAR/NAV/HEADER/FILTER/
    # LIST/REVIEW competing for the win anymore, a card with just a
    # rating-like number and a short caption can cross MIN_SCORE on
    # KPI's numeric-value bonus alone; explicitly suppress that.
    if re.search(r"\b\d+\s*(day|days|hour|hours|week|weeks|month|months|year|years)\s*ago\b", text):
        scores["KPI"] -= 10
    # A node with 2+ SEPARATE non-percentage primary readings (plain
    # numbers, money, durations, or "X/Y" ratios) AND multiple children
    # is very likely a WRAPPER around several distinct KPI cards, not
    # one card with one value — e.g. a parent group spanning "Active
    # Users: 27/80" and "Questions Answered: 3,298" as two separate
    # child cards. A single genuine KPI card has exactly one primary
    # reading (percentages are typically a secondary delta, already
    # excluded here). Without this, the wrapper wins the label itself
    # and swallows every card beneath it into one component with
    # mismatched, merged fields — the same "container swallows its
    # children" failure mode fixed earlier for stacked review cards,
    # just triggered by value-count here instead of raw size (sizes
    # vary too much between design systems to use as the only signal).
    primary_non_pct_values = sum(
        (is_numeric(t) or is_money(t) or is_duration(t) or is_ratio(t)) and not is_percentage(t)
        for t in texts
    )
    if primary_non_pct_values >= 2 and len(children) >= 2:
        scores["KPI"] -= 12
    # Three or more percentages is a ranked breakdown/leaderboard (each
    # named item has its own %), not a single KPI reading — a real KPI
    # card has one primary value plus, at most, one secondary delta
    # percentage.
    pct_count = sum(1 for t in texts if is_percentage(t))
    if pct_count >= 3:
        scores["KPI"] -= 8

    # --------------------------------------------------------
    # Chart-specific signals
    # --------------------------------------------------------

    # Only real axis evidence — month or day labels — unlocks the
    # structural bonuses below. Plain numbers (ranks, point totals,
    # percentages) are too ubiquitous to trust as chart evidence on
    # their own: a leaderboard has point counts, a table has row
    # counts, a KPI card has its value — none of that is a chart axis.
    # A genuine chart without month/day labels still gets credit
    # through its explicit type-word match (bar/line/pie/...) above;
    # this gate exists only to stop plain numeric content from
    # promoting an otherwise-unlabeled section to CHART via shape
    # alone.
    has_chart_evidence = month_count >= 1 or day_count >= 1

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

    # --------------------------------------------------------
    # Table-specific signals
    # --------------------------------------------------------

    table_header_words = {"name","price","status","options","date","amount","quantity","total","description","category","id","type","email","phone","tracking","order","orders","product","products","in stock","action","actions"}
    header_hits = sum(1 for t in texts if t.lower().strip() in table_header_words)
    if header_hits >= 4:
        scores["TABLE"] += 10
    elif header_hits >= 2:
        scores["TABLE"] += 5
    if len(texts) >= 6:
        scores["TABLE"] += 2
    if sum(is_date(t) for t in texts) >= 2:
        scores["TABLE"] += 2
    # Child count and size are pure geometry — they can't tell a real
    # data table (rows sharing actual column headers like Name/Date/
    # Amount) apart from a ranked list, a leaderboard, or any other
    # large multi-item container. Without at least one recognized
    # header word actually present, "many children + large size" is
    # true of dozens of non-table UI patterns — it was letting exactly
    # that class of content (leaderboards, ranked breakdowns) win
    # TABLE with zero real column evidence, even though this
    # classifier has no ability to extract actual rows/columns for
    # them either way. Require genuine header-word evidence first.
    if header_hits >= 1:
        if len(children) >= 8:
            scores["TABLE"] += 3
        if width >= 500 and height >= 150:
            scores["TABLE"] += 3

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
        "keywords": matched_keywords(_camel_split(get_name(node)) + " " + get_all_text(node), KEYWORDS[best_label])
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
        if value is None and (is_numeric(text) or is_percentage(text) or is_money(text) or is_duration(text) or is_ratio(text)):
            value = text
        elif title is None:
            title = text
        elif description is None:
            description = text
    return {"title": title, "value": value, "description": description}


# ============================================================
# Chart subtype taxonomy
#
#   CHART
#   ├── BAR        -> VERTICAL | HORIZONTAL | GROUPED | STACKED
#   ├── LINE       -> SINGLE | MULTI
#   ├── AREA       -> STACKED
#   ├── PIE
#   ├── DONUT
#   ├── SCATTER
#   ├── HISTOGRAM
#   ├── FUNNEL
#   ├── RADAR
#   ├── GAUGE
#   ├── WATERFALL
#   ├── COMBO
#   ├── HEATMAP
#   └── TREEMAP
#
# Rule-based and explainable, same philosophy as the rest of this
# classifier: matched from the layer's own name/text first (most
# reliable), with a couple of light structural heuristics where text
# alone can't disambiguate (e.g. single- vs multi-series line charts).
# ============================================================

_NO_SUBTYPE_CHART_KEYWORDS = [
    (("donut",), "DONUT"),
    (("pie",), "PIE"),
    (("scatter", "scatterplot"), "SCATTER"),
    (("histogram",), "HISTOGRAM"),
    (("funnel",), "FUNNEL"),
    (("radar", "spider chart", "spider graph"), "RADAR"),
    (("gauge", "speedometer"), "GAUGE"),
    (("waterfall",), "WATERFALL"),
    (("heatmap", "heat map"), "HEATMAP"),
    (("treemap", "tree map"), "TREEMAP"),
    (("combo", "combination chart"), "COMBO"),
]


def _looks_multi_series(node):
    """Crude but explainable: repeated 4-digit years (e.g. a legend of
    '2020' / '2021') or several short legend-like tokens suggest more
    than one series is being compared on the same chart."""
    texts = get_texts(node)
    year_tokens = {t.strip() for t in texts if re.fullmatch(r"(19|20)\d{2}", t.strip())}
    return len(year_tokens) >= 2


def classify_chart_type(node) -> Dict[str, Optional[str]]:
    """Returns {'category', 'subtype', 'chart_type'} — chart_type is
    'CATEGORY/SUBTYPE' when there's a subtype, else just 'CATEGORY',
    else 'UNKNOWN' if nothing specific enough could be determined."""
    combined = (_camel_split(get_name(node)) + " " + get_all_text(node)).lower()

    for keywords, category in _NO_SUBTYPE_CHART_KEYWORDS:
        if any(_keyword_pattern(kw).search(combined) for kw in keywords):
            return {"category": category, "subtype": None, "chart_type": category}

    if _keyword_pattern("area").search(combined):
        return {"category": "AREA", "subtype": "STACKED", "chart_type": "AREA/STACKED"}

    if _keyword_pattern("line").search(combined):
        subtype = "MULTI" if _looks_multi_series(node) else "SINGLE"
        return {"category": "LINE", "subtype": subtype, "chart_type": f"LINE/{subtype}"}

    if _keyword_pattern("bar").search(combined) or _keyword_pattern("column").search(combined):
        if _keyword_pattern("stacked").search(combined):
            subtype = "STACKED"
        elif any(_keyword_pattern(kw).search(combined) for kw in ("grouped", "clustered")):
            subtype = "GROUPED"
        elif _keyword_pattern("horizontal").search(combined):
            subtype = "HORIZONTAL"
        else:
            subtype = "VERTICAL"
        return {"category": "BAR", "subtype": subtype, "chart_type": f"BAR/{subtype}"}

    # A generic chart keyword ("chart", "graph", "analytics", "overview")
    # matched at the top level but nothing names a specific chart type —
    # can't responsibly guess a subtype from text alone.
    return {"category": None, "subtype": None, "chart_type": "UNKNOWN"}


def extract_chart_fields(node):
    raw_name = get_name(node)
    chart_info = classify_chart_type(node)

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

    return {
        "title": title,
        "chart_type": chart_info["chart_type"],
        "chart_category": chart_info["category"],
        "chart_subtype": chart_info["subtype"],
    }


def extract_table_fields(node):
    texts = get_texts(node)
    title = texts[0] if texts else get_name(node)
    return {"title": title, "columns": [], "rows": []}


def extract_fields(node, label):
    if label == "KPI":
        return extract_kpi_fields(node)
    if label == "CHART":
        return extract_chart_fields(node)
    if label == "TABLE":
        return extract_table_fields(node)
    return {}


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
            # A leaf node that isn't a KPI, CHART, or TABLE — by design,
            # per the current classification scope. Still worth keeping
            # its text as a candidate for gap-resolution elsewhere (e.g.
            # a stray "Customer Map" heading next to an untitled chart),
            # rather than discarding it outright.
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
        "orphan_texts": orphan_texts,
    }