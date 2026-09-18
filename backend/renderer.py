"""
renderer.py

Turns a classifier's `classified_design` output into a self-contained HTML
page, absolutely-positioned using each component's real Figma x/y/width/
height — a quick visual sanity check that doesn't require the full React
renderer from the architecture diagram. Optionally overlays validator
output (validate_classified_design) so flagged components are visibly
marked instead of you cross-checking a JSON list against a screenshot.

No LLM, no network calls — pure string templating from data you already
have.
"""

import html as html_lib
from typing import Any, Dict, List, Optional


TYPE_COLORS = {
    "KPI":     "#2e7d32",
    "CHART":   "#1565c0",
    "TABLE":   "#6a1b9a",
    "SIDEBAR": "#37474f",
    "NAV":     "#00838f",
    "HEADER":  "#ef6c00",
    "FILTER":  "#8d6e63",
    "LIST":    "#5d4037",
    "REVIEW":  "#ad1457",
}
DEFAULT_COLOR = "#9e9e9e"


def _esc(value: Any) -> str:
    return html_lib.escape(str(value)) if value is not None else ""


def _render_fields(comp_type: str, fields: Dict[str, Any]) -> str:
    fields = fields or {}

    if comp_type == "KPI":
        return (
            f'<div class="value">{_esc(fields.get("value") or "—")}</div>'
            f'<div class="title">{_esc(fields.get("title") or "")}</div>'
            f'<div class="desc">{_esc(fields.get("description") or "")}</div>'
        )

    if comp_type == "CHART":
        return (
            f'<div class="title">{_esc(fields.get("title") or "(untitled chart)")}</div>'
            f'<div class="tag">{_esc(fields.get("chart_type") or "UNKNOWN")}</div>'
        )

    if comp_type == "TABLE":
        return f'<div class="title">{_esc(fields.get("title") or "(untitled table)")}</div>'

    if comp_type in ("SIDEBAR", "NAV", "LIST"):
        items = fields.get("items") or []
        items_html = "".join(f"<li>{_esc(i)}</li>" for i in items)
        return (
            f'<div class="title">{_esc(fields.get("title") or "")}</div>'
            f'<ul class="items">{items_html}</ul>'
        )

    if comp_type == "HEADER":
        return f'<div class="title">{_esc(fields.get("title") or "")}</div>'

    if comp_type == "FILTER":
        opts = fields.get("options") or []
        opts_html = "".join(f"<li>{_esc(o)}</li>" for o in opts)
        return (
            f'<div class="title">{_esc(fields.get("label") or "")}</div>'
            f'<ul class="items">{opts_html}</ul>'
        )

    if comp_type == "REVIEW":
        rating = fields.get("rating")
        rating_html = f'<span class="tag">★ {_esc(rating)}</span>' if rating else ""
        return (
            f'<div class="title">{_esc(fields.get("reviewer") or "")}</div>'
            f'<div class="desc">{_esc(fields.get("time_ago") or "")} {rating_html}</div>'
            f'<div class="desc">{_esc((fields.get("body") or "")[:80])}</div>'
        )

    return f'<pre class="raw">{_esc(fields)}</pre>'


def render_dashboard_html(
    classified_design: Dict[str, Any],
    validation: Optional[Dict[str, Any]] = None,
) -> str:
    components: List[Dict[str, Any]] = classified_design.get("components", [])
    dashboard_name = classified_design.get("dashboard_name", "Dashboard")

    flagged_ids = set()
    if validation:
        flagged_ids = {issue["id"] for issue in validation.get("issues", [])}

    max_x = max((c["position"]["x"] + c["size"]["width"] for c in components), default=1600)
    max_y = max((c["position"]["y"] + c["size"]["height"] for c in components), default=900)

    boxes = []
    for c in components:
        comp_type = c.get("type", "OTHER")
        color = TYPE_COLORS.get(comp_type, DEFAULT_COLOR)
        x, y = c["position"]["x"], c["position"]["y"]
        w, h = c["size"]["width"], c["size"]["height"]
        flagged = c.get("id") in flagged_ids
        flag_badge = '<span class="flag" title="Flagged by validator">⚠</span>' if flagged else ""

        boxes.append(f'''
        <div class="component {'flagged' if flagged else ''}"
             style="left:{x}px; top:{y}px; width:{w}px; height:{h}px; border-color:{color};">
          <div class="comp-header" style="background:{color};">
            <span class="comp-type">{_esc(comp_type)}</span>
            {flag_badge}
          </div>
          <div class="comp-body">
            {_render_fields(comp_type, c.get("fields"))}
          </div>
        </div>''')

    validation_banner = ""
    if validation is not None:
        status = "✓ valid" if validation.get("valid") else f'⚠ {validation.get("flagged_count", 0)} flagged'
        banner_color = "#2e7d32" if validation.get("valid") else "#c62828"
        validation_banner = (
            f'<div class="validation-banner" style="background:{banner_color};">'
            f'{_esc(dashboard_name)} — {len(components)} components — {status}'
            f'</div>'
        )

    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{_esc(dashboard_name)} — preview</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: system-ui, sans-serif; background:#eceff1; }}
  .validation-banner {{
    position: sticky; top:0; z-index: 10; color:white; padding:10px 20px;
    font-size:14px; font-weight:600;
  }}
  .canvas {{ position: relative; width:{max_x + 40}px; height:{max_y + 40}px; margin:20px; }}
  .component {{
    position:absolute; background:white; border:2px solid; border-radius:6px;
    overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.15);
  }}
  .component.flagged {{ box-shadow:0 0 0 3px #ffca28; }}
  .comp-header {{
    display:flex; justify-content:space-between; align-items:center;
    color:white; font-size:11px; font-weight:700; letter-spacing:.05em;
    padding:3px 8px; text-transform:uppercase;
  }}
  .flag {{ font-size:13px; }}
  .comp-body {{ padding:8px 10px; font-size:12px; color:#333; overflow:auto; height:calc(100% - 22px); }}
  .value {{ font-size:20px; font-weight:700; }}
  .title {{ font-weight:600; margin:2px 0; }}
  .desc {{ color:#666; font-size:11px; }}
  .tag {{ display:inline-block; background:#eee; border-radius:4px; padding:1px 6px; font-size:10px; }}
  .items {{ margin:4px 0 0; padding-left:16px; font-size:11px; }}
  .raw {{ font-size:10px; white-space:pre-wrap; }}
</style>
</head>
<body>
  {validation_banner}
  <div class="canvas">
    {"".join(boxes)}
  </div>
</body>
</html>'''