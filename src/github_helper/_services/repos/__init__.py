"""Repo service allow manage repositories."""

import asyncio
import atexit
import fnmatch
import os
import subprocess
import tempfile
from pathlib import Path

import logistro

from github_helper import _utils as ghu
from github_helper._services.file import github as ghf

_logger = logistro.getLogger(__name__)


class GitError(RuntimeError):
    """Error when git commanding."""


def _clean_cancel_task(task):
    if task.done():
        if not task.cancelled():
            exc = task.exception()
            return exc if exc else task.result()
        return asyncio.CancelledError
    else:
        task.cancel()
        return asyncio.CancelledError


# no sé que have cuando hay dos remotos
# y sí lo usamos para locales, se cambia
# el comportamiento
class Repo:
    """Provides functions for manage repositories."""

    def __init__(
        self,
        url,
        owner,
        name,
        path,
        *,
        working=False,
    ):
        """Initializize a new Repo with arguments."""
        self.url = url
        self.owner = owner
        self.name = name
        self.working = working
        # this should change how update clones TODO
        self._path = path / self.owner / self.name

    # check git version
    async def _git_(self, *args, repo=True):
        myself = ["-C", self._path] if repo else []
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        p = await asyncio.create_subprocess_exec(
            "git",
            *myself,
            *args,
            env=env,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        stdout, stderr = await p.communicate()
        retval = await p.wait()
        if retval:
            raise GitError(
                f"git {myself} {args}. Retval: {retval!s}. Stderr: {stderr}.",
            )
        return stdout

    async def list_branches(self):
        """Return the list of branches."""
        cli = [
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/heads",
            "refs/remotes",
        ]
        branches = await self._git_(*cli)
        return branches.decode().split("\n")

    async def list_tags(self):
        """Return the list of tags."""
        return (await self._git_("tag", "-l", "--sort=-v:refname")).decode().split("\n")

    async def describe(self, ref):
        """Return the version tag as given by git describe."""
        has_tags = await self._git_("tag")
        flag = "--tags" if has_tags else "--all"
        if not self.working:
            return (await self._git_("describe", flag, ref)).decode().split("\n")[0]
        else:
            return (
                (await self._git_("describe", flag, "--dirty")).decode().split("\n")[0]
            )

    async def get_working_tree(self, ref):
        """Return a complete list of files with their paths."""
        return (
            (await self._git_("ls-tree", "-r", "--name-only", ref)).decode().split("\n")
        )

    async def get_files_by_name(self, name, ref):
        """Get all files that match a certain name."""
        tree = await self.get_working_tree(ref)

        async def query(file):
            return {"path": file, "content": await self.get_file(file, ref)}

        tasks = {
            asyncio.create_task(query(file), name=file)
            for file in tree
            if fnmatch.fnmatch(file.split("/")[-1], name)
        }
        if not tasks:
            return None
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def get_file(self, path, ref):
        """Return a byte string of file contents."""
        if "github" in self.url:
            return await ghf.get_file(self.owner, self.name, path, ref)
        else:
            raise NotImplementedError(
                "Non-github git archive file retrieval not yet implemented",
            )

    async def get_files(self, *paths, ref):
        """Return a list of byte string file contents."""
        raise NotImplementedError("multiple file get not yet implemented")

    async def update_repo(self):
        """Return an updated repository."""
        if (self._path).is_dir():
            return await self._fetch_repo()
        else:
            return await self._clone_repo()

    async def _fetch_repo(self):
        _ = await self._git_(
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
            str(self._path),
            repo=False,
        )


class RepoFolder:
    """Provides functions for manage repositories."""

    _github = "ssh://git@github.com"

    def __init__(self, *, cache=True, path=None):
        """Initializize a new RepoFolder with arguments."""
        if cache and path:
            raise ValueError("Use either cache or path or neither.")
        if cache:
            self._root = ghu.get_cache_dir()
        elif path:
            self._root = path
        else:
            self._tempdir = tempfile.TemporaryDirectory(
                delete=True,
                ignore_cleanup_errors=True,
            )  # can set path here too, why not
            atexit.register(self._tempdir.cleanup)
            self._root = Path(self._tempdir.name).resolve()

        self.repos = {}

    async def add_repo(self, owner, name, url=None):
        """Return initialized repo instance."""
        # if not cache
        path = self._root / owner
        path.mkdir(parents=True, exist_ok=True)

        repo = Repo(
            url if url else self._github,
            owner,
            name,
            self._root,
        )
        if owner not in self.repos:
            self.repos[owner] = {}
        self.repos[owner][name] = repo
        await repo.update_repo()
        return repo

    def __del__(self):
        """Clean up temp files."""
        # if not cache
        if hasattr(self, "_tempdir") and self._tempdir:
            self._tempdir.cleanup()
            del self._tempdir
