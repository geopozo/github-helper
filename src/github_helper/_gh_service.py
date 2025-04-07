import asyncio
import subprocess

import logistro

_logger = logistro.getLogger(__name__)


class GHError(RuntimeError):
    """Error type for `gh` CLI tool errors."""


class ScopesError(RuntimeError):
    """Error for when missing necessary scope."""


class ScopesWarning(UserWarning):
    """Warning for when missing optional enhancing scope."""


async def gh_call(*commands, direct=False) -> tuple[int, bytes, bytes]:
    p = await asyncio.create_subprocess_exec(
        *commands,
        stdout=None if direct else subprocess.PIPE,
        stderr=None if direct else subprocess.PIPE,
        limit=10240000,
    )
    retval = await p.wait()
    stdout, stderr = await p.communicate()
    return retval, stdout, stderr


async def gh_api(endpoint: str, *, direct: bool = False) -> tuple[int, bytes, bytes]:
    return await gh_call("gh", "api", endpoint, direct=direct)


async def gh_graphql(query: str) -> tuple[int, bytes, bytes]:
    return await gh_call(
        "gh",
        "api",
        "graphql",
        "--raw-field",
        f"query={query}",
    )
