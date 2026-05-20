import os
from dataclasses import dataclass, field


@dataclass
class Settings:
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
    def from_env(cls) -> "Settings":
        env = os.getenv("AETHERFORGE_ENV", "prod")
        if env == "test":
            defaults = {
                "db_path": "data/test.db",
                "registry_path": "data/test-registry.json",
            }
        else:
            defaults = {}

        return cls(
            gateway_port=int(os.getenv("GATEWAY_PORT", 8000)),
            tool_port_start=int(os.getenv("TOOL_PORT_START", 8101)),
            tool_port_end=int(os.getenv("TOOL_PORT_END", 8199)),
            db_path=os.getenv("DB_PATH", defaults.get("db_path", "data/aetherforge.db")),
            registry_path=os.getenv("REGISTRY_PATH", defaults.get("registry_path", "data/registry.json")),
            tools_dir=os.getenv("TOOLS_DIR", "tools"),
        )
