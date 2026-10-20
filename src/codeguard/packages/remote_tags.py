import re
import subprocess
from dataclasses import dataclass
from typing import Self

from packaging.specifiers import SpecifierSet
from packaging.version import Version

_VERSION_TAG = re.compile(r"^refs/tags/(v?(\d+(?:\.\d+)*))$")


@dataclass(frozen=True, order=True)
class VersionTag:
    version: Version
    name: str

    @classmethod
    def from_ref(cls, ref: str) -> Self | None:
        match = _VERSION_TAG.match(ref)
        return cls(Version(match[2]), match[1]) if match else None


class RemoteTags:
    def latest(self, url: str, version: SpecifierSet) -> str | None:
        matching = [tag for tag in self._tags(url) if version.contains(tag.version)]
        return max(matching).name if matching else None

    def _tags(self, url: str) -> list[VersionTag]:
        listing = subprocess.run(
            ["git", "ls-remote", "--tags", "--refs", url],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        found = (VersionTag.from_ref(line.split("\t")[-1]) for line in listing.splitlines())
        return [tag for tag in found if tag is not None]
