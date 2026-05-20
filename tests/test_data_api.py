import os
import shutil
import tempfile

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.data_api import router


def _make_app(db_path: str):
    app = FastAPI()
    app.state.db_path = db_path
    app.include_router(router)
    return app


def test_create_and_read():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test.db")
    try:
        client = TestClient(_make_app(db))
        resp = client.post("/_api/data/tool-a/results", json={"score": 42})
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == 1
        assert data["data"]["score"] == 42
        assert "created_at" in data

        resp = client.get("/_api/data/tool-a/results/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["score"] == 42
    finally:
        shutil.rmtree(tmp)


def test_list_with_pagination():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test.db")
    try:
        client = TestClient(_make_app(db))
        for i in range(10):
            client.post("/_api/data/tool-a/items", json={"n": i})
        resp = client.get("/_api/data/tool-a/items?limit=5&offset=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 5
    finally:
        shutil.rmtree(tmp)


def test_update():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test.db")
    try:
        client = TestClient(_make_app(db))
        resp = client.post("/_api/data/tool-a/config", json={"theme": "dark"})
        created_at = resp.json()["created_at"]

        resp = client.put("/_api/data/tool-a/config/1", json={"theme": "light"})
        assert resp.status_code == 200
        assert resp.json()["data"]["theme"] == "light"
        assert resp.json()["updated_at"] >= created_at
    finally:
        shutil.rmtree(tmp)


def test_delete():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test.db")
    try:
        client = TestClient(_make_app(db))
        client.post("/_api/data/tool-a/temp", json={"x": 1})
        resp = client.delete("/_api/data/tool-a/temp/1")
        assert resp.json()["deleted"] is True
        resp = client.get("/_api/data/tool-a/temp/1")
        assert resp.status_code == 404
    finally:
        shutil.rmtree(tmp)


def test_namespace_isolation():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test.db")
    try:
        client = TestClient(_make_app(db))
        client.post("/_api/data/tool-a/data", json={"owner": "a"})
        client.post("/_api/data/tool-b/data", json={"owner": "b"})

        resp = client.get("/_api/data/tool-a/data")
        assert len(resp.json()) == 1
        assert resp.json()[0]["data"]["owner"] == "a"

        resp = client.get("/_api/data/tool-b/data")
        assert len(resp.json()) == 1
        assert resp.json()[0]["data"]["owner"] == "b"
    finally:
        shutil.rmtree(tmp)


def test_404_on_missing_record():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test.db")
    try:
        client = TestClient(_make_app(db))
        resp = client.get("/_api/data/tool-a/stuff/999")
        assert resp.status_code == 404
    finally:
        shutil.rmtree(tmp)


def test_rejects_invalid_tool_name():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test.db")
    try:
        client = TestClient(_make_app(db))
        resp = client.post("/_api/data/bad%2Fname/data", json={})
        assert resp.status_code >= 400
    finally:
        shutil.rmtree(tmp)
