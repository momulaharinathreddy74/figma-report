# Figma Report Generator — Plugin

A Figma plugin that extracts the design tree from a selected frame and saves it to Supabase.

## Usage

1. Open Figma and run the plugin
2. Select any frame or component in your design
3. Click **Extract Design** — the full node tree appears as JSON in the panel
4. Click **Save to Database** — the JSON is POSTed directly to Supabase
5. Click **Copy JSON** to copy the extracted JSON to your clipboard
6. Click **Cancel** to close the plugin

## Setup

### 1. Install dependencies

```bash
npm install
```

### 2. Add Supabase credentials

Create `config.local.ts` (already gitignored):

```ts
export const SUPABASE_URL = "https://your-project.supabase.co";
export const SUPABASE_KEY = "your-anon-key";
```

### 3. Build

```bash
npm run build
```

### 4. Load in Figma

- Plugins → Development → Import plugin from manifest
- Select `manifest.json` from this folder

## Available Scripts

| Command | Description |
|---|---|
| `npm run build` | Compile `code.ts` → `code.js` |
| `npm run watch` | Watch mode — rebuilds on file change |
| `npm run typecheck` | TypeScript type check without emitting |
| `npm run lint` | Run ESLint |

## How Extraction Works

`code.ts` walks the selected Figma node tree recursively:

- Collects `id`, `name`, `type`, `x/y`, `width/height`
- Extracts fills, strokes, opacity, corner radius, effects
- Reads auto-layout fields (mode, padding, spacing)
- For TEXT nodes: reads `characters` (guarded against unloaded fonts)
- Depth-limited to 50 levels to prevent stack overflow on deep trees

The UI panel (`ui.html`) performs the Supabase HTTP POST — the plugin sandbox has unreliable `fetch` support, but the UI runs in a real browser iframe.

## Supabase Table

```sql
CREATE TABLE designs (
  id             uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at     timestamptz DEFAULT now(),
  name           text,
  figma_node_id  text,
  design_json    jsonb
);
```
