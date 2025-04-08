import asyncio
import os
import subprocess


class GHError(RuntimeError):
    """Error type for `gh` CLI tool errors."""


class ScopesError(RuntimeError):
    """Error for when missing necessary scope."""


class ScopesWarning(UserWarning):
    """Warning for when missing optional enhancing scope."""


async def gh_call(*commands) -> tuple[int, bytes, bytes]:
    new_env = os.environ.copy()
    new_env.update(CLICOLOR_FORCE="1")
    p = await asyncio.create_subprocess_exec(
        *commands,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        limit=10240000,
        env=new_env,
    )
    retval = await p.wait()
    stdout, stderr = await p.communicate()
    return retval, stdout, stderr


async def gh_api(endpoint: str) -> tuple[int, bytes, bytes]:
    return await gh_call("gh", "api", endpoint)


def check_retval(retval, err, **kwargs):
    if retval != 0:
        raise GHError(f"{err!s}, add'l: {kwargs.items()!s}")
