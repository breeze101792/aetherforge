import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def _find_config() -> str | None:
    """Look for aetherforge.toml starting from gateway/ parent, then upward."""
    here = Path(__file__).resolve().parent
    for ancestor in [here.parent] + list(here.parent.parents):
        candidate = ancestor / "aetherforge.toml"
        if candidate.exists():
            return str(candidate)
    return None


def _load_toml(path: str) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


@dataclass
class Settings:
    host: str = "127.0.0.1"
    gateway_port: int = 8000
    tool_port_start: int = 8101
    tool_port_end: int = 8199
    db_path: str = "data/aetherforge.db"
    registry_path: str = "data/registry.json"
    tools_dir: str = "tools"
    health_poll_interval: float = 0.2
    health_timeout: float = 5.0
    max_restart_attempts: int = 3

    @classmethod
    def from_env(cls, config_path: str | None = None) -> "Settings":
        # 1. Load TOML config file
        toml = {}
        path = config_path or _find_config()
        if path is not None:
            toml = _load_toml(path)

        server = toml.get("server", {})
        tools = toml.get("tools", {})
        data = toml.get("data", {})

        # 2. Apply [test] overrides when AETHERFORGE_ENV=test
        env = os.getenv("AETHERFORGE_ENV", "prod")
        if env == "test":
            test_overrides = toml.get("test", {})
            server = {**server, **{k: v for k, v in test_overrides.items() if k in ("port", "host")}}
            data = {**data, **{k: v for k, v in test_overrides.items() if k in ("db_path", "registry_path")}}

        return cls(
            host=os.getenv("AETHERFORGE_HOST", server.get("host", "127.0.0.1")),
            gateway_port=int(os.getenv("GATEWAY_PORT", server.get("port", 8000))),
            tool_port_start=int(os.getenv("TOOL_PORT_START", tools.get("port_start", 8101))),
            tool_port_end=int(os.getenv("TOOL_PORT_END", tools.get("port_end", 8199))),
            db_path=os.getenv("DB_PATH", data.get("db_path", "data/aetherforge.db")),
            registry_path=os.getenv("REGISTRY_PATH", data.get("registry_path", "data/registry.json")),
            tools_dir=os.getenv("TOOLS_DIR", tools.get("dir", "tools")),
        )
