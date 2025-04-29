import copy
import re
from dataclasses import dataclass, field
from typing import Literal

import logistro
from colored import Fore, Style
from packaging import tags, utils

from github_helper.api.versions import Version

from ._types import Audit, Error

_logger = logistro.getLogger(__name__)

bdist_template = {
    "Windows": {
        "x86_64": [],
        "arm64": [],
        "win32": [],
    },
    "Mac": {
        "x86_64": {},
        "arm64": {},
        "universal2": {},
    },
    "Linux": {
        "x86_64": {
            "Glibc": {
                "2.17": [],
            },
            "musl": {},
        },
        "aarch64": {
            "Glibc": {
                "2.17": [],
            },
            "musl": {},
        },
        "armv7l": {
            "Glibc": {
                "2.17": [],
            },
            "musl": {},
        },
    },
}

class PythonAudit:
    projects: dict[str, "Project"]
    version: Version

    def __init__(self, v: Version) -> None:
        self.projects: dict[str, Project] = {}
        self.version = v

    def check_file(self, filename) -> Audit | Error | None:
        if filename.endswith("tar.gz"):
            try:
                name, version = utils.parse_sdist_filename(filename)
            except utils.InvalidSdistFilename:
                _logger.debug(f"Invalid Sdist Filename: {filename}")
                return None
            else:
                self.projects.setdefault(name, Project())
                self.projects[name].add_sdist(filename)
                # TODO check version against tag
                return { "name": name, "action": "resolved" }
        elif filename.endswith(".whl"):
            try:
                (
                    name,
                    version,
                    build,
                    tags,
                ) = utils.parse_wheel_filename(filename)
            except utils.InvalidWheelFilename:
                _logger.debug(f"Invalid Wheel Filename: {filename}")
                return {"error": "invalid name", "value": filename}
            else:
                self.projects.setdefault(name, Project())
                self.projects[name].add_bdist(filename, tags)
                # TODO check version against
                return { "name": name, "action": "resolved" }
        return None


@dataclass(slots=True, kw_only=True)
class Project:
    sdist: bool = False
    bdist: bool = False
    weird_version: bool = False
    pure_tags: set[tags.Tag] = field(default_factory=set)
    all_tags: set[tags.Tag] = field(default_factory=set)
    unknown_tags: set[tags.Tag] = field(default_factory=set)
    files: set[str] = field(default_factory=set)
    bdist_tree: dict | None = None

    def add_sdist(self, file: str):
        self.sdist = True
        self.files.add(file)

    def add_bdist(self, file: str, tags: set[tags.Tag] | frozenset[tags.Tag]) -> None:
        self.bdist = True
        self.files.add(file)
        self.all_tags.update(tags)
        for t in tags:
            # t.interpreter, t.abi, t.platform
            pair = f"{t.interpreter}-{t.abi}"
            if t.abi == "none" and t.platform == "any":
                self.pure_tags.add(t)
                continue
        if not self.bdist_tree:
            self.bdist_tree = copy.deepcopy(bdist_template)
        if t.platform == "any":
            x = self.bdist_tree.setdefault("All OS", [])
            x.append(pair)
        elif (mactag := self._parse_mac_platform(t.platform)):
            x = self.bdist_tree["Mac"][mactag.arch].setdefault("version", [])
            x.append(pair)
        elif (arch := self._parse_win_platform(t.platform)):
            self.bdist_tree["Windows"][arch].append(pair)
        elif (linuxtag := self._parse_linux_platform(t.platform)):
            arch_default: dict = { "Glibc": {"2.17": []}, "musl": {} }
            x = self.bdist_tree["Linux"].setdefault(linuxtag.arch, arch_default)
            x[linuxtag.arch].setdefault(linuxtag.version, []).append(pair)
        else:
            self.unknown_tags.add(t)

    @dataclass(slots=True, frozen=True)
    class MacTag:
        version: str
        arch: str
    def _parse_mac_platform(self, tag) -> MacTag | None:
        pattern = r"^macosx_(\d+)(?:_(\d+))?_(.+)$"
        m = re.match(pattern, tag)
        if not m:
            return None

        major = int(m.group(1))
        minor = int(m.group(2) or 0)  # Default minor version to 0 if omitted
        arch = m.group(3)
        return Project.MacTag(version=f"{major!s}.{minor!s}", arch= arch)

    def _parse_win_platform(
            self, tag: str
    ) -> Literal["win32", "x86_64", "arm64"] | None:
        tag = tag.lower()
        if tag == "win32":
            return "win32"
        if tag.startswith("win_"):
            arch = tag.split("_", 1)[1]
            if arch == "amd64":
                return "x86_64"
            elif arch == "arm64":
                return "arm64"
        return None

    @dataclass(frozen=True, slots=True)
    class LinuxTag:
        version: str
        arch: str
        libc: Literal["Glibc", "musl"]

    def _parse_linux_platform(self, tag: str) -> LinuxTag | None:
        libc: Literal["Glibc", "musl"]
        if tag.startswith("manylinux_"):
            libc = "Glibc"
            # PEP 600 perennial tag: manylinux_X_Y_arch
            m = re.match(r"^manylinux_([0-9]+)_([0-9]+)_(.+)$", tag)
            if not m:
                return None
            glibc_major = int(m.group(1))
            glibc_minor = int(m.group(2))
            arch = m.group(3)
            version = f"{glibc_major}.{glibc_minor}"
        elif tag.startswith("manylinux"):
            libc = "Glibc"
            # Legacies: *1_x86_64, *2010_i686, *2014_x86_64, etc.
            m = re.match(r"^manylinux(\d+)_(.+)$", tag)
            if not m:
                return None
            identifier = m.group(1)  # e.g. "1", "2010", "2014"
            arch = m.group(2)
            # Map known legacy identifiers to glibc versions (optional)
            if identifier == "1":
                version = "2.5"
            elif identifier == "2010":
                version = "2.12"
            elif identifier == "2014":
                version = "2.17"
            else:
                return None
        elif (m := re.match(r"^musllinux_([0-9]+)_([0-9]+)_(.+)$", tag)):
            libc = "musl"
            musl_major = int(m.group(1))
            musl_minor = int(m.group(2))
            arch = m.group(3)
            version = f"{musl_major}.{musl_minor}"
        else:
            return None
        return Project.LinuxTag(
            version= version,
            arch = arch,
            libc = libc,
        )
