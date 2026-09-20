# Figma Report Generator

A full-stack pipeline that extracts Figma design data, classifies dashboard components, validates the output, and generates a structured dashboard configuration — all without requiring Figma's REST API or a paid integration.

---

## Project Overview

```
Figma Canvas
     │
     ▼
Figma Plugin  (code.ts + ui.html)
     │  extracts design tree → saves to Supabase
     ▼
Supabase  (Postgres — raw design_json stored)
     │
     ▼
FastAPI Backend  (Python)
     │
     ├── normalizer.py    → clean, flat node tree with bubbled-up texts
     ├── classifier.py    → weighted signal scoring → KPI / CHART / TABLE / ...
     ├── validator.py     → schema check on classified output
     ├── renderer.py      → HTML visual preview (absolute-positioned)
     └── Orchestrator.py  → deterministic layout + optional LLM gap-fill
```

---

## Repository Structure

```
figma/
├── backend/
│   ├── main.py               FastAPI app — all HTTP endpoints
│   ├── normalizer.py         Raw Figma JSON → normalized node tree
│   ├── classifier.py         Weighted scoring → component classification
│   ├── validator.py          Schema / contract check on classified output
│   ├── renderer.py           Classified output → HTML visual preview
│   ├── Orchestrator.py       Grid layout engine + targeted LLM resolver
│   ├── static/
│   │   └── dashboard.html    Backend Manager UI (served at GET /)
│   └── .env                  SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY
│
└── figma-plugin/
    └── figma report generator/
        ├── code.ts           Plugin sandbox logic (TypeScript)
        ├── code.js           Compiled bundle (esbuild output)
        ├── ui.html           Plugin panel UI
        ├── manifest.json     Figma plugin manifest
        ├── config.local.ts   Supabase credentials (gitignored)
        └── package.json      Build scripts + dependencies
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Design tool | Figma |
| Plugin language | TypeScript (compiled with esbuild) |
| Database | Supabase (PostgreSQL) |
| Backend | Python 3.9 · FastAPI · Uvicorn |
| LLM (optional) | Anthropic Claude Haiku (gap-fill only) |
| Backend UI | Vanilla HTML/JS served at `GET /` |

---

## How It Works — Step by Step

### Step 1 — Extract (Figma Plugin)

The plugin runs inside Figma's sandbox (`code.ts`). When the user selects a frame and clicks **Extract Design**, it:

1. Walks the selected node tree recursively using `extractNode()`
2. Collects `id`, `name`, `type`, `x/y`, `width/height`, `fills`, `strokes`, `characters` (text), auto-layout fields, and typography for every node
3. Sends the JSON to the UI panel via `figma.ui.postMessage`

When the user clicks **Save to Database**, the plugin sends the JSON directly to Supabase's REST API from the UI iframe (the sandbox has unreliable `fetch` support — the iframe doesn't):

```
POST https://<project>.supabase.co/rest/v1/designs
{
  "name": "Body",
  "figma_node_id": "1:600",
  "design_json": { ...full node tree... }
}
```

**Key files:** `code.ts`, `ui.html`, `config.local.ts`, `manifest.json`

---

### Step 2 — Normalize (`normalizer.py`)

Raw Figma JSON has text scattered across leaf `TEXT` nodes deep in the tree. The normalizer walks the tree recursively and **bubbles all descendant text strings up** to each ancestor node's `texts` array (de-duplicated). This means every parent frame already has a flat list of all text visible inside it — the classifier can read it without recursing.

Also extracts: `position`, `size`, `layout` (auto-layout mode/padding/spacing), `style` (fills, strokes, opacity, corner radius).

```python
# Every parent gets a deduplicated list of all text in its subtree
normalized["texts"] = ["Total Orders", "75", "4% (30 days)"]
```

**Input:** raw `design_json` from Supabase  
**Output:** normalized node tree with `texts`, `position`, `size`, `layout`, `style`, `children`

---

### Step 3 — Classify (`classifier.py`)

Uses a **weighted signal / confidence-score decision tree** — not a first-match-wins list.

For every node, three independent score buckets are computed in parallel:

| Bucket | Example signals |
|---|---|
| **KPI** | compact size (80–600×60–300px), exactly 1 numeric value, single percentage, domain keyword (revenue / orders / …), 2–5 text strings |
| **CHART** | month/day axis labels (Jan–Dec / Sun–Sat), multiple % values (pie), many numeric Y-axis values, `chart`/`graph` in node name, many children |
| **TABLE** | column header words (name / price / status / …), wide+tall size (≥500×150), many text strings (≥10), repeated equal-height children (rows) |

**Classification rules:**
- Node must reach `MIN_RAW_SCORE = 10` in the winning bucket
- Winner must beat runner-up by `MARGIN = 4` points (prevents ambiguous ties)
- Large frames (dashboard root, page containers) are always skipped — they're walked into, not classified

Each component result includes:
```json
{
  "id": "1:480",
  "type": "KPI",
  "confidence": 0.99,
  "score": 16,
  "signals": [
    { "weight": 4, "reason": "compact size 337×172 typical of KPI card" },
    { "weight": 5, "reason": "exactly one numeric value" },
    ...
  ],
  "fields": { "title": "Total Orders", "value": "75" }
}
```

Supports types: `KPI · CHART · TABLE · SIDEBAR · NAV · HEADER · FILTER · LIST`

---

### Step 4 — Validate (`validator.py`)

Pure schema check — no network calls. Checks that each component has the fields its type requires:

| Type | Required fields |
|---|---|
| KPI | `value`, `title` |
| CHART | `title` or `chart_type` (not both missing) |
| TABLE | `title` |
| SIDEBAR / NAV / LIST | `items` (non-empty) |
| FILTER | `label` |

Returns:
```json
{
  "valid": false,
  "component_count": 12,
  "flagged_count": 2,
  "issues": [
    { "id": "1:704", "type": "CHART", "problems": ["missing 'title'"] }
  ]
}
```

---

### Step 5 — Render (`renderer.py`)

Generates a **self-contained HTML preview** using each component's real Figma `x/y/width/height` as absolute CSS positions. No React, no bundler — pure string templating.

- Each component is rendered as a colour-coded box (green = KPI, blue = CHART, purple = TABLE, etc.)
- Validator-flagged components get a yellow warning border + ⚠ badge
- Available at `GET /designs/{id}/render` in the browser

---

### Step 6 — Orchestrate (`Orchestrator.py`)

Two-tier pipeline:

**Tier 1 — Deterministic layout (always runs, zero cost)**
- Groups components into rows using vertical Y-overlap clustering
- Computes 12-column grid spans proportional to each component's width
- Full-height structural elements (sidebars, nav rails) are separated out first — they would otherwise swallow every row due to their Y-range

**Tier 2 — Gap-fill (opt-in, costs tokens)**
- For each validator-flagged component, tries rule-based resolution first (free): looks for nearby orphan heading text within 200px
- If rule-based fails AND `use_llm_fallback=True`, makes one small, targeted Claude Haiku call — just the flagged component + its 4 nearest spatial neighbors
- Most designs have zero flagged components → zero LLM calls
- Output includes `unresolved` list for anything that couldn't be fixed

**Output:**
```json
{
  "dashboard_name": "Food Delivery Dashboard",
  "sections": [
    {
      "section_name": "KPI Summary",
      "components": [
        { "id": "1:480", "type": "KPI", "grid_column_span": 3, "fields": { "title": "Total Orders", "value": "75" } }
      ]
    }
  ],
  "unresolved": []
}
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Backend Manager UI |
| `GET` | `/health` | Health check |
| `GET` | `/designs` | List all saved designs |
| `POST` | `/designs` | Save a new design |
| `GET` | `/designs/{id}` | Get raw design JSON |
| `POST` | `/designs/{id}/normalize` | Normalize node tree |
| `POST` | `/designs/{id}/classify` | Classify components |
| `GET` | `/designs/{id}/render` | HTML visual preview |
| `POST` | `/designs/{id}/orchestrate` | Full pipeline → dashboard config |

---

## Setup & Running

### 1. Backend

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install fastapi uvicorn supabase python-dotenv anthropic

# Create .env
echo "SUPABASE_URL=https://your-project.supabase.co" >> .env
echo "SUPABASE_KEY=your-anon-key" >> .env
echo "ANTHROPIC_API_KEY=your-key" >> .env   # optional — only for LLM fallback

# Run
uvicorn main:app --reload --port 8001
```

Open `http://127.0.0.1:8001` for the Backend Manager UI.  
Open `http://127.0.0.1:8001/docs` for Swagger.

---

### 2. Figma Plugin

```bash
cd "figma-plugin/figma report generator"
npm install

# Add your Supabase credentials
# Edit config.local.ts:
#   export const SUPABASE_URL = "https://your-project.supabase.co";
#   export const SUPABASE_KEY = "your-anon-key";

# Build
npm run build
```

**Load in Figma:**
1. Open Figma → Plugins → Development → Import plugin from manifest
2. Select `figma-plugin/figma report generator/manifest.json`
3. Run the plugin, select a frame, click **Extract Design** → **Save to Database**

---

### 3. Supabase Setup

Run this SQL in the Supabase SQL Editor:

```sql
CREATE TABLE IF NOT EXISTS designs (
  id             uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at     timestamptz DEFAULT now(),
  name           text,
  figma_node_id  text,
  design_json    jsonb
);

-- Allow anon reads and writes
CREATE POLICY "allow anon insert" ON public.designs FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "allow anon select" ON public.designs FOR SELECT TO anon USING (true);
```

---

## Classifier Signal Weights (Reference)

### KPI Signals

| Signal | Weight |
|---|---|
| Name contains `kpi` | +10 |
| Name contains `big number` | +10 |
| Name contains `metric` | +8 |
| Compact size (80–600 × 60–300px) | +4 |
| Exactly 1 numeric value | +5 |
| Single percentage | +4 |
| Currency symbol or abbreviated value | +3 |
| Domain keyword (revenue, orders, …) | +3 |
| 2–5 text strings | +2 |
| Large size (>700px wide or >350px tall) | −8 |
| Only 1 text string | −6 |
| More than 10 text strings | −6 |

### CHART Signals

| Signal | Weight |
|---|---|
| Name contains `chart` / `graph` | +10 |
| 6+ month labels | +8 |
| 3+ percentage values | +8 |
| 5+ day labels | +7 |
| 5+ numeric Y-axis values | +5 |
| 3–5 month labels | +5 |
| Multiple year labels (multi-series) | +4 |

### TABLE Signals

| Signal | Weight |
|---|---|
| 4+ column header words | +10 |
| Name contains `table` | +10 |
| Repeated equal-height children (rows) | +6 |
| Wide + tall size (≥500 × 150px) | +4 |
| 20+ text strings | +5 |

---

## Key Design Decisions

**Why delegate Supabase fetch to the UI iframe?**  
Figma's plugin sandbox has unreliable `fetch` support. The UI panel runs in a real browser iframe with full network access, so `code.ts` passes the URL + API key to `ui.html` which performs the actual HTTP request.

**Why weighted scoring instead of first-match-wins?**  
A node with months + money values would match both CHART (axis labels) and KPI (numeric values) under a simple rule list. Weighted scoring lets all signals vote simultaneously — the class with the strongest combined evidence wins, and ambiguous ties (score gap < `MARGIN`) fall through to `OTHER` rather than making a confident wrong guess.

**Why is the LLM off by default in the Orchestrator?**  
Most designs have zero validator-flagged components, meaning zero LLM calls needed. Making it opt-in (`use_llm_fallback=True`) means running the pipeline over hundreds of designs costs nothing unless you explicitly need the gap-fill.

**Why does the normalizer de-duplicate bubbled texts?**  
Figma component instances share masters. Without deduplication, the same text string (e.g. `"Revenues"`) appears 2–3× at every ancestor, inflating text counts and causing the classifier to misfire on thresholds like `len(texts) <= 6`.
