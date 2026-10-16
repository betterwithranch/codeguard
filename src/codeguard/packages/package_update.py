import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from codeguard.config import CONFIG_FILE

_VERSION_TAG = re.compile(r"^refs/tags/(v?(\d+(?:\.\d+)*))$")


@dataclass(frozen=True)
class PackageRef:
    git: str
    ref: str
    start: int
    end: int

    @classmethod
    def from_node(cls, package: Node) -> Self | None:
        git, ref = _value(package, "git"), _value(package, "ref")
        if not isinstance(git, ScalarNode) or not isinstance(ref, ScalarNode):
            return None
        return cls(git.value, ref.value, ref.start_mark.index, ref.end_mark.index)


@dataclass(frozen=True)
class RefUpdate:
    package: PackageRef
    new: str

    def apply(self, text: str) -> str:
        return text[: self.package.start] + self.new + text[self.package.end :]

    def __str__(self) -> str:
        return f"{self.package.git}: {self.package.ref} -> {self.new}"


class RemoteTags:
    def latest_version(self, url: str) -> str | None:
        listing = subprocess.run(
            ["git", "ls-remote", "--tags", "--refs", url],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        versions = [
            (tuple(int(part) for part in match[2].split(".")), match[1])
            for line in listing.splitlines()
            if (match := _VERSION_TAG.match(line.split("\t")[-1]))
        ]
        return max(versions)[1] if versions else None


@dataclass(frozen=True)
class PackageUpdate:
    working_tree: Path
    tags: RemoteTags = field(default_factory=RemoteTags)

    def run(self) -> list[RefUpdate]:
        config_file = self.working_tree / CONFIG_FILE
        if not config_file.is_file():
            return []
        text = config_file.read_text()
        updates = self._updates(_package_refs(text))
        if updates:
            config_file.write_text(_applied(text, updates))
        return updates

    def _updates(self, packages: list[PackageRef]) -> list[RefUpdate]:
        return [
            RefUpdate(package, latest)
            for package in packages
            if (latest := self.tags.latest_version(package.git)) not in (None, package.ref)
        ]


def _package_refs(text: str) -> list[PackageRef]:
    packages = _value(yaml.compose(text), "packages")
    if not isinstance(packages, SequenceNode):
        return []
    found = (PackageRef.from_node(package) for package in packages.value)
    return [package for package in found if package is not None]


def _applied(text: str, updates: list[RefUpdate]) -> str:
    for update in sorted(updates, key=lambda update: update.package.start, reverse=True):
        text = update.apply(text)
    return text


def _value(node: Node | None, key: str) -> Node | None:
    if not isinstance(node, MappingNode):
        return None
    return next((value for name, value in node.value if name.value == key), None)
