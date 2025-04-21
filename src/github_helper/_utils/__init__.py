"""A util functions."""

import json
from pathlib import Path

import aiofiles
import logistro
import orjson

_logger = logistro.getLogger(__name__)


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
        _logger.debug2(o)
        if hasattr(o, "__json__"):
            return o.__json__()  # manual call here
        return super().default(o)
