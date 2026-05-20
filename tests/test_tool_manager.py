import json
import os
import shutil
import signal
import tempfile
import time

import httpx

from gateway.registry import Registry
from gateway.settings import Settings
from gateway.tool_manager import ToolManager

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "minimal-tool")


def _setup(monkeypatch, tmpdir, tool_copies=None):
    tools_dir = os.path.join(tmpdir, "tools")
    os.makedirs(tools_dir, exist_ok=True)
    if tool_copies:
        for name, src in tool_copies:
            dst = os.path.join(tools_dir, name)
            shutil.copytree(src, dst)
    settings = Settings(tools_dir=tools_dir, health_timeout=5.0)
    registry = Registry()
    manager = ToolManager(registry, settings)
    return manager, settings, tools_dir


def test_discover_finds_tool():
    tmp = tempfile.mkdtemp()
    try:
        manager, _, _ = _setup(None, tmp, [("minimal-tool", FIXTURE)])
        found = manager.discover()
        assert len(found) == 1
        _, manifest = found[0]
        assert manifest["name"] == "minimal-tool"
        assert manifest["route"] == "/minimal"
    finally:
        shutil.rmtree(tmp)


def test_discover_skips_invalid():
    tmp = tempfile.mkdtemp()
    try:
        tools_dir = os.path.join(tmp, "tools")
        os.makedirs(os.path.join(tools_dir, "bad-tool", "backend"), exist_ok=True)
        with open(os.path.join(tools_dir, "bad-tool", "manifest.json"), "w") as f:
            json.dump({"name": "bad"}, f)
        settings = Settings(tools_dir=tools_dir)
        manager = ToolManager(Registry(), settings)
        found = manager.discover()
        assert len(found) == 0
    finally:
        shutil.rmtree(tmp)


def test_spawn_and_stop_tool():
    tmp = tempfile.mkdtemp()
    try:
        manager, settings, _ = _setup(None, tmp, [("minimal-tool", FIXTURE)])
        path, manifest = manager.discover()[0]

        record = manager.spawn_tool(path, manifest)
        assert record.status == "running"
        assert record.port >= settings.tool_port_start

        resp = httpx.get(f"http://127.0.0.1:{record.port}/_health", timeout=3)
        assert resp.status_code == 200

        manager.stop_tool(manifest["name"])
        assert manager.registry.get(manifest["name"]) is None

        try:
            httpx.get(f"http://127.0.0.1:{record.port}/_health", timeout=1)
            assert False, "should not respond after stop"
        except Exception:
            pass
    finally:
        shutil.rmtree(tmp)


def test_find_free_port_skips_used():
    tmp = tempfile.mkdtemp()
    try:
        manager, _, _ = _setup(None, tmp, [("minimal-tool", FIXTURE)])
        path, manifest = manager.discover()[0]
        record = manager.spawn_tool(path, manifest)

        free_port = manager.find_free_port()
        assert free_port != record.port

        manager.stop_tool(manifest["name"])
    finally:
        shutil.rmtree(tmp)


def test_crash_detection():
    tmp = tempfile.mkdtemp()
    try:
        manager, _, _ = _setup(None, tmp, [("minimal-tool", FIXTURE)])
        path, manifest = manager.discover()[0]
        record = manager.spawn_tool(path, manifest)
        assert record.status == "running"

        os.kill(record.pid, signal.SIGKILL)
        time.sleep(0.5)

        try:
            httpx.get(f"http://127.0.0.1:{record.port}/_health", timeout=1)
            assert False, "should be dead"
        except Exception:
            pass

        manager.stop_tool(manifest["name"])
    finally:
        shutil.rmtree(tmp)


def test_hot_add_detection():
    tmp = tempfile.mkdtemp()
    try:
        tools_dir = os.path.join(tmp, "tools")
        os.makedirs(tools_dir)
        settings = Settings(tools_dir=tools_dir, health_timeout=10.0)
        registry = Registry()
        manager = ToolManager(registry, settings)
        manager.watch()
        time.sleep(0.5)

        shutil.copytree(FIXTURE, os.path.join(tools_dir, "minimal-tool"))

        # Poll for tool to be running (watcher debounce + spawn + health check)
        record = None
        for _ in range(30):
            time.sleep(0.5)
            record = registry.get("minimal-tool")
            if record and record.status == "running":
                break

        assert record is not None, "Tool was never registered"
        assert record.status == "running", f"Tool status is {record.status}"

        manager.stop_tool("minimal-tool")
    finally:
        shutil.rmtree(tmp)


def test_hot_remove_detection():
    tmp = tempfile.mkdtemp()
    try:
        tools_dir = os.path.join(tmp, "tools")
        os.makedirs(tools_dir)
        shutil.copytree(FIXTURE, os.path.join(tools_dir, "minimal-tool"))
        settings = Settings(tools_dir=tools_dir, health_timeout=5.0)
        registry = Registry()
        manager = ToolManager(registry, settings)

        path, manifest = manager.discover()[0]
        manager.spawn_tool(path, manifest)
        assert registry.get("minimal-tool") is not None

        manager.watch()
        time.sleep(0.5)

        shutil.rmtree(os.path.join(tools_dir, "minimal-tool"))
        time.sleep(2)

        assert registry.get("minimal-tool") is None
    finally:
        shutil.rmtree(tmp)
