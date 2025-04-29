"""For a unified version framework."""

import re
import sys
import warnings
from dataclasses import dataclass
from enum import StrEnum
from functools import total_ordering

import logistro
import semver
from colored import Fore, Style
from packaging import version as pyversion

_logger = logistro.getLogger(__name__)

if not sys.stdout.isatty():

    class _NoColor:
        def __getattr__(self, name):
            return ""

    # Override colored's foreground, background, and style
    Fore = Style = _NoColor()  # type: ignore[misc, assignment]


@dataclass(frozen=True, slots=True)
class BadVersion:
    """A weak parser that looks for instances where someone tried to tag."""

    _tag_part_re = re.compile(r"^(\d*)(?:\.?(.*))?$")
    tag: str
    major: int
    minor: int
    micro: int
    pre: None = None
    local: str | None = None
    is_prerelease: bool = False

    def __init__(self, tag: str):
        """Look for tag-like structures that parsers won't return."""
        object.__setattr__(self, "tag", tag)
        object.__setattr__(self, "major", 0)
        object.__setattr__(self, "minor", 0)
        object.__setattr__(self, "micro", 0)
        object.__setattr__(self, "pre", None)
        object.__setattr__(self, "local", None)
        object.__setattr__(self, "is_prerelease", False)
        tag = tag.removeprefix("v")
        major_match = self._tag_part_re.search(tag)
        if not major_match or not major_match.group(1):
            raise ValueError
        # else
        object.__setattr__(self, "major", int(major_match.group(1)))
        if not major_match.group(2):
            return
        # else
        minor_match = self._tag_part_re.search(major_match.group(2))
        if not minor_match or not minor_match.group(1):
            object.__setattr__(self, "local", major_match.group(2))
            return
        # else
        object.__setattr__(self, "minor", int(minor_match.group(1)))
        if not minor_match.group(2):
            return
        # else
        micro_match = self._tag_part_re.search(minor_match.group(2))
        if not micro_match or not micro_match.group(1):
            object.__setattr__(self, "local", minor_match.group(2))
            return
        # else
        object.__setattr__(self, "micro", int(micro_match.group(1)))
        object.__setattr__(self, "local", micro_match.group(2) or None)


_VersionTypes = semver.Version | pyversion.Version | BadVersion


@total_ordering
@dataclass(frozen=True, slots=True)
class Version:
    """A unified version class. Most similar to Python, not SemVer."""

    class Type(StrEnum):
        """The possible types of version formats."""

        PYTHON = "Python"
        SEMVER = "SemVer"
        MALFORMED_PY = "Malformed Python"
        MALFORMED = f"{Fore.red}Malformed{Style.reset}"
        UNPARSABLE = f"{Fore.red}Unparsable{Style.reset}"

    tag: str
    valid: bool
    kind: Type
    major: int
    minor: int
    micro: int
    pre: tuple[str, int] | None
    dev: int | None
    post: int | None
    local: str | None
    is_prerelease: bool
    _parsed: _VersionTypes

    def __init__(self, tag: str, *, raise_parse_exc: bool = False):
        """Convert a tag into a Version object, collecting info."""
        if not isinstance(tag, str):
            raise TypeError("tag argument must be string.")
        object.__setattr__(self, "tag", tag)
        parsed_v, kind = self._test_parsers(rpe=raise_parse_exc)
        object.__setattr__(self, "kind", kind)
        if not parsed_v:
            object.__setattr__(self, "valid", False)
            return
        object.__setattr__(self, "valid", True)
        self._enumerate_version(parsed_v)

    def _test_parsers(  # noqa: C901
        self,
        *,
        rpe: bool = False,
    ) -> tuple[_VersionTypes | None, Type | None]:
        """See which parsers handle the tag."""
        tag = self.tag
        try:
            parsed: _VersionTypes = pyversion.Version(tag)

            if str(parsed) != tag.removeprefix("v"):
                old_parsed = parsed
                try:
                    parsed = semver.Version.parse(tag)
                except ValueError:
                    return old_parsed, Version.Type.MALFORMED_PY
                else:
                    return parsed, Version.Type.PYTHON
        except Exception:
            if rpe:
                raise
        else:
            return parsed, Version.Type.PYTHON
        try:
            parsed = semver.Version.parse(tag)
        except Exception:
            if rpe:
                raise
        else:
            return parsed, Version.Type.SEMVER
        try:
            parsed = BadVersion(tag)
        except ValueError:
            pass
        else:
            return parsed, Version.Type.MALFORMED
        return None, Version.Type.UNPARSABLE

    def _enumerate_version(self, v: _VersionTypes) -> None:
        """Break tag attributes into unified attributes."""
        if hasattr(v, "epoch") and v.epoch:
            raise NotImplementedError(
                "Not working with versions with epochs, but would be easy tbh.",
            )
        object.__setattr__(self, "_parsed", v)
        object.__setattr__(self, "major", v.major)
        object.__setattr__(self, "minor", v.minor)
        object.__setattr__(
            self,
            "micro",
            v.micro if hasattr(v, "micro") else v.patch,
        )
        if hasattr(v, "prerelease"):
            if not v.prerelease:
                pre = None
            else:
                match = re.match(r"([a-zA-Z]+)(?:[.\-]?(\d+))?", v.prerelease)
                if not match:
                    warnings.warn(
                        "Prerelease string parsed but is not valid",
                        stacklevel=1,
                    )
                    pre = (v.prerelease, 0)
                else:
                    label = match.group(1).lower()
                    number = int(match.group(2)) if match.group(2) else 0
                    pre = (label, number)
        else:
            pre = v.pre
        object.__setattr__(
            self,
            "pre",
            pre,
        )
        object.__setattr__(
            self,
            "dev",
            v.dev if hasattr(v, "dev") else None,
        )
        object.__setattr__(
            self,
            "post",
            v.post if hasattr(v, "post") else None,
        )
        object.__setattr__(
            self,
            "local",
            v.local if hasattr(v, "local") else v.build,
        )
        object.__setattr__(
            self,
            "is_prerelease",
            (v.is_prerelease if hasattr(v, "is_prerelease") else bool(v.prerelease)),
        )

    def __str__(self):
        """Print Version as string."""
        return self.__repr__()

    def __repr__(self):
        """Print Version as python-compatible string if possible."""
        if not self.valid:
            return ""
        post = f".post{self.post}" if self.post else ""
        dev = f".dev{self.dev}" if self.dev else ""
        pre = f"{self.pre[0]}{self.pre[1]}" if self.pre else ""
        local = f"+{self.local}" if self.local else ""
        return f"{self.major}.{self.minor}.{self.micro}{pre}{post}{dev}{local}"

    def _cmp_tuple(self) -> tuple:
        if not self.valid:
            return (float("NaN"),)
        return (
            self.major,
            self.minor,
            self.micro,
            self.pre,
            self.post,
            self.dev,
            self.local,
        )

    # this could def be simplified to tuple comparison
    # but some values would need to be normalized first
    # thx ai
    def _compare(  # noqa: C901, PLR0911, PLR0912
        self,
        other,
    ) -> int:  # intrinsically special NotImplemented accepted as return
        """
        Compare two versions with major, minor, micro, pre, post, dev.

        Returns:
            -1 if self < other
            0 if self == other
            1 if self > other
            NotImplemented if wrong type

        """
        if not self.valid:
            return NotImplemented
        if isinstance(other, _VersionTypes):
            other = Version(str(other))
        elif not isinstance(other, Version):
            return NotImplemented
        # Compare major, minor, micro
        if (c := (self.major - other.major)) != 0:
            return (c > 0) - (c < 0)
        if (c := (self.minor - other.minor)) != 0:
            return (c > 0) - (c < 0)
        if (c := (self.micro - other.micro)) != 0:
            return (c > 0) - (c < 0)

        # Compare pre-releases
        if self.pre is None and other.pre is not None:
            return 1  # final > pre
        if self.pre is not None and other.pre is None:
            return -1  # pre < final
        if self.pre and other.pre:
            if self.pre[0] != other.pre[0]:
                return (self.pre[0] > other.pre[0]) - (self.pre[0] < other.pre[0])
            if self.pre[1] != other.pre[1]:
                return (self.pre[1] > other.pre[1]) - (self.pre[1] < other.pre[1])

        # Compare post-releases (before dev!)
        if self.post is None and other.post is not None:
            return -1  # no post < post
        if self.post is not None and other.post is None:
            return 1  # post > no post
        if self.post and other.post:  # noqa: SIM102 clarity
            if self.post != other.post:
                return (self.post > other.post) - (self.post < other.post)

        # Compare dev-releases (only if same pre/post/final)
        if self.dev is None and other.dev is not None:
            return 1  # no dev > dev
        if self.dev is not None and other.dev is None:
            return -1  # dev < no dev
        if self.dev and other.dev:  # noqa: SIM102 clarity
            if self.dev != other.dev:
                return (self.dev > other.dev) - (self.dev < other.dev)

        # local is not used in official sorting
        # but if we do not provide some arbitrary tie breaking
        # python will sometimes think two versions are equal
        # in some instances (like when physical sorting)
        # and disequal in others (like when looking for keys)
        # so functions like sorted() which do both will break
        # so just sort arbitrarily unless they _really_ _are_ _equal_
        if self.local == other.local:
            return 0
        elif self.local is not None and other.local is None:
            return 1
        else:
            return -1

    def __eq__(self, other) -> bool:
        """Check if equal."""
        c = self._compare(other)
        if c is NotImplemented:
            return NotImplemented
        return c == 0

    def __lt__(self, other) -> bool:
        """Check if less than."""
        c = self._compare(other)
        if c is NotImplemented:
            return NotImplemented
        return c < 0

    def __hash__(self):
        """Return hash based on normalized value."""
        return self._cmp_tuple().__hash__()
