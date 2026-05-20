from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from gateway.proxy import ToolProxy
from gateway.registry import Registry, ToolRecord


def _make_test_app(registry):
    app = FastAPI()
    proxy = ToolProxy(registry)

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def catch_all(request: Request):
        return await proxy.proxy(request)

    return app


def test_proxy_unknown_tool_returns_404():
    registry = Registry()
    app = _make_test_app(registry)
    client = TestClient(app)
    resp = client.get("/nonexistent/foo")
    assert resp.status_code == 404


def test_proxy_dead_tool_returns_502():
    registry = Registry()
    registry.register(ToolRecord(name="dead", route="/dead", port=8888, status="stopped"))
    app = _make_test_app(registry)
    client = TestClient(app)
    resp = client.get("/dead/foo")
    assert resp.status_code == 502


def test_proxy_longest_prefix_match():
    registry = Registry()
    registry.register(ToolRecord(name="app", route="/app", port=8101, status="running"))
    registry.register(ToolRecord(name="app-sub", route="/app/sub", port=8102, status="running"))
    proxy = ToolProxy(registry)
    assert proxy._match_tool("/app/sub/page").name == "app-sub"
    assert proxy._match_tool("/app/page").name == "app"
    assert proxy._match_tool("/app").name == "app"
