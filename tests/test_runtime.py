import json
import os
import shutil
import subprocess
import tempfile
import time

import httpx


def _make_tool(tmpdir: str, name="test-tool", has_handler=True):
    tool = os.path.join(tmpdir, name)
    os.makedirs(os.path.join(tool, "backend"), exist_ok=True)
    os.makedirs(os.path.join(tool, "frontend"), exist_ok=True)

    manifest = {"name": name, "route": f"/{name}", "version": "1.0.0", "description": "test"}
    with open(os.path.join(tool, "manifest.json"), "w") as f:
        json.dump(manifest, f)

    if has_handler:
        with open(os.path.join(tool, "backend", "handler.py"), "w") as f:
            f.write("""
from fastapi import FastAPI
def create_app():
    app = FastAPI()
    @app.get("/ping")
    def ping():
        return {"pong": True}
    @app.post("/echo")
    def echo(data: dict):
        return {"received": data}
    return app
""")

    with open(os.path.join(tool, "frontend", "index.html"), "w") as f:
        f.write("<!DOCTYPE html><html><head><title>Test</title></head><body><h1>Hello Forge</h1></body></html>")

    return tool


def _start_runtime(tool_path, tool_name, port):
    env = {**os.environ, "TOOL_NAME": tool_name, "TOOL_PORT": str(port), "TOOL_PATH": tool_path}
    proc = subprocess.Popen(["python", "-m", "runtime.main"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    return proc


def test_runtime_health():
    tmp = tempfile.mkdtemp()
    try:
        tool = _make_tool(tmp)
        proc = _start_runtime(tool, "test-tool", 8198)
        resp = httpx.get("http://127.0.0.1:8198/_health", timeout=3)
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-tool"
        proc.terminate()
        proc.wait(timeout=3)
    finally:
        shutil.rmtree(tmp)


def test_runtime_api():
    tmp = tempfile.mkdtemp()
    try:
        tool = _make_tool(tmp)
        proc = _start_runtime(tool, "test-tool", 8197)
        resp = httpx.get("http://127.0.0.1:8197/api/ping", timeout=3)
        assert resp.status_code == 200
        assert resp.json() == {"pong": True}

        resp = httpx.post("http://127.0.0.1:8197/api/echo", json={"hello": "world"}, timeout=3)
        assert resp.json() == {"received": {"hello": "world"}}

        proc.terminate()
        proc.wait(timeout=3)
    finally:
        shutil.rmtree(tmp)


def test_runtime_serves_frontend():
    tmp = tempfile.mkdtemp()
    try:
        tool = _make_tool(tmp)
        proc = _start_runtime(tool, "test-tool", 8196)
        resp = httpx.get("http://127.0.0.1:8196/", timeout=3)
        assert resp.status_code == 200
        assert "Hello Forge" in resp.text
        assert "<!DOCTYPE html>" in resp.text
        proc.terminate()
        proc.wait(timeout=3)
    finally:
        shutil.rmtree(tmp)


def test_runtime_tool_info():
    tmp = tempfile.mkdtemp()
    try:
        tool = _make_tool(tmp)
        proc = _start_runtime(tool, "test-tool", 8195)
        resp = httpx.get("http://127.0.0.1:8195/_tool/info", timeout=3)
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-tool"
        assert resp.json()["manifest"]["version"] == "1.0.0"
        proc.terminate()
        proc.wait(timeout=3)
    finally:
        shutil.rmtree(tmp)


def test_runtime_frontend_only_tool():
    tmp = tempfile.mkdtemp()
    try:
        tool = _make_tool(tmp, has_handler=False)
        proc = _start_runtime(tool, "test-tool", 8194)
        resp = httpx.get("http://127.0.0.1:8194/_health", timeout=3)
        assert resp.status_code == 200
        resp = httpx.get("http://127.0.0.1:8194/", timeout=3)
        assert "Hello Forge" in resp.text
        proc.terminate()
        proc.wait(timeout=3)
    finally:
        shutil.rmtree(tmp)
