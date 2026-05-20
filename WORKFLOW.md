# Development Workflow

## Quick start

```bash
./start.sh           # production: port 8000, data/aetherforge.db
./start.sh --test    # test: port 8001, data/test.db
```

## Project layout

```
aetherforge/
├── gateway/          # Central gateway: routing, proxy, Data API
├── runtime/          # Per-tool process entry point
├── shared/
│   ├── backend/      # Python DataClient for tools
│   └── frontend/     # Shared CSS, web components, JS utils
├── tools/            # Each tool lives here (auto-discovered)
│   ├── markdown-note/
│   │   ├── manifest.json
│   │   ├── backend/handler.py
│   │   └── frontend/{index.html,app.js,style.css}
│   └── prompt-vault/
├── tests/            # Test suite
│   └── fixtures/     # Minimal tool template for tests
└── data/             # Runtime data (DB, registry — gitignored)
```

## Adding a new tool

1. Create `tools/<tool-name>/manifest.json`:
   ```json
   { "name": "my-tool", "route": "/my", "version": "1.0.0", "description": "..." }
   ```

2. Create `tools/<tool-name>/backend/handler.py` with a `create_app()` function that returns a FastAPI app. Use `shared.backend.data_client.DataClient` for persistence.

3. Create `tools/<tool-name>/frontend/` with `index.html`, `app.js`, `style.css`. Reference shared assets at `/shared/styles/base.css`, `/shared/components/modal.js`, `/shared/utils/dataClient.js`.

4. Drop the folder into `tools/`. The watcher detects it and spawns the process automatically. No gateway restart needed.

## Backend conventions

- Each tool gets its own process (uvicorn on a dynamic port) for crash isolation.
- Tools communicate with the gateway Data API via `DataClient` (HTTP to `/_api/data/{tool}/{resource}`).
- The gateway reverse-proxies `/<route>/*` to the tool process.
- Path traversal protection: always resolve with `os.path.realpath()` and verify the result stays within the allowed root.

## Frontend conventions

- No build step. Plain HTML/CSS/JS served as static files.
- Use `<forge-modal>` from `/shared/components/modal.js` for dialogs.
- Use `DataClient` from `/shared/utils/dataClient.js` for persistence (set `.namespace` to your tool name).
- Reference design tokens from `/shared/styles/base.css` (`--forge-primary`, `--forge-border`, etc.).

## Testing

### Run all tests
```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

### Run a single test file
```bash
python -m pytest tests/test_e2e.py -v
```

### Run a single test
```bash
python -m pytest tests/test_e2e.py::test_data_api_crud -v
```

### Test architecture

| Test file | What it covers | DB isolation |
|---|---|---|
| `test_data_api.py` | CRUD, pagination, namespace isolation, validation | Temp dir per test |
| `test_registry.py` | In-memory registry operations, persistence, thread safety | No DB needed |
| `test_runtime.py` | Tool process startup, health, frontend serving | No DB needed |
| `test_tool_manager.py` | Discovery, spawn/stop, crash detection, hot-add/remove | Temp dir + in-memory |
| `test_proxy.py` | Route matching, error cases (404, 502) | No DB needed |
| `test_e2e.py` | Full gateway + tool integration | `AETHERFORGE_ENV=test` → `data/test.db` |

### Test flow for E2E

1. Fixture (`_setup_teardown`) runs before each test:
   - Kills any lingering gateway/tool processes
   - Removes e2e-* tools from `tools/`
   - Deletes `data/test.db` and `data/test-registry.json` for fresh state
2. `_start_gateway()` spawns gateway with `AETHERFORGE_ENV=test` — this isolates test data from production
3. `_add_tool()` prepares a tool from the fixture template, patches manifest and frontend paths, then atomically moves it into `tools/`
4. Test exercises the tool through the gateway (HTTP)
5. Teardown cleans up e2e-* tools, kills processes, removes test db

### DB separation

Production and test use different database files:

| Mode | Env var | DB path | Registry path | Default port |
|---|---|---|---|---|
| prod | `AETHERFORGE_ENV=prod` (default) | `data/aetherforge.db` | `data/registry.json` | 8000 |
| test | `AETHERFORGE_ENV=test` | `data/test.db` | `data/test-registry.json` | 8001 (hardcoded in E2E tests) |

Set via `start.sh --test` or by exporting `AETHERFORGE_ENV=test` before running `python -m gateway.main`. The E2E test fixture sets this automatically — production data is never touched by tests.

## Hot-reload

The gateway watches `tools/` via `watchfiles`. Changes are detected automatically:

- **New tool**: drop a folder into `tools/` → spawns automatically
- **Modified tool**: edit any file in the tool folder → restarts automatically
- **Removed tool**: delete the folder → stops automatically

No manual gateway restart needed during development.
