"""
Github and Pypi versions can contain multiple files: here are tools.

a) the versions can have multiple projects (separated by name).

b) compiled binary extensions: When writing python (or javascript) extensions
in C, C++, rust, etc, you have to create a separate binary for each
environment you wish to support, and there are several levels.

Here is a list of the environments we check for:

.
|-- Windows
|   |-- x86_64
|   |-- Arm64
|   `-- Win32
|-- Mac
|   |-- Apple ARM
|   |-- Intel
|   `-- Universal (1 binary twice the size, 2 architectures)
`-- Linux
    |-- x86_64
    |   |-- Glibc-2.17
    |   |-- Glibc-2.28
    |   |-- Glibc-2.31
    |   |-- Glibc-2.35
    |   `-- musl
    |-- Arm64
    |   |-- Glibc-2.17
    |   |-- Glibc-2.28
    |   |-- Glibc-2.31
    |   |-- Glibc-2.35
    |   `-- musl
    `-- Arm32
        |-- Glibc-2.17
        |-- Glibc-2.28
        |-- Glibc-2.31
        |-- Glibc-2.35
        `-- musl

On top of that, we have to see what is the minimum python version supported for
each one.
"""

import re
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import NamedTuple

import logistro
import semver
from packaging import utils, version
from packaging.version import Version as V  # noqa: N817 I like my V()

_logger = logistro.getLogger(__name__)


GlibcReference = {
    V("2.17"): "Most compatible.",
    V("2.28"): "Debian 10. Reasonably Compatible >2018",
    V("2.29"): "Transitional Version.",
    V("2.31"): "Ubuntu 20.04",
    V("2.34"): "Ubuntu 22.04",
    V("2.35"): "Ubuntu >22.04.1. 2022+",
    V("2.36"): "New?",
    V("2.38"): "Released Yesterday?",
}
"""
A list of common Glibc versions and what theyare as of 2025-04-19.

What is Glibc? It is GNU's libc, and libc is the most fundamental dependency
of C and C++, it offers most of the operating system's API. Compiled programs
can be compiled with a lower version for compatibility, or a higher version for
speed and features. However, compiling against a higher version will make it
unsupported on older distros where everything is compiled against a lower
version.
"""

GlibcRecommended = (V("2.17"), V("2.28"), V("2.31"), V("2.34"))
"""List of libc versions recommended as of 2025-04-19."""


class CompatibilityMatrix(NamedTuple):
    """
    Compiled python extensions (eg. in c or rust) minimum supported pythons.

    When compiling python extensions, version restrictions come from both
    a) headers and b) ABI (Application Binary Interface, the cousin of API). As
    for a) headers, you can only use a version of python >= the version of the
    headers you used. As for b) ABI, If you do not compile with abi3, it means
    you MUST run the extension against the very specific interpreter you
    compiled against.
    """

    abi3: bool
    python_h: V


class GlibcMatrix(dict[V, CompatibilityMatrix]):
    """Describes python compatibility for each Glibc you compiled against."""


@dataclass
class ArchSet:
    x86: CompatibilityMatrix | GlibcMatrix | None = None
    x86_64: CompatibilityMatrix | GlibcMatrix | None = None
    universal: CompatibilityMatrix | None = None
    arm64: CompatibilityMatrix | GlibcMatrix | None = None
    arm32: CompatibilityMatrix | GlibcMatrix | None = None

    @classmethod
    def for_glibc(cls):
        return cls(
            x86=GlibcMatrix(),
            x86_64=GlibcMatrix(),
            arm64=GlibcMatrix(),
            arm32=GlibcMatrix(),
        )


class ProjectAudit:
    name: str
    files: field(default_factory=list[str])
    languages: field(default_factory=set[str])

    def __init__(self, name):
        self.name = name
        self.files = []


class PyProjectAudit(ProjectAudit):
    pure_python: bool | None = None
    with_sdist: bool = False
    with_bdist: bool = False
    is_compiled: bool = False
    win: ArchSet
    mac: ArchSet
    linux_glibc: ArchSet
    linux_musl: ArchSet

    def __init__(self, name, filename, rest):
        super().__init__(name)
        self.pure_python = None
        self.with_sdist = False
        self.with_bdist = False
        self.is_compiled = False
        self.win = ArchSet()
        self.mac = ArchSet()
        self.linux_glibc = ArchSet.for_glibc()
        self.linux_musl = ArchSet()
        self.add_file(filename, rest)

    def add_file(self, filename, rest):  # noqa: PLR0912, C901 complexity
        if filename.endswith("tar.gz"):
            self.with_sdist = True
            return True
        elif filename.endswith(".whl"):
            (
                version,
                build_tag,
                python_tag,
                abi_tags,
                platform_tags,
            ) = rest
            _logger.debug(f"whl attributes: {rest}")
            self.with_bdist = True
            if python_tag in ("py3", "py2.py3"):
                self.pure_python = True
                self.files.append(filename)
                return True
            else:
                self.pure_python = False
                self.is_compiled = True
                match = re.match(r"cp3(\d+)", python_tag)
                if not match:
                    return False
                py_h = V(f"3.{match.group(1)}")

                if abi_tags != "abi3":
                    return False
                cm = CompatibilityMatrix(abi3=True, python_h=py_h)
                match platform_tags:
                    case "win_amd64":
                        self.win.x86_64 = cm
                    case "win32":
                        self.win.x86 = cm
                    case "win_arm64":
                        self.win.arm64 = cm
                    case p if fnmatch(p, "macosx_*_x86_64"):
                        self.mac.x86_64 = cm
                    case p if fnmatch(p, "macosx_*_arm64"):
                        self.mac.arm64 = cm
                    case p if fnmatch(p, "macosx_*_universal2"):
                        self.mac.universal = cm
                    case p if (m := re.match(r"manylinux(2014|_\d_\d)_(.*)^", p)):
                        if m.group(1) == "2014":
                            v = V("2.17")
                        else:  # process_group
                            v = V(m.group(1)[1:].replace("_", "."))
                        match m.group(2):
                            case "x86_64":
                                self.linux_glibc.x86_64[v] = cm
                            case "aarch64":
                                self.linux_glibc.amd64[v] = cm
                            case "armv71l":
                                self.linux_glibc.amd32[v] = cm
                    case p if (m := re.match(r"musllinux_(\d_\d)_(.*)^", p)):
                        match m.group(2):
                            case "x86_64":
                                self.linux_musl.x86_64 = cm
                            case "aarch64":
                                self.linux_musl.x86 = cm
                            case "armv7l":
                                self.linux_musl.amd64 = cm
        return False

        # identify operating system


class Projects:
    projects: field(default_factory=MutableMapping[str, ProjectAudit])
    unknown_files: field(default_factory=list[str])
    incompliant_files: field(default_factory=list[str])

    def __init__(self):
        self.projects = {}
        self.unknown_files = []
        self.incompliant_files = []

    def add_file(self, filename):
        if filename.endswith((".whl", "tar.gz")):
            try:
                name, *rest = utils.parse_sdist_filename(filename)
                if name not in self.projects:
                    self.projects[name] = PyProjectAudit(name, filename, rest)
                elif not self.projects[name].add_file(filename, rest):
                    self.incompliant_files.append(filename)
            except utils.InvalidSdistFilename:
                self.unknown_files.append(filename)
                return
        elif filename.endswith(".whl"):
            try:
                name, *rest = utils.parse_wheel_filename(filename)
                if name not in self.projects:
                    self.projects[name] = PyProjectAudit(name, filename, rest)
                elif not self.projects[name].add_file(filename, rest):
                    self.incompliant_files.append(filename)
            except utils.InvalidWheelFilename:
                self.incompliant_files.append(filename)
                return
        else:
            self.unknown_files.append(filename)
            return


class ReleaseAudit:
    prerelease_agree: bool
    projects: Projects

    def __init__(self, release):
        self.version = explode_versions(release["tag"])
        if not self.version:
            return
        self.prerelease_agree = self.version["is_prerelease"] == release["prerelease"]
        self.unknown = []
        self.incompliant = []
        self.projects = Projects()
        for file in release["files"]:
            self.projects.add_file(file)

    def __str__(self):
        if not self.prerelease_agree:
            return "prerelease disagreement."
        return ""


def explode_versions(tag):
    v = None
    try:
        v = version.Version(tag)
    except version.InvalidVersion:
        pass
    try:
        v = semver.Version.parse(tag)
    except ValueError:
        pass
    if not v:
        return None
    ret = {
        "major": v.major,
        "minor": v.minor,
        "patch": v.patch if hasattr(v, "patch") else v.micro,
        "pre": v.prerelease if hasattr(v, "prerelese") else v.pre,
        "dev": v.dev if hasattr(v, "dev") else None,
        "post": v.post if hasattr(v, "post") else None,
    }
    ret["is_prerelease"] = (
        v.is_prerelease if hasattr(v, "is_prerelease") else bool(v.pre)
    )
    return ret


def order_versions(versions: list[dict], key: str):
    return sorted(
        versions,
        key=lambda x: version.parse(x[key]),
        reverse=True,
    )


def filter_versions(versions: list[dict], key: str):
    _regex = re.compile(
        r"^" + version.VERSION_PATTERN + r"$",
        re.VERBOSE,
    )
    return {v[key] for v in versions if _regex.match(v[key])}
