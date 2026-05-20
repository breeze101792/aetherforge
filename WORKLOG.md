# aetherforge — Work Log

## 2026-05-18: Initial implementation

### Context
Started a new project for hosting LLM-generated web tools. Each tool is an independent process with its own backend (Python) and frontend (HTML/JS/CSS). The main gateway server discovers tools, proxies requests to them, and provides shared infrastructure (persistence, UI components).

### Design phase
- Settled on project name **aetherforge**
- Created `README.md` — project overview and architecture at a glance
- Created `ARCH.md` — full high-level design with components, data flow, route design, lifecycle, directory structure, and design decisions
- Created `PLAN.md` — 9-phase implementation plan with test strategies and verification checklists

Key architectural decisions:
- **Process-per-tool** for crash isolation and hot-add/remove without restart
- **Reverse proxy routing** so browser sees one origin, no CORS issues
- **Central Data API** (`/_api/data/{tool}/{resource}`) backed by SQLite, namespace-isolated per tool
- **Manifest-based discovery** — each tool declares its name, route, version in `manifest.json`
- **Shared frontend** served at `/shared/` for reusable CSS/JS components

### Implementation (9 phases)

**Phase 1 — Scaffolding:**
- Created virtualenv, installed dependencies (fastapi, uvicorn, httpx, watchfiles, pytest)
- Created directory structure: `gateway/`, `runtime/`, `shared/`, `tools/`, `data/`, `tests/`
- Implemented `gateway/settings.py` with dataclass config, env var loading

**Phase 2 — Registry:**
- Implemented `gateway/registry.py` with `ToolRecord` dataclass and thread-safe `Registry`
- Operations: register, unregister, get, get_by_route, list_all, save_to_disk, load_from_disk
- 6 tests passing: CRUD, thread safety, persistence round-trip, missing file handling

**Phase 3 — Tool Runtime:**
- Implemented `runtime/loader.py` — imports tool handler via importlib, reads manifest
- Implemented `runtime/main.py` — FastAPI app wrapper with health endpoint, API mounting, frontend static serving
- Created test fixture `tests/fixtures/minimal-tool/` for testing
- 5 tests passing: health, API, frontend serving, tool info, frontend-only mode

**Phase 4 — Tool Manager:**
- Implemented `gateway/tool_manager.py` — discover, spawn, stop, restart, watch
- Filesystem watcher using `watchfiles` library for hot-add/remove/update
- Bug fix: `watchfiles` returns paths relative to CWD, needed `os.path.realpath()` for macOS symlink resolution (`/var` → `/private/var`)
- Bug fix: `_handle_fs_event` path resolution reworked to use real paths throughout
- 7 tests passing: discover valid/invalid, spawn/stop, port allocation, crash detection, hot-add, hot-remove

**Phase 5 — Reverse Proxy:**
- Implemented `gateway/proxy.py` — longest prefix matching, header/body forwarding, error handling
- Simplified proxy tests to avoid TestClient + httpx.AsyncClient event loop conflicts
- 3 tests passing: 404 for unknown, 502 for dead/stopped, longest prefix matching

**Phase 6 — Data API:**
- Implemented `gateway/data_api.py` — full CRUD at `/_api/data/{tool}/{resource}`
- SQLite with WAL mode, auto-created tables per tool/resource, JSON data column
- Namespace isolation: each tool's data in separate SQLite tables
- Input validation against path traversal in tool/resource names
- Bug fix: `updated_at` can equal `created_at` when operations happen in same second (changed `!=` to `>=`)
- Bug fix: path traversal test used `../` which FastAPI normalizes away (switched to `%2F`)
- 7 tests passing: create/read, pagination, update, delete, namespace isolation, 404, validation

**Phase 7 — Gateway Main App + Portal:**
- Implemented `gateway/main.py` — FastAPI app with lifespan, all components wired together
- Portal dashboard at `/` with tool grid, status colors, empty state, responsive CSS
- Health endpoint at `/_health` returning gateway status and all tool statuses
- Reverse proxy catch-all for unmatched routes

**Phase 8 — Shared Libraries:**
- `shared/backend/data_client.py` — Python HTTP client for Data API, reads `GATEWAY_URL` and `TOOL_NAME` from env
- `shared/frontend/styles/base.css` — CSS reset, design tokens (colors, spacing, typography), utility classes
- `shared/frontend/components/modal.js` — `<forge-modal>` web component with backdrop, close button, slot
- `shared/frontend/utils/dataClient.js` — JavaScript client for Data API

**Phase 9 — Example Tool + E2E:**
- Created `tools/.hello-forge-template/` — demo tool with greeter API and notes persistence
- Backend: `/api/greet`, `/api/notes` (CRUD via DataClient)
- Frontend: interactive page using shared CSS, forge-modal, DataClient JS
- E2E test suite with pytest fixture for cleanup between tests
- Bug fix: moved template out of `tools/` to prevent auto-discovery (dot-prefix not enough, `os.listdir` includes dot-files)
- Bug fix: `_add_tool` helper now prepares tool in temp location first, then moves atomically into `tools/` (avoids race condition where watcher fires before manifest patching)
- Bug fix: `request.url.query` is `str` in newer Starlette, not `bytes` — added isinstance check
- Bug fix: DB file cleaned between E2E tests to avoid stale data accumulation
- 9 tests passing: gateway startup, portal, frontend serving, API proxying, persistence flow, hot-remove, shared assets, portal listing, health tracking

### Final results
- **37/37 tests passing** across all 6 test files
- Live smoke test confirmed: portal renders, tool hot-adds, frontend serves, API responds, Data API persists, shared CSS loads

### Files created (26 source files + 6 test files)

```
aetherforge/
├── gateway/
│   ├── __init__.py
│   ├── settings.py
│   ├── registry.py
│   ├── tool_manager.py
│   ├── proxy.py
│   ├── data_api.py
│   └── main.py
├── runtime/
│   ├── __init__.py
│   ├── loader.py
│   └── main.py
├── shared/
│   ├── __init__.py
│   ├── backend/
│   │   ├── __init__.py
│   │   └── data_client.py
│   └── frontend/
│       ├── styles/base.css
│       ├── components/modal.js
│       └── utils/dataClient.js
├── tools/.hello-forge-template/
│   ├── manifest.json
│   ├── backend/handler.py
│   └── frontend/
│       ├── index.html
│       ├── app.js
│       └── style.css
├── tests/
│   ├── fixtures/minimal-tool/...
│   ├── test_registry.py
│   ├── test_runtime.py
│   ├── test_tool_manager.py
│   ├── test_proxy.py
│   ├── test_data_api.py
│   └── test_e2e.py
├── README.md
├── ARCH.md
├── PLAN.md
└── requirements.txt
```

### Bugs encountered and fixed
1. `watchfiles` paths relative to CWD → use `os.path.realpath()` for symlink-safe path resolution
2. macOS `/var` symlink → `os.path.realpath()` on both changed path and tools directory
3. `request.url.query` returned `str` in Starlette ≥1.0 → added isinstance check for bytes/str
4. Race condition: watcher fired during tool directory creation before manifest patching → prepare tool in temp location, move atomically
5. Template auto-discovered by gateway → moved out of `tools/` directory
6. Stale DB data across E2E test runs → clean DB in fixture
7. `updated_at == created_at` in same-second operations → changed test assertion from `!=` to `>=`
