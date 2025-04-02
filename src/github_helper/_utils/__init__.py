"""A util functions."""

from pathlib import Path

import aiofiles
import orjson

from github_helper._gh_service import GHError


async def load_json(path):
    if not Path(path).is_file():
        raise GHError(f"{path} not exist")

    async with aiofiles.open(path) as f:
        file = await f.read()
    return orjson.loads(file)
