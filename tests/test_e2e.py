import json
import os
import shutil
import signal
import subprocess
import time

import httpx
import pytest

GATEWAY_URL = "http://127.0.0.1:8001"
PROJECT = os.path.join(os.path.dirname(__file__), "..")
HELLO_FORGE_TEMPLATE = os.path.join(os.path.dirname(__file__), "fixtures", "hello-forge")


def _clean_tools_dir():
    """Remove test-created tool directories from tools/ (e2e-* prefix only)."""
    tools_dir = os.path.join(PROJECT, "tools")
    if not os.path.isdir(tools_dir):
        return
    for name in os.listdir(tools_dir):
        if name.startswith("e2e-"):
            path = os.path.join(tools_dir, name)
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)



def _start_gateway():
    env = {
        **os.environ,
        "AETHERFORGE_ENV": "test",
        "GATEWAY_PORT": "8001",
    }
    proc = subprocess.Popen(
        ["python", "-m", "gateway.main"],
        cwd=PROJECT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        try:
            r = httpx.get(f"{GATEWAY_URL}/_health", timeout=1)
            if r.status_code == 200:
                return proc
        except Exception:
            time.sleep(0.3)
    proc.kill()
    raise RuntimeError("Gateway did not start")


def _stop_gateway(proc):
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _add_tool(name, route, template=HELLO_FORGE_TEMPLATE):
    """Copy template, patch in a temp location, then move to tools/ atomically."""
    tools_dir = os.path.join(PROJECT, "tools")
    # Prepare in a temp location first to avoid race condition with watcher
    tmp_dst = os.path.join(PROJECT, "data", f".tmp-{name}")
    if os.path.exists(tmp_dst):
        shutil.rmtree(tmp_dst)
    shutil.copytree(template, tmp_dst)

    manifest_path = os.path.join(tmp_dst, "manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    manifest["name"] = name
    manifest["route"] = route
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    app_js = os.path.join(tmp_dst, "frontend", "app.js")
    with open(app_js) as f:
        js = f.read()
    js = js.replace("hello-forge", name)
    js = js.replace("/hello/api", f"{route}/api")
    with open(app_js, "w") as f:
        f.write(js)

    index_html = os.path.join(tmp_dst, "frontend", "index.html")
    with open(index_html) as f:
        html = f.read()
    html = html.replace("/hello/", f"{route}/")
    with open(index_html, "w") as f:
        f.write(html)

    # Move atomically into tools/
    dst = os.path.join(tools_dir, name)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.rename(tmp_dst, dst)
    return dst, manifest


def _remove_original():
    """Remove original hello-forge to avoid auto-spawn conflicts."""
    orig = os.path.join(PROJECT, "tools", "hello-forge")
    if os.path.exists(orig):
        shutil.rmtree(orig)


def _restore_original():
    """No-op since we don't modify the template. The tests copy from template."""
    pass


@pytest.fixture(autouse=True)
def _setup_teardown():
    """Clean up before each test."""
    subprocess.run(["pkill", "-f", "gateway.main"], capture_output=True)
    subprocess.run(["pkill", "-f", "runtime.main"], capture_output=True)
    time.sleep(0.5)
    _clean_tools_dir()
    # Clean test database for fresh state (never touches production db)
    for f in ["test.db", "test-registry.json"]:
        p = os.path.join(PROJECT, "data", f)
        if os.path.exists(p):
            os.remove(p)
    yield
    _clean_tools_dir()
    subprocess.run(["pkill", "-f", "gateway.main"], capture_output=True)
    subprocess.run(["pkill", "-f", "runtime.main"], capture_output=True)


def test_gateway_starts_and_portal_loads():
    proc = _start_gateway()
    try:
        resp = httpx.get(f"{GATEWAY_URL}/_health", timeout=3)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "tools" in data

        resp = httpx.get(f"{GATEWAY_URL}/", timeout=3)
        assert resp.status_code == 200
        assert "aetherforge" in resp.text
        assert "<!DOCTYPE html>" in resp.text
    finally:
        _stop_gateway(proc)


def test_tool_frontend_served_through_gateway():
    proc = _start_gateway()
    try:
        dst, manifest = _add_tool("e2e-frontend", "/e2e-frontend")
        time.sleep(3)

        resp = httpx.get(f"{GATEWAY_URL}/e2e-frontend/", timeout=3)
        assert resp.status_code == 200
        html = resp.text
        assert "<!DOCTYPE html>" in html
        assert "Hello Forge" in html
        assert 'id="greet-btn"' in html
        assert 'id="save-btn"' in html
        assert "forge-modal" in html
        assert '/shared/styles/base.css' in html
        assert '/shared/components/modal.js' in html

        shutil.rmtree(dst)
        time.sleep(2)
    finally:
        _stop_gateway(proc)


def test_tool_api_through_gateway():
    proc = _start_gateway()
    try:
        dst, manifest = _add_tool("e2e-api", "/e2e-api")
        time.sleep(3)

        resp = httpx.get(f"{GATEWAY_URL}/e2e-api/api/greet?name=World", timeout=3)
        assert resp.status_code == 200
        assert resp.json()["greeting"] == "Hello, World!"

        resp = httpx.get(f"{GATEWAY_URL}/e2e-api/api/greet", timeout=3)
        assert resp.status_code == 200
        assert resp.json()["greeting"] == "Hello, Forge!"

        shutil.rmtree(dst)
        time.sleep(2)
    finally:
        _stop_gateway(proc)


def test_data_api_crud():
    proc = _start_gateway()
    try:
        resp = httpx.post(f"{GATEWAY_URL}/_api/data/e2e-test/items", json={"key": "value"}, timeout=3)
        assert resp.status_code == 201
        record = resp.json()
        assert record["data"]["key"] == "value"
        rid = record["id"]

        resp = httpx.get(f"{GATEWAY_URL}/_api/data/e2e-test/items/{rid}", timeout=3)
        assert resp.status_code == 200
        assert resp.json()["data"]["key"] == "value"

        resp = httpx.put(f"{GATEWAY_URL}/_api/data/e2e-test/items/{rid}", json={"key": "new"}, timeout=3)
        assert resp.status_code == 200
        assert resp.json()["data"]["key"] == "new"

        resp = httpx.delete(f"{GATEWAY_URL}/_api/data/e2e-test/items/{rid}", timeout=3)
        assert resp.json()["deleted"] is True

        resp = httpx.get(f"{GATEWAY_URL}/_api/data/e2e-test/items/{rid}", timeout=3)
        assert resp.status_code == 404
    finally:
        _stop_gateway(proc)


def test_tool_persistence_flow():
    proc = _start_gateway()
    try:
        dst, manifest = _add_tool("e2e-persist", "/e2e-persist")
        time.sleep(3)

        resp = httpx.post(f"{GATEWAY_URL}/e2e-persist/api/notes", json={"text": "e2e test note"}, timeout=3)
        assert resp.status_code == 200

        resp = httpx.get(f"{GATEWAY_URL}/_api/data/e2e-persist/notes", timeout=3)
        assert resp.status_code == 200
        notes = resp.json()
        assert len(notes) == 1
        assert notes[0]["data"]["text"] == "e2e test note"

        shutil.rmtree(dst)
        time.sleep(2)
    finally:
        _stop_gateway(proc)


def test_hot_remove_tool():
    proc = _start_gateway()
    try:
        dst, manifest = _add_tool("e2e-remove", "/e2e-remove")
        time.sleep(3)

        assert httpx.get(f"{GATEWAY_URL}/e2e-remove/", timeout=3).status_code == 200

        shutil.rmtree(dst)
        time.sleep(3)

        resp = httpx.get(f"{GATEWAY_URL}/e2e-remove/", timeout=3)
        assert resp.status_code == 404
    finally:
        _stop_gateway(proc)


def test_shared_assets():
    proc = _start_gateway()
    try:
        resp = httpx.get(f"{GATEWAY_URL}/shared/styles/base.css", timeout=3)
        assert resp.status_code == 200
        assert "text/css" in resp.headers.get("content-type", "")

        resp = httpx.get(f"{GATEWAY_URL}/shared/components/modal.js", timeout=3)
        assert resp.status_code == 200

        resp = httpx.get(f"{GATEWAY_URL}/shared/utils/dataClient.js", timeout=3)
        assert resp.status_code == 200
    finally:
        _stop_gateway(proc)


def test_portal_lists_tool():
    proc = _start_gateway()
    try:
        resp = httpx.get(f"{GATEWAY_URL}/", timeout=3)
        # Portal loads; e2e-portal should not yet be listed
        assert "e2e-portal" not in resp.text

        dst, manifest = _add_tool("e2e-portal", "/e2e-portal")
        time.sleep(3)

        resp = httpx.get(f"{GATEWAY_URL}/", timeout=3)
        assert "e2e-portal" in resp.text
        assert "/e2e-portal" in resp.text
        assert "running" in resp.text

        shutil.rmtree(dst)
        time.sleep(2)
    finally:
        _stop_gateway(proc)


def test_gateway_health_tracks_tools():
    proc = _start_gateway()
    try:
        health = httpx.get(f"{GATEWAY_URL}/_health", timeout=3).json()
        initial_count = len(health["tools"])

        dst, manifest = _add_tool("e2e-health", "/e2e-health")
        time.sleep(3)

        health = httpx.get(f"{GATEWAY_URL}/_health", timeout=3).json()
        assert "e2e-health" in health["tools"]
        assert health["tools"]["e2e-health"] == "running"
        assert len(health["tools"]) == initial_count + 1

        shutil.rmtree(dst)
        time.sleep(2)
    finally:
        _stop_gateway(proc)
