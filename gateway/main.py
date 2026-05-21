import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from gateway.data_api import router as data_router
from gateway.proxy import ToolProxy
from gateway.registry import Registry
from gateway.settings import Settings
from gateway.tool_manager import ToolManager

settings = Settings.from_env()
registry = Registry()
tool_manager = ToolManager(registry, settings)
tool_proxy = ToolProxy(registry)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.tools_dir, exist_ok=True)
    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    registry.load_from_disk(settings.registry_path)

    tools = tool_manager.discover()
    for tool_path, manifest in tools:
        existing = registry.get(manifest["name"])
        if existing is None:
            tool_manager.spawn_tool(tool_path, manifest)

    tool_manager.watch()
    yield
    for record in registry.list_all():
        tool_manager.stop_tool(record.name)
    registry.save_to_disk(settings.registry_path)
    await tool_proxy.close()


app = FastAPI(title="Aether Forge", lifespan=lifespan)
app.state.db_path = settings.db_path

app.include_router(data_router)

shared_frontend = os.path.join(os.path.dirname(__file__), "..", "shared", "frontend")
if os.path.isdir(shared_frontend):
    app.mount("/shared", StaticFiles(directory=shared_frontend), name="shared")


@app.get("/_health")
def gateway_health():
    tools_status = {r.name: r.status for r in registry.list_all()}
    return {"status": "ok", "tools": tools_status}


@app.get("/", response_class=HTMLResponse)
def portal():
    tools = registry.list_all()
    tool_cards = ""
    for t in tools:
        status_color = {"running": "#22c55e", "starting": "#f59e0b", "stopped": "#9ca3af", "crashed": "#ef4444"}.get(t.status, "#9ca3af")
        desc = t.manifest.get("description", "")
        tool_cards += f"""
        <a href="{t.route}" class="tool-card">
          <div class="tool-header">
            <span class="tool-name">{t.name}</span>
            <span class="tool-status" style="--status-color:{status_color}">{t.status}</span>
          </div>
          <div class="tool-route">{t.route}</div>
          <div class="tool-desc">{desc}</div>
        </a>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Aether Forge</title>
<link rel="icon" href="/shared/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/shared/styles/base.css">
<style>
  .portal-header {{
    text-align: center; padding: 3rem 1rem 2rem;
    border-bottom: 1px solid var(--forge-border);
    margin-bottom: 2rem;
  }}
  .portal-header h1 {{
    font-size: 2.5rem; color: var(--forge-primary);
    margin-bottom: .5rem;
  }}
  .portal-header p {{
    color: #6b7280; font-size: 1.1rem;
  }}
  .tool-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem; max-width: 960px; margin: 0 auto; padding: 0 1rem 3rem;
  }}
  .tool-card {{
    display: block; padding: 1.25rem;
    background: #fff; border: 1px solid var(--forge-border);
    border-radius: var(--forge-radius); box-shadow: var(--forge-shadow);
    text-decoration: none; color: inherit;
    transition: border-color .15s, box-shadow .15s;
  }}
  .tool-card:hover {{
    border-color: var(--forge-primary);
    box-shadow: 0 2px 8px rgba(79,70,229,.12);
    text-decoration: none;
  }}
  .tool-header {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: .35rem;
  }}
  .tool-name {{ font-weight: 600; font-size: 1.1rem; color: var(--forge-fg); }}
  .tool-status {{
    font-size: .75rem; padding: .15rem .5rem; border-radius: 999px;
    background: color-mix(in srgb, var(--status-color) 15%, transparent);
    color: var(--status-color); font-weight: 500;
  }}
  .tool-route {{
    font-family: var(--forge-mono); font-size: .85rem;
    color: var(--forge-primary); margin-bottom: .35rem;
  }}
  .tool-desc {{ font-size: .9rem; color: #6b7280; }}
  .empty-state {{
    text-align: center; padding: 3rem 1rem; color: #9ca3af;
  }}
  .empty-state code {{
    display: inline-block; margin-top: .5rem; padding: .5rem 1rem;
    background: var(--forge-bg); border-radius: var(--forge-radius);
    font-family: var(--forge-mono); font-size: .9rem;
  }}
</style>
</head>
<body>
<div class="portal-header">
  <h1>Aether Forge</h1>
  <p>{len(tools)} tool(s) running</p>
</div>
<div class="tool-grid">
  {tool_cards if tools else '<div class="empty-state"><p>No tools yet.</p><p>Drop a tool folder into <code>tools/</code> and it appears here automatically.</p></div>'}
</div>
</body>
</html>"""


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_catch_all(request: Request, path: str):
    return await tool_proxy.proxy(request)


def main():
    import uvicorn
    uvicorn.run("gateway.main:app", host=settings.host, port=settings.gateway_port, reload=False)


if __name__ == "__main__":
    main()
