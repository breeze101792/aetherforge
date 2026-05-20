# aetherforge

A web platform for hosting AI-built tools. Each tool is a self-contained package with its own backend (Python) and frontend (HTML/JS/CSS), mounted automatically by the main server.

## Architecture

```
aetherforge/
├── server/                    # Main FastAPI application
│   ├── main.py               # Entry point — discovers & mounts tools
│   ├── router.py             # Dynamic tool router
│   └── middleware/            # Auth, logging, CORS, etc.
│
├── tools/                     # AI-built tools (each is self-contained)
│   └── <tool-name>/
│       ├── manifest.json      # { name, route, version, icon, description }
│       ├── backend/
│       │   ├── __init__.py
│       │   └── handler.py     # FastAPI APIRouter — tool's API endpoints
│       └── frontend/
│           ├── index.html
│           ├── app.js
│           └── style.css
│
├── shared/                    # Reusable across tools
│   ├── backend/               # Python: LLM client, DB helpers, models
│   └── frontend/              # JS/CSS: UI components, design tokens, utils
│
├── static/                    # Global static assets (favicon, fonts, etc.)
├── requirements.txt
└── README.md
```

## How it works

1. **Tool discovery** — On startup, the server scans `tools/` for folders containing a `manifest.json`. Each valid tool is mounted automatically.

2. **Routing** — Each tool declares its route prefix in `manifest.json` (e.g., `"/image-gen"`). The main server mounts the tool's `APIRouter` for backend endpoints and serves its `frontend/` folder as static files under that prefix.

3. **Isolation** — Tools don't know about each other. They only depend on `shared/` and their own code.

4. **Shared components** — Common functionality (LLM API calls, auth, UI components, design tokens) lives in `shared/` so tools don't reinvent the wheel.

## manifest.json

```json
{
  "name": "Image Generator",
  "route": "/image-gen",
  "version": "1.0.0",
  "description": "Generate images from text prompts",
  "icon": "🖼️"
}
```

## Two modes per tool

Each tool can choose its rendering strategy:
- **Multi-page** — traditional HTML pages with full page loads, server-rendered via Jinja2
- **SPA-like** — single HTML shell + client-side JS that calls the tool's own API endpoints

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend server | Python / FastAPI |
| Backend per tool | Python (FastAPI APIRouter) |
| Frontend | HTML + vanilla JS + CSS |
| Shared frontend | Web components or ES modules |
| LLM integration | Shared `llm_client` in `shared/backend/` |
