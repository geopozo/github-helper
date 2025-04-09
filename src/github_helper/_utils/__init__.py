"""A util functions."""

from pathlib import Path

import aiofiles
import orjson


async def load_json(path):
    if not Path(path).is_file():
        raise FileNotFoundError(f"{path} not exist")

    async with aiofiles.open(path) as f:
        file = await f.read()
    return orjson.loads(file)
