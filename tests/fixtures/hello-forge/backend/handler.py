from fastapi import FastAPI, Request
from shared.backend.data_client import DataClient


def create_app():
    app = FastAPI()
    client = DataClient()

    @app.get("/greet")
    def greet(name: str = "Forge"):
        return {"greeting": f"Hello, {name}!"}

    @app.post("/notes")
    async def save_note(request: Request):
        body = await request.json()
        return client.create("notes", body)

    @app.get("/notes")
    def list_notes():
        return client.list("notes")

    return app
