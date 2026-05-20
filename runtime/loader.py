import importlib.util
import json
import os
import sys
from typing import Optional


def load_manifest(tool_path: str) -> Optional[dict]:
    manifest_path = os.path.join(tool_path, "manifest.json")
    if not os.path.isfile(manifest_path):
        return None
    with open(manifest_path) as f:
        return json.load(f)


def load_tool_app(tool_path: str):
    backend = os.path.join(tool_path, "backend", "handler.py")
    if not os.path.isfile(backend):
        return None
    spec = importlib.util.spec_from_file_location("tool_handler", backend)
    module = importlib.util.module_from_spec(spec)
    sys.modules["tool_handler"] = module
    spec.loader.exec_module(module)
    return module.create_app()
