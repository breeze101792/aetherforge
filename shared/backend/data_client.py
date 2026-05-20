import os
import httpx


class DataClient:
    def __init__(self, gateway_url: str | None = None):
        self.base = (gateway_url or os.environ.get("GATEWAY_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.namespace = os.environ.get("TOOL_NAME", "unknown")

    def _url(self, resource: str, record_id: int | None = None) -> str:
        u = f"{self.base}/_api/data/{self.namespace}/{resource}"
        return f"{u}/{record_id}" if record_id is not None else u

    def create(self, resource: str, data: dict) -> dict:
        resp = httpx.post(self._url(resource), json=data, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def list(self, resource: str, limit=100, offset=0) -> list[dict]:
        resp = httpx.get(self._url(resource), params={"limit": limit, "offset": offset}, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get(self, resource: str, record_id: int) -> dict:
        resp = httpx.get(self._url(resource, record_id), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def update(self, resource: str, record_id: int, data: dict) -> dict:
        resp = httpx.put(self._url(resource, record_id), json=data, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def delete(self, resource: str, record_id: int) -> dict:
        resp = httpx.delete(self._url(resource, record_id), timeout=10)
        resp.raise_for_status()
        return resp.json()
