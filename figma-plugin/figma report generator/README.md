# Figma Report Generator

A Figma plugin that extracts design data from a selected frame and outputs it as structured JSON. Useful for design-to-code workflows, design audits, and report generation.

## Features

- Select any frame or element on the canvas
- Extract its full node tree as JSON (id, name, type, position, dimensions, text content, children)
- Copy the JSON output to clipboard with one click

## Prerequisites

- [Figma Desktop App](https://www.figma.com/downloads/) (plugins do not work in the browser version)
- [Node.js](https://nodejs.org/en/download/) (comes with npm)

## Setup

```bash
# Install dependencies
npm install

# Build the plugin
npm run build
```

This compiles `code.ts` → `code.js`, which Figma needs to load the plugin.

## Loading the Plugin in Figma

1. Open a file in the **Figma desktop app**.
2. Go to **Plugins → Development → Import plugin from manifest…**
3. Navigate to this project folder and select `manifest.json`.
4. The plugin will appear in your Plugins menu under Development.

## Usage

1. Select a **frame** (or any element) on the canvas.
2. Run: **Plugins → Development → Figma Report Generator**.
3. Click **"Extract Design"** in the plugin panel.
4. The JSON data appears in the text area.
5. Click **"Copy JSON"** to copy it to your clipboard.

## Development

To watch for changes and auto-rebuild:

```bash
npm run watch
```

After each rebuild, re-run the plugin in Figma to pick up changes.

> **Note:** If `npm run build` fails on Windows with a "not recognized" error, run the compiler directly:
> ```bash
> node node_modules/typescript/bin/tsc -p tsconfig.json
> ```

## Project Structure

| File            | Description                                      |
| --------------- | ------------------------------------------------ |
| `code.ts`       | Plugin backend — runs in Figma's sandbox, extracts node data |
| `ui.html`       | Plugin UI — buttons and textarea for interaction |
| `manifest.json` | Figma plugin manifest                            |
| `tsconfig.json` | TypeScript configuration                         |
