import httpx
from starlette.requests import Request
from starlette.responses import Response

from gateway.registry import Registry


class ToolProxy:
    def __init__(self, registry: Registry):
        self.registry = registry
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def proxy(self, request: Request) -> Response:
        path = request.url.path
        tool = self._match_tool(path)
        if tool is None:
            return Response(content="not found", status_code=404)
        if tool.status not in ("running", "starting"):
            return Response(content="tool unavailable", status_code=502)

        prefix = tool.route
        if path == prefix:
            target_path = "/"
        elif path.startswith(prefix + "/"):
            target_path = path[len(prefix):]
        else:
            target_path = path

        target_url = f"http://127.0.0.1:{tool.port}{target_path}"
        if request.url.query:
            q = request.url.query.decode() if isinstance(request.url.query, bytes) else request.url.query
            target_url += f"?{q}"

        body = await request.body()

        headers = {}
        for k, v in request.headers.items():
            if k.lower() not in ("host", "connection", "transfer-encoding"):
                headers[k] = v

        try:
            upstream = await self.client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )
        except httpx.ConnectError:
            return Response(content="tool unreachable", status_code=502)
        except httpx.TimeoutException:
            return Response(content="tool timeout", status_code=504)

        resp_headers = {}
        for k, v in upstream.headers.items():
            if k.lower() not in ("transfer-encoding", "connection"):
                resp_headers[k] = v

        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=resp_headers,
        )

    def _match_tool(self, path: str):
        tools = sorted(self.registry.list_all(), key=lambda t: -len(t.route))
        for tool in tools:
            if path == tool.route or path.startswith(tool.route + "/"):
                return tool
        return None
