import asyncio
import subprocess
import tempfile
from pathlib import Path

# get file
# get tree
# get graph (can we filter graph)


def _clean_cancel_task(task):
    if task.done():
        if not task.cancelled():
            exc = task.exception()
            return exc if exc else task.result()
        return asyncio.CancelledError
    else:
        task.cancel()
        return asyncio.CancelledError


class GitError(RuntimeError):
    """Error when git commanding."""


class Repo:
    def __init__(self, url, owner, name, path):
        self.url = url
        self.owner = owner
        self.name = name
        self.cloned = False
        self._path = path

    # check git version
    async def _git_(self, *args):
        command = list("git", *args)
        p = await asyncio.create_subprocess_exec(
            *command,
            stderr=subprocess.PIPE,
        )
        retval = await p.wait()
        stdout, stderr = await p.communicate()
        if retval:
            raise GitError(
                f"Command: {args}. Reval: {retval!s}. Stderr: {stderr}.",
            )
        return stdout

    async def update_repo(self):
        if (self._path / ".git").is_dir():
            return await self._fetch_repo()
        else:
            return await self._clone_repo()

    async def _fetch_repo(self):
        _ = await self._git_(
            "git",
            "fetch",
            "--prune",
            "origin",
            r"+refs/*:refs/*",
        )

    async def _clone_repo(self):
        await self._git_(
            "clone",
            "--filter=tree:0",
            "--no-checkout",
            "--mirror",
            "--quiet",
            f"{self.url!s}/{self.owner!s}/{self.name!s}",
            str(self._path / self.owner / self.name),
        )


class RepoFolder:
    _github = "https://www.github.com"

    def __init__(self, *, cache=True, path=None):
        if not cache:
            self._tempdir = tempfile.TemporaryDirectory(
                delete=True,
                ignore_cleanup_errors=True,
            )  # can set path here too, why not
            self._root = Path(self._tempdir.name).resolve()
        else:
            _ = path
            raise NotImplementedError("Caching is not yet implemented.")

        self.repos = {}

    async def add_repo(self, owner, name, url=None):
        # if not cache
        (self._root / owner).mkdir(parents=True, exist_ok=True)

        repo = Repo(url if url else self._github, owner, name)
        if owner not in self.repos:
            self.repos[owner] = {}
        self.repos[owner][name] = repo
        await repo.update_repo()
        return repo

    def __del__(self):
        # if not cache
        tempfile.cleanup()
        del self._tempdir
