import asyncio
import subprocess


async def gh_call(*commands: str, direct: bool = False) -> tuple[int, bytes, bytes]:
    p = await asyncio.create_subprocess_exec(
        *commands,
        stdout=None if direct else subprocess.PIPE,
        stderr=None if direct else subprocess.PIPE,
        limit=102400,
    )
    retval = await p.wait()
    stdout, stderr = await p.communicate()
    return retval, stdout, stderr


async def gh_api(endpoint: str, *, direct: bool = False) -> tuple[int, bytes, bytes]:
    return await gh_call("gh", "api", endpoint, direct=direct)
