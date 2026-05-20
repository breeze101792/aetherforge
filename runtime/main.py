import os
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from runtime.loader import load_manifest, load_tool_app


def main():
    tool_name = os.environ["TOOL_NAME"]
    tool_port = int(os.environ["TOOL_PORT"])
    tool_path = os.environ["TOOL_PATH"]

    manifest = load_manifest(tool_path)
    tool_app = load_tool_app(tool_path)

    app = FastAPI(title=tool_name)

    @app.get("/_health")
    def health():
        return {"status": "ok", "name": tool_name}

    @app.get("/_tool/info")
    def tool_info():
        return {"name": tool_name, "manifest": manifest}

    if tool_app is not None:
        app.mount("/api", tool_app)

    frontend_dir = os.path.join(tool_path, "frontend")
    if os.path.isdir(frontend_dir):
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    uvicorn.run(app, host="127.0.0.1", port=tool_port, log_level="warning")


if __name__ == "__main__":
    main()
