import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time

import httpx
from watchfiles import watch as fs_watch

from gateway.registry import Registry, ToolRecord
from gateway.settings import Settings


class ToolManager:
    def __init__(self, registry: Registry, settings: Settings):
        self.registry = registry
        self.settings = settings
        self._watcher_thread: threading.Thread | None = None

    def discover(self) -> list[tuple[str, dict]]:
        found = []
        tools_dir = self.settings.tools_dir
        if not os.path.isdir(tools_dir):
            return found
        for name in sorted(os.listdir(tools_dir)):
            tool_path = os.path.join(tools_dir, name)
            manifest_path = os.path.join(tool_path, "manifest.json")
            if os.path.isdir(tool_path) and os.path.isfile(manifest_path):
                try:
                    with open(manifest_path) as f:
                        manifest = json.load(f)
                    if self._validate_manifest(manifest):
                        found.append((tool_path, manifest))
                except (json.JSONDecodeError, OSError):
                    continue
        return found

    def _validate_manifest(self, m: dict) -> bool:
        required = ["name", "route", "version", "description"]
        return all(k in m for k in required) and m["route"].startswith("/")

    def find_free_port(self) -> int:
        for port in range(self.settings.tool_port_start, self.settings.tool_port_end + 1):
            if not self._port_in_use(port):
                return port
        raise RuntimeError("No free ports in configured range")

    def _port_in_use(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return False
            except OSError:
                return True

    def spawn_tool(self, tool_path: str, manifest: dict) -> ToolRecord:
        name = manifest["name"]
        port = self.find_free_port()
        env = {
            **os.environ,
            "TOOL_NAME": name,
            "TOOL_PORT": str(port),
            "TOOL_PATH": os.path.abspath(tool_path),
            "GATEWAY_URL": f"http://127.0.0.1:{self.settings.gateway_port}",
        }
        proc = subprocess.Popen(
            [sys.executable, "-m", "runtime.main"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        record = ToolRecord(
            name=name,
            route=manifest["route"],
            port=port,
            status="starting",
            pid=proc.pid,
            manifest=manifest,
        )
        self.registry.register(record)

        healthy = self._wait_healthy(port)
        if healthy:
            record.status = "running"
            self.registry.register(record)
        else:
            record.status = "crashed"
            self.registry.register(record)
        return record

    def _wait_healthy(self, port: int) -> bool:
        deadline = time.time() + self.settings.health_timeout
        while time.time() < deadline:
            try:
                resp = httpx.get(f"http://127.0.0.1:{port}/_health", timeout=1)
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(self.settings.health_poll_interval)
        return False

    def _process_exists(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def stop_tool(self, name: str):
        record = self.registry.get(name)
        if record is None:
            return
        if record.pid and self._process_exists(record.pid):
            try:
                os.kill(record.pid, signal.SIGTERM)
                for _ in range(10):
                    if not self._process_exists(record.pid):
                        break
                    time.sleep(0.1)
                else:
                    os.kill(record.pid, signal.SIGKILL)
            except OSError:
                pass
        self.registry.unregister(name)

    def restart_tool(self, tool_path: str, manifest: dict):
        self.stop_tool(manifest["name"])
        return self.spawn_tool(tool_path, manifest)

    def watch(self):
        tools_dir = os.path.abspath(self.settings.tools_dir)

        def _watch_loop():
            for changes in fs_watch(tools_dir):
                for change_type, changed_path in changes:
                    try:
                        self._handle_fs_event(change_type, changed_path, tools_dir)
                    except Exception:
                        pass

        self._watcher_thread = threading.Thread(target=_watch_loop, daemon=True, name="tool-watcher")
        self._watcher_thread.start()
        return self._watcher_thread

    def _handle_fs_event(self, change_type, changed_path: str, tools_dir: str):
        # watchfiles returns paths relative to CWD; resolve symlinks (macOS /var)
        real_tools_dir = os.path.realpath(tools_dir)
        abs_path = os.path.realpath(changed_path)
        try:
            rel = os.path.relpath(abs_path, real_tools_dir)
        except ValueError:
            return
        parts = rel.split(os.sep)
        if not parts or parts[0] in (".", ".."):
            return
        tool_name = parts[0]
        tool_path = os.path.join(real_tools_dir, tool_name)
        manifest_path = os.path.join(tool_path, "manifest.json")

        if change_type == 3:  # deleted — tool dir or any file within deleted
            if self.registry.get(tool_name) and not os.path.isdir(tool_path):
                self.stop_tool(tool_name)
            return

        # added (1) or modified (2) — try to spawn or restart
        if not os.path.isfile(manifest_path) or not os.path.isdir(tool_path):
            return

        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
        except Exception:
            return

        if not self._validate_manifest(manifest):
            return

        existing = self.registry.get(manifest["name"])
        if existing is None:
            self.spawn_tool(tool_path, manifest)
        else:
            self.stop_tool(manifest["name"])
            time.sleep(0.3)
            self.spawn_tool(tool_path, manifest)
