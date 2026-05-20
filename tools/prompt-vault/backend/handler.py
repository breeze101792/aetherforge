from fastapi import FastAPI, HTTPException, Request
from shared.backend.data_client import DataClient


def create_app():
    app = FastAPI()
    db = DataClient()

    @app.get("/list")
    def list_prompts(limit: int = 100, offset: int = 0):
        return db.list("prompts", limit=limit, offset=offset)

    @app.get("/get/{prompt_id}")
    def get_prompt(prompt_id: int):
        return db.get("prompts", prompt_id)

    @app.post("/save")
    async def save_prompt(request: Request):
        body = await request.json()
        prompt_id = body.pop("id", None)
        if prompt_id:
            return db.update("prompts", prompt_id, body)
        return db.create("prompts", body)

    @app.delete("/delete/{prompt_id}")
    def delete_prompt(prompt_id: int):
        return db.delete("prompts", prompt_id)

    return app
