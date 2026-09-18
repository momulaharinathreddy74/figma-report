"""
validator.py

Pure schema/contract check over a classifier's `classified_design` output.
No LLM calls, no network, no dependency on classifier.py or normalizer.py —
just reads the JSON shape you already have and reports which components
are missing the fields their type requires.

This is intentionally thin: it reports issues, it does not fix them,
retry, or loop. Wire the retry/correction logic in later, once the
Agent/Orchestrator exists and you know what it actually gets wrong.
"""

from typing import Any, Dict, List


# --------------------------------------------------------------------
# Per-type field requirements.
# Each rule is (field_path, human_reason). field_path may use "a|b" to
# mean "at least one of a, b must be present/non-empty".
# --------------------------------------------------------------------

def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def _get(fields: Dict[str, Any], path: str):
    return fields.get(path)


def _check_kpi(fields: Dict[str, Any]) -> List[str]:
    issues = []
    if _is_empty(_get(fields, "value")):
        issues.append("missing 'value' — a KPI card with no number to display")
    if _is_empty(_get(fields, "title")):
        issues.append("missing 'title'")
    return issues


def _check_chart(fields: Dict[str, Any]) -> List[str]:
    issues = []
    title = _get(fields, "title")
    chart_type = _get(fields, "chart_type")
    if _is_empty(title) and (chart_type in (None, "UNKNOWN")):
        issues.append("missing both 'title' and a known 'chart_type' — nothing to label this chart with")
    return issues


def _check_table(fields: Dict[str, Any]) -> List[str]:
    issues = []
    if _is_empty(_get(fields, "title")):
        issues.append("missing 'title'")
    return issues


def _check_review(fields: Dict[str, Any]) -> List[str]:
    issues = []
    if _is_empty(_get(fields, "reviewer")):
        issues.append("missing 'reviewer' — can't attribute this review to anyone")
    if _is_empty(_get(fields, "body")) and _is_empty(_get(fields, "rating")):
        issues.append("missing both 'body' and 'rating' — no actual review content")
    return issues


def _check_header(fields: Dict[str, Any]) -> List[str]:
    issues = []
    if _is_empty(_get(fields, "title")):
        issues.append("missing 'title'")
    return issues


def _check_filter(fields: Dict[str, Any]) -> List[str]:
    issues = []
    if _is_empty(_get(fields, "label")):
        issues.append("missing 'label'")
    return issues


def _check_list_like(fields: Dict[str, Any]) -> List[str]:
    # Shared by SIDEBAR, NAV, LIST — all use {"title": ..., "items": [...]}
    issues = []
    if _is_empty(_get(fields, "items")):
        issues.append("missing or empty 'items' — nothing to render as a list/menu")
    return issues


_CHECKS = {
    "KPI": _check_kpi,
    "CHART": _check_chart,
    "TABLE": _check_table,
    "REVIEW": _check_review,
    "HEADER": _check_header,
    "FILTER": _check_filter,
    "SIDEBAR": _check_list_like,
    "NAV": _check_list_like,
    "LIST": _check_list_like,
}


def validate_component(component: Dict[str, Any]) -> List[str]:
    """Return a list of human-readable issue strings for one component
    (empty list means the component is clean)."""
    comp_type = component.get("type")
    fields = component.get("fields") or {}

    checker = _CHECKS.get(comp_type)
    if checker is None:
        # Unknown/unregistered type — flag it rather than silently pass.
        return [f"no validation rule registered for type '{comp_type}'"]

    return checker(fields)


def validate_classified_design(classified_design: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate every component in a classifier's `classified_design` output.

    Returns:
        {
            "valid": bool,                 # True iff zero components have issues
            "component_count": int,
            "flagged_count": int,
            "issues": [
                {
                    "id": "...",
                    "name": "...",
                    "type": "...",
                    "problems": ["missing 'value' — ...", ...]
                },
                ...
            ]
        }
    """
    components = classified_design.get("components", [])

    issues = []
    for component in components:
        problems = validate_component(component)
        if problems:
            issues.append({
                "id": component.get("id"),
                "name": component.get("name"),
                "type": component.get("type"),
                "problems": problems,
            })

    return {
        "valid": len(issues) == 0,
        "component_count": len(components),
        "flagged_count": len(issues),
        "issues": issues,
    }


if __name__ == "__main__":
    # Quick manual check — paste any classified_design dict here.
    import json
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            payload = json.load(f)
    else:
        print("Usage: python validator.py <path_to_classified_design.json>")
        sys.exit(1)

    design = payload.get("classified_design", payload)
    report = validate_classified_design(design)
    print(json.dumps(report, indent=2, ensure_ascii=False))