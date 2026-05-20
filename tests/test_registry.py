import json
import os
import tempfile
import threading

from gateway.registry import Registry, ToolRecord


def test_register_and_lookup():
    r = Registry()
    r.register(ToolRecord(name="test", route="/test", port=8101, status="running", pid=1234))
    t = r.get("test")
    assert t is not None
    assert t.port == 8101
    assert t.route == "/test"
    assert len(r.list_all()) == 1


def test_get_by_route():
    r = Registry()
    r.register(ToolRecord(name="a", route="/alpha", port=8101, status="running"))
    r.register(ToolRecord(name="b", route="/beta", port=8102, status="running"))
    assert r.get_by_route("/alpha").name == "a"
    assert r.get_by_route("/beta").name == "b"
    assert r.get_by_route("/gamma") is None


def test_unregister():
    r = Registry()
    r.register(ToolRecord(name="test", route="/test", port=8101, status="running"))
    r.unregister("test")
    assert r.get("test") is None
    assert len(r.list_all()) == 0


def test_persistence_roundtrip():
    r = Registry()
    r.register(ToolRecord(name="x", route="/x", port=8101, status="running", pid=42))
    tmp = tempfile.mktemp(suffix=".json")
    try:
        r.save_to_disk(tmp)
        r2 = Registry()
        r2.load_from_disk(tmp)
        t = r2.get("x")
        assert t is not None
        assert t.port == 8101
        assert t.pid == 42
    finally:
        os.unlink(tmp)


def test_thread_safety():
    r = Registry()
    errors = []

    def writer():
        for i in range(100):
            try:
                r.register(ToolRecord(name=f"t{i}", route=f"/t{i}", port=8100 + i, status="running"))
                r.get(f"t{i}")
                r.list_all()
                r.unregister(f"t{i}")
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=writer) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(errors) == 0


def test_load_from_disk_missing_file():
    r = Registry()
    r.load_from_disk("/nonexistent/path.json")
    assert len(r.list_all()) == 0
