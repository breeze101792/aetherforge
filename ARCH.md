# aetherforge — High-Level Design

## Overview

aetherforge is a web platform that hosts AI-generated tools. Each tool is an independent process with its own backend and frontend. The gateway server discovers tools, routes traffic to them, and provides shared infrastructure (persistence, UI components, utilities). Tools can be added, updated, or removed without restarting the gateway.

## Architecture

```
                         ┌──────────────────────┐
                         │     Browser           │
                         └──────────┬───────────┘
                                    │  HTTP (port 8000)
                                    ▼
                         ┌──────────────────────┐
                         │    Gateway Server     │
                         │    (FastAPI)          │
                         │                       │
                         │  ┌─────────────────┐  │
                         │  │  Reverse Proxy   │  │
                         │  └────────┬────────┘  │
                         │           │           │
                         │  ┌────────┴────────┐  │
                         │  │  Tool Manager    │  │
                         │  │  (spawn/stop/    │  │
                         │  │   watch fs)      │  │
                         │  └────────┬────────┘  │
                         │           │           │
                         │  ┌────────┴────────┐  │
                         │  │  Registry        │  │
                         │  │  (name→port map) │  │
                         │  └─────────────────┘  │
                         │                       │
                         │  ┌─────────────────┐  │
                         │  │  Data API        │  │
                         │  │  (SQLite via     │  │
                         │  │   central API)   │  │
                         │  └─────────────────┘  │
                         │                       │
                         │  Shared frontend       │
                         │  (/shared/*)           │
                         └──┬───────┬───────┬────┘
                            │       │       │
                    proxy   │       │       │  proxy
              /tool-a/*     │       │  /tool-b/*
                            ▼       │       ▼
               ┌────────────┐      │      ┌────────────┐
               │  Tool A    │      │      │  Tool B    │
               │  Process   │      │      │  Process   │
               │  :8101     │      │      │  :8102     │
               │            │      │      │            │
               │ ┌────────┐ │      │      │ ┌────────┐ │
               │ │backend │ │      │      │ │backend │ │
               │ │handler │ │      │      │ │handler │ │
               │ └────────┘ │      │      │ └────────┘ │
               │ ┌────────┐ │      │      │ ┌────────┐ │
               │ │frontend│ │      │      │ │frontend│ │
               │ │static  │ │      │      │ │static  │ │
               │ └────────┘ │      │      │ └────────┘ │
               └────────────┘      │      └────────────┘
                                   │
                          More tools as needed
                          (one per port, auto-assigned)
```

## Components

### 1. Gateway Server (FastAPI)

The single entry point. All client requests hit this server on port 8000.

Responsibilities:
- **Reverse proxy** — forwards requests to the correct tool process based on URL prefix
- **Static file serving** — serves shared frontend assets at `/shared/`
- **Health dashboard** — lists all registered tools at `/` (optional)
- **Does NOT** run any tool logic itself

### 2. Tool Manager

Manages the lifecycle of tool processes.

- On startup: scans `tools/` directory, reads each `manifest.json`, spawns a process for each valid tool
- **Hot-add**: watches `tools/` via filesystem events. New folder with valid manifest → spawn process → register route. No restart.
- **Hot-remove**: detects folder deletion → stop process → unregister route
- **Hot-update**: detects manifest or code change → restart that tool's process only
- Assigns each tool a free port from a configured range (e.g., 8101–8199)
- Passes the assigned port and gateway URL to the tool process via environment variables

### 3. Registry

An in-memory table maintained by the gateway.

```
tool_name → { port, status, pid, started_at, manifest }
```

Used by the reverse proxy to route requests. Persisted to disk as `registry.json` so the gateway can recover after its own restart (re-attach to existing tool processes or respawn them).

### 4. Data API

A central HTTP API exposed by the gateway for tool processes to persist data.

- Tools do **not** access SQLite directly
- Tools call `http://localhost:8000/_data/...` for CRUD operations
- Each tool gets its own namespace (table prefix) based on its name
- API: `GET/POST/PUT/DELETE /_data/<tool_name>/<resource>`
- This keeps SQLite access centralized, makes migration to another DB transparent later

### 5. Tool Runtime

Each tool runs as a **separate process** with its own HTTP server.

A tool process is a minimal FastAPI (or lighter) app that:
- Listens on the port assigned by the Tool Manager
- Serves its own `frontend/` files as static assets
- Exposes its backend logic as HTTP endpoints
- Calls the gateway Data API when it needs persistence
- Calls external APIs (LLMs, etc.) directly — the gateway does not gate this

The tool runtime is **generic** — a thin wrapper that loads the tool's handler code and frontend files. Most of the code in a tool process is the same for every tool; only the handler logic and frontend differ.

```
Tool process boilerplate (provided by aetherforge):
  - HTTP server setup
  - Static file serving (tool's frontend/)
  - Config from env vars (port, gateway URL, tool name)
  - Error handling + logging

Tool-specific code (generated by LLM):
  - backend/handler.py  — API endpoints
  - frontend/*          — HTML, JS, CSS
```

### 6. Shared Libraries

**Backend (Python):**
- `data_client.py` — HTTP client for the Data API (tools use this instead of raw `requests`)
- `tool_utils.py` — helpers for parsing env vars, logging, error responses
- Future: `llm_client.py` if we add a central LLM proxy

**Frontend (JS/CSS):**
- `components/` — reusable UI elements (modal, toast, tabs, etc.)
- `styles/` — CSS variables, reset, layout primitives
- `utils/` — `dataClient.js`, form helpers, markdown renderer

Served by the gateway at `/shared/`. Tools reference them with absolute paths:

```html
<link rel="stylesheet" href="/shared/styles/base.css">
<script type="module" src="/shared/components/modal.js"></script>
```

## Route Design

```
/                          → Gateway dashboard (tool listing)
/_data/<tool>/<resource>   → Data API (CRUD, internal only)
/_health                   → Gateway health check
/shared/*                  → Shared frontend assets

/<tool-route>/*            → Proxied to tool process
                              e.g., /image-gen/* → localhost:8101/*
```

For each tool, the gateway proxies:
- `/<route>/`       → tool's index.html
- `/<route>/api/*`  → tool's backend endpoints
- `/<route>/*`      → tool's static files (JS, CSS, images)

## Manifest Specification

```json
{
  "name": "image-generator",
  "route": "/image-gen",
  "version": "1.0.0",
  "description": "Generate images from text prompts using DALL-E",
  "entrypoint": "backend.handler:create_app",
  "python": "python3"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Unique tool identifier (snake_case). Used as namespace in Data API |
| `route` | yes | URL prefix for this tool. Must start with `/` |
| `version` | yes | Semver |
| `description` | yes | Human-readable, shown on dashboard |
| `entrypoint` | no | Module:function that returns the FastAPI/ASGI app. Default: `backend.handler:create_app` |
| `python` | no | Python interpreter to use. Default: `python3` |

## Tool Lifecycle

```
  Directory created
       │
       ▼
  Tool Manager detects new tool
       │
       ▼
  Read manifest.json → validate
       │
       ▼
  Assign free port (8101–8199)
       │
       ▼
  Spawn: python -m aetherforge.tool_runtime --port=8101 --tool=image-generator
       │
       ▼
  Tool process starts → health check (poll /_health)
       │
       ▼
  Register in Registry → route goes live
       │
       ▼
  ┌─ Running ──────────────────────────────┐
  │  - Serves requests                     │
  │  - Gateway watches for fs changes      │
  │  - On manifest change → restart tool   │
  │  - On directory delete → stop tool     │
  │  - On crash → detected by health poll  │
  │               → auto-restart (3 tries) │
  └────────────────────────────────────────┘
```

## Data Flow

### Requesting a tool's page
```
Browser ──GET /image-gen/──▶ Gateway ──proxy──▶ Tool Process (port 8101)
                                                    │
                                                    ▼
                                            Serves frontend/index.html
                                            (or backend endpoint)
```

### Tool calling the Data API
```
Tool Process ──POST /_data/my-tool/results──▶ Gateway
                                                   │
                                                   ▼
                                            Validates tool namespace
                                                   │
                                                   ▼
                                            SQLite: INSERT INTO t_my_tool_results
                                                   │
                                                   ▼
                                            Returns { id, ... }
```

### Loading shared frontend
```
Browser ──GET /shared/components/modal.js──▶ Gateway ──serve static file──▶ shared/frontend/components/modal.js
```

## Directory Structure (detailed)

```
aetherforge/
├── gateway/                       # Gateway server package
│   ├── __init__.py
│   ├── main.py                   # FastAPI app, startup, middleware
│   ├── proxy.py                  # Reverse proxy logic (httpx or aiohttp)
│   ├── tool_manager.py           # Discover, spawn, stop, watch tools
│   ├── registry.py               # Tool → port mapping
│   ├── data_api.py               # /_data endpoints + SQLite access
│   └── settings.py               # Config (port range, db path, etc.)
│
├── runtime/                      # Tool runtime (executed by each tool process)
│   ├── __init__.py
│   ├── main.py                   # Entry: reads env, loads tool, starts server
│   └── loader.py                 # Imports tool's handler, mounts frontend
│
├── tools/                        # AI-generated tools
│   └── <tool-name>/
│       ├── manifest.json
│       ├── backend/
│       │   ├── __init__.py
│       │   └── handler.py        # create_app() → FastAPI/ASGI app
│       └── frontend/
│           ├── index.html
│           ├── app.js
│           └── style.css
│
├── shared/
│   ├── backend/                   # Python libs for tools to import
│   │   ├── __init__.py
│   │   ├── data_client.py        # HTTP client for the Data API
│   │   └── tool_utils.py         # Env parsing, logging, errors
│   └── frontend/                  # Served by gateway at /shared/
│       ├── components/
│       │   ├── modal.js
│       │   ├── toast.js
│       │   └── tabs.js
│       ├── styles/
│       │   ├── base.css          # CSS reset + variables
│       │   └── layout.css        # Grid/flex primitives
│       └── utils/
│           ├── dataClient.js     # JS client for Data API
│           └── helpers.js
│
├── data/                          # SQLite DB + registry.json
│   └── aetherforge.db
│
├── requirements.txt
├── README.md
└── ARCH.md
```

## Key Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Process-per-tool | Crash isolation, no-restart hot-add/hot-remove, independent lifecycle |
| 2 | Reverse proxy routing | Browser sees one origin, no CORS issues, tools are transparent to client |
| 3 | Central Data API | Single SQLite access point, namespaced per tool, DB engine swappable later |
| 4 | Tool-agnostic gateway | Gateway never assumes what a tool does — it only routes and provides infra |
| 5 | Shared frontend at `/shared/` | Absolute paths work from any tool, no bundler needed, easy for LLM to generate |
| 6 | Generic runtime | Tool processes are 90% boilerplate. Tools only provide handler logic + frontend |
| 7 | File watching for hot changes | No admin API needed yet, just filesystem operations trigger lifecycle changes |

## Future: Central API System

Beyond the Data API, the gateway may grow a broader central API layer that tools call into instead of reaching out to external services directly. This keeps cross-cutting concerns centralized.

Planned capabilities (add as needed):

| API | Purpose | Priority |
|-----|---------|----------|
| `/_api/data/*` | CRUD persistence (exists today as Data API) | done |
| `/_api/llm/*` | Central LLM proxy — tools send prompts, gateway handles provider/auth/keys | later |
| `/_api/auth/*` | User/session management if the platform goes multi-user | later |
| `/_api/events/*` | Pub/sub bus — Tool A emits event, Tool B subscribes | later |
| `/_api/config/*` | Central key-value config per tool, managed via dashboard | later |
| `/_api/files/*` | File upload/download with central storage | later |

The principle: tools always call `/_api/*` on the gateway rather than managing their own DB connections, API keys, or file storage. The gateway owns infrastructure; tools own logic.

## Open Questions

1. **Tool inter-communication** — Should Tool A be able to call Tool B's API? Currently no. The events API above would be the cleaner way to enable composition without tight coupling. Defer until a concrete use case.
2. **Auth** — Not needed now (VLAN, single user). When it is: plug into gateway as middleware, tools receive verified user identity via header (`X-User`). The central API system handles this.
3. **Streaming** — SSE/WebSocket passthrough through the proxy. The proxy needs to handle streaming responses for real-time LLM output. The future `/_api/llm/*` would handle this centrally.
4. **Tool dependencies** — If a tool needs `pillow` or `numpy`, does it declare them in `manifest.json`? The tool manager could `pip install` them on spawn.
