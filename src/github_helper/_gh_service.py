import asyncio
import subprocess


async def gh_call(*commands, direct=False) -> asyncio.subprocess.Process:
    p = await asyncio.create_subprocess_exec(
        *commands,
        stdout=None if direct else subprocess.PIPE,
        stderr=None if direct else subprocess.PIPE,
        limit=102400,
    )
    retval = await p.wait()
    stdout, stderr = await p.communicate()
    return retval, stdout, stderr


async def gh_api(endpoint: str, *, direct=False):
    return await gh_call("gh", "api", endpoint, direct=direct)