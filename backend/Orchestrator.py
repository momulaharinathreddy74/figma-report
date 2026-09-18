"""
orchestrator.py

The "Agent / Orchestrator" stage: Plan + Generate JSON.

Cost-conscious split, since this pipeline is meant to run over hundreds
of designs:

  1. LAYOUT (rows, ordering, 12-column grid spans) is pure geometry —
     computed deterministically from position/size data. Zero LLM
     calls, zero API cost, same result every time, for every design.

  2. The LLM is called ONLY to resolve a component the validator
     flagged, and only using that one component + its nearest spatial
     neighbors — not the whole page. Most designs have zero flagged
     components, meaning zero LLM calls. A design with one gap costs
     one small, targeted call, not one large whole-page call.

Input:  classified_design (from classifier.classify_tree)
        validation        (from validator.validate_classified_design)
Output: dashboard_config — components grouped into sections/rows, each
        with a grid_column_span, plus any validator-flagged fields the
        LLM could confidently resolve from nearby context.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

# Small/cheap model — each call here resolves exactly one flagged
# field using a handful of neighbor components, not a whole-page plan.
RESOLVER_MODEL = "claude-haiku-4-5-20251001"

_client = None


def _get_client():
    """Lazy import + lazy client creation — the anthropic package and
    an API key are only required if you actually opt into
    use_llm_fallback=True. The free, rule-based path never touches
    this function at all."""
    global _client
    if _client is None:
        from anthropic import Anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is missing")
        _client = Anthropic(api_key=api_key)
    return _client


# ====================================================================
# 1. Deterministic layout engine — no LLM, runs on every design
# ====================================================================

def group_into_rows(components: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Cluster components into rows by vertical (y) overlap, then sort
    each row left-to-right by x. Pure geometry, no model call."""
    ordered = sorted(components, key=lambda c: c["position"]["y"])
    rows: List[Dict[str, Any]] = []

    for c in ordered:
        y0 = c["position"]["y"]
        y1 = y0 + c["size"]["height"]
        placed = False

        for row in rows:
            ry0, ry1 = row["y_range"]
            overlap = min(y1, ry1) - max(y0, ry0)
            shortest = min(y1 - y0, ry1 - ry0)
            if shortest > 0 and overlap > 0 and (overlap / shortest) >= 0.3:
                row["components"].append(c)
                row["y_range"] = (min(ry0, y0), max(ry1, y1))
                placed = True
                break

        if not placed:
            rows.append({"y_range": (y0, y1), "components": [c]})

    rows.sort(key=lambda r: r["y_range"][0])
    for row in rows:
        row["components"].sort(key=lambda c: c["position"]["x"])

    return [row["components"] for row in rows]


def compute_grid_spans(row: List[Dict[str, Any]]) -> List[int]:
    """Proportional 12-column spans based on relative width, rounded
    and corrected so they always sum to exactly 12."""
    if not row:
        return []

    total_width = sum(c["size"]["width"] for c in row)
    if total_width <= 0:
        base = max(1, 12 // len(row))
        spans = [base] * len(row)
    else:
        spans = [max(1, round(c["size"]["width"] / total_width * 12)) for c in row]

    diff = 12 - sum(spans)
    if diff != 0:
        idx = spans.index(max(spans))
        spans[idx] = max(1, spans[idx] + diff)

    return spans


_TYPE_LABELS = {
    "KPI": "KPI Summary",
    "CHART": "Charts",
    "REVIEW": "Customer Reviews",
    "FILTER": "Filters",
    "NAV": "Navigation",
    "SIDEBAR": "Sidebar",
    "TABLE": "Table",
    "LIST": "List",
    "HEADER": "Header",
}


def label_row(row: List[Dict[str, Any]]) -> str:
    if len(row) == 1:
        fields = row[0].get("fields") or {}
        title = fields.get("title") or fields.get("label") or row[0].get("name")
        return title or row[0].get("type", "Section")

    types = {c.get("type") for c in row}
    if len(types) == 1:
        return _TYPE_LABELS.get(next(iter(types)), next(iter(types)).title())

    return "Section"


def build_sections(components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not components:
        return []

    page_height = max(c["position"]["y"] + c["size"]["height"] for c in components)
    page_width = max(c["position"]["x"] + c["size"]["width"] for c in components)

    # A component spanning most of the page's height (a sidebar, a full-
    # height nav rail) isn't a "row" — it's structural framing. Left in
    # the row-clustering pass, its huge y-range would overlap with every
    # other row and swallow the whole page into one giant row. Pull these
    # out first and give each its own section, sized by width against the
    # full page rather than against a row it doesn't actually share.
    rail_threshold = page_height * 0.6
    rails = [c for c in components if c["size"]["height"] >= rail_threshold]
    content = [c for c in components if c["size"]["height"] < rail_threshold]

    sections = []

    for rail in sorted(rails, key=lambda c: c["position"]["x"]):
        span = max(1, min(12, round(rail["size"]["width"] / page_width * 12)))
        sections.append({
            "section_name": label_row([rail]),
            "components": [{
                "id": rail.get("id"),
                "type": rail.get("type"),
                "grid_column_span": span,
                "fields": dict(rail.get("fields") or {}),
            }],
        })

    for row in group_into_rows(content):
        spans = compute_grid_spans(row)
        sections.append({
            "section_name": label_row(row),
            "components": [
                {
                    "id": c.get("id"),
                    "type": c.get("type"),
                    "grid_column_span": span,
                    "fields": dict(c.get("fields") or {}),
                }
                for c, span in zip(row, spans)
            ],
        })

    return sections


# ====================================================================
# 2. Targeted LLM resolution — only for validator-flagged components
# ====================================================================

def find_neighbors(
    component: Dict[str, Any],
    all_components: List[Dict[str, Any]],
    max_neighbors: int = 4,
) -> List[Dict[str, Any]]:
    """Nearest other components by center-to-center distance — cheap
    spatial proxy for 'what's near this thing on the page'."""
    cx = component["position"]["x"] + component["size"]["width"] / 2
    cy = component["position"]["y"] + component["size"]["height"] / 2

    others = [c for c in all_components if c.get("id") != component.get("id")]

    def _dist(c):
        ox = c["position"]["x"] + c["size"]["width"] / 2
        oy = c["position"]["y"] + c["size"]["height"] / 2
        return ((ox - cx) ** 2 + (oy - cy) ** 2) ** 0.5

    others.sort(key=_dist)
    return others[:max_neighbors]


# --------------------------------------------------------------------
# Rule-based resolver — free, deterministic, no LLM. Tries this first
# (and, by default, only this) for every flagged component.
# --------------------------------------------------------------------

_MAX_ORPHAN_DISTANCE = 200   # px — how close a stray text must be to count
_MAX_TITLE_LEN = 60          # a real heading is short; a paragraph isn't


def _nearest_orphan_title(
    component: Dict[str, Any],
    orphan_texts: List[Dict[str, Any]],
) -> Optional[str]:
    if not orphan_texts:
        return None

    cx = component["position"]["x"] + component["size"]["width"] / 2
    cy = component["position"]["y"] + component["size"]["height"] / 2

    best_text = None
    best_dist = None
    for orphan in orphan_texts:
        text = (orphan.get("text") or "").strip()
        if not text or len(text) > _MAX_TITLE_LEN:
            continue
        ox = orphan["position"]["x"] + orphan["size"]["width"] / 2
        oy = orphan["position"]["y"] + orphan["size"]["height"] / 2
        dist = ((ox - cx) ** 2 + (oy - cy) ** 2) ** 0.5
        if dist <= _MAX_ORPHAN_DISTANCE and (best_dist is None or dist < best_dist):
            best_dist = dist
            best_text = text

    return best_text


def resolve_flagged_rule_based(
    flagged_component: Dict[str, Any],
    neighbors: List[Dict[str, Any]],
    orphan_texts: List[Dict[str, Any]],
    problems: List[str],
) -> Dict[str, Any]:
    """Deterministic, zero-cost first attempt at fixing a flagged
    component. Only handles the 'missing title' shape of problem for
    now, and only trusts orphan_texts (genuine stray heading-like text
    the classifier kept instead of dropping) as a source — NOT another
    component's own title. Borrowing a neighbor's title is tempting but
    unsafe: it produces a confident, plausible-looking, WRONG answer
    (verified during testing — it grabbed a nearby chart's title and
    mislabeled an unrelated chart with it). An honest 'unresolved' is
    always better than a fabricated one, so anything that isn't a
    clean orphan-text match falls through unresolved instead of
    guessing from unrelated components."""
    needs_title = any("title" in p for p in problems)
    if not needs_title:
        return {"resolved": False, "reason": "not a missing-title problem — rule-based resolver only handles that case"}

    title = _nearest_orphan_title(flagged_component, orphan_texts)
    if title:
        return {"resolved": True, "fields": {"title": title}, "source": "a nearby stray heading text"}

    return {
        "resolved": False,
        "reason": "no nearby orphan text found within range — refusing to guess from an unrelated component's title",
    }


def _slim(c: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": c.get("id"),
        "type": c.get("type"),
        "position": c.get("position"),
        "size": c.get("size"),
        "fields": c.get("fields"),
    }


def build_resolution_prompt(
    flagged_component: Dict[str, Any],
    neighbors: List[Dict[str, Any]],
    problems: List[str],
) -> str:
    return f'''One component from a dashboard layout has missing/incomplete fields.
Try to fix it using ONLY the nearby components listed below as context.

FLAGGED COMPONENT:
{json.dumps(_slim(flagged_component), indent=2, ensure_ascii=False)}

PROBLEMS:
{json.dumps(problems, indent=2, ensure_ascii=False)}

NEARBY COMPONENTS (by physical proximity on the page):
{json.dumps([_slim(n) for n in neighbors], indent=2, ensure_ascii=False)}

If you can confidently fix the flagged fields using this context (e.g. a
CHART with a null title sitting right next to a text component whose content
reads like a section heading), respond with the corrected fields. If you
cannot confidently resolve it, say so rather than guessing.

Respond with ONLY valid JSON, no prose, no markdown fences, in exactly this
shape:

{{
  "resolved": true or false,
  "fields": {{ ...only the fields you are confidently correcting... }},
  "reason": "explanation if resolved is false, otherwise omit or leave empty"
}}'''


def _extract_json(raw_text: str) -> Dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Resolver did not return valid JSON: {e}\n---\n{raw_text}")


def call_resolver_llm(prompt: str) -> str:
    client = _get_client()
    response = client.messages.create(
        model=RESOLVER_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )


def resolve_flagged_component(
    flagged_component: Dict[str, Any],
    neighbors: List[Dict[str, Any]],
    problems: List[str],
) -> Dict[str, Any]:
    """One small, targeted LLM call for exactly one flagged component.
    Returns {"resolved": bool, "fields": {...}, "reason": "..."}."""
    prompt = build_resolution_prompt(flagged_component, neighbors, problems)
    raw = call_resolver_llm(prompt)
    return _extract_json(raw)


# ====================================================================
# Public entry point
# ====================================================================

def generate_dashboard_config(
    classified_design: Dict[str, Any],
    validation: Optional[Dict[str, Any]] = None,
    use_llm_fallback: bool = False,
) -> Dict[str, Any]:
    """
    classified_design + validation -> dashboard_config.

    Layout/grouping is always deterministic (no LLM).

    Flagged components are resolved in two tiers:
      1. Rule-based (free, deterministic) — uses orphan_texts (stray
         low-confidence text the classifier kept instead of dropping)
         and neighboring components' own titles.
      2. LLM (costs tokens) — only attempted if use_llm_fallback=True
         AND the rule-based pass couldn't resolve it. Off by default,
         so running this against a batch of designs costs nothing
         unless you deliberately opt in.
    """
    components = classified_design.get("components", [])
    orphan_texts = classified_design.get("orphan_texts", [])
    sections = build_sections(components)

    unresolved = []
    issues = (validation or {}).get("issues", []) if validation else []

    if issues:
        by_id = {c.get("id"): c for c in components}
        patch_targets = {
            comp["id"]: comp
            for section in sections
            for comp in section["components"]
        }

        for issue in issues:
            comp = by_id.get(issue.get("id"))
            if comp is None:
                continue

            neighbors = find_neighbors(comp, components)
            problems = issue.get("problems", [])

            result = resolve_flagged_rule_based(comp, neighbors, orphan_texts, problems)

            if not result.get("resolved") and use_llm_fallback:
                try:
                    result = resolve_flagged_component(comp, neighbors, problems)
                except Exception as e:
                    result = {"resolved": False, "reason": f"resolver error: {e}"}

            if result.get("resolved") and result.get("fields"):
                patch_targets[comp["id"]]["fields"].update(result["fields"])
            else:
                unresolved.append({
                    "id": comp.get("id"),
                    "reason": result.get("reason") or "could not resolve with available context",
                })

    return {
        "dashboard_name": classified_design.get("dashboard_name", "Untitled Dashboard"),
        "sections": sections,
        "unresolved": unresolved,
    }