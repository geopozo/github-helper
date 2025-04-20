"""A util functions."""

import json
import os
import platform
from pathlib import Path

import aiofiles
import orjson


async def load_json(path):
    if not Path(path).is_file():
        raise FileNotFoundError(f"{path} not exist")

    async with aiofiles.open(path) as f:
        file = await f.read()
    return orjson.loads(file)


class ErrorSerializer:
    def __json__(self):
        return f"Error: {self!s}"


class AutoEncoder(json.JSONEncoder):
    def default(self, o):
        if hasattr(o, "__json__"):
            return o.__json__()  # manual call here
        return super().default(o)


def get_cache_dir(app_name: str) -> Path:
    system = platform.system()

    if system == "Windows":
        base = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        path = base / app_name / "Cache"

    elif system == "Darwin":  # macOS
        path = Path.home() / "Library" / "Caches" / app_name

    else:  # Linux/Unix
        base = Path(os.getenv("XDG_CACHE_HOME") or Path.home() / ".cache")
        path = base / app_name

    path.mkdir(parents=True, exist_ok=True)
    return path
