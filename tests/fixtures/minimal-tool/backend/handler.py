from fastapi import FastAPI


def create_app():
    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"pong": True}

    @app.post("/echo")
    def echo(data: dict):
        return {"received": data}

    return app
