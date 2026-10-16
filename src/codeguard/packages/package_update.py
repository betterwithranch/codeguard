from dataclasses import dataclass, field
from pathlib import Path

from codeguard.config import ConfigLoader, Lock, LockedPackage, VersionedPackageConfig
from codeguard.packages.package_refs import LatestRefs
from codeguard.packages.remote_tags import RemoteTags


@dataclass(frozen=True)
class LockUpdate:
    git: str
    old: str | None
    new: str

    def __str__(self) -> str:
        return f"{self.git}: {self.old or 'unlocked'} -> {self.new}"


@dataclass(frozen=True)
class PackageUpdate:
    working_tree: Path
    tags: RemoteTags = field(default_factory=RemoteTags)

    def run(self) -> list[LockUpdate]:
        lock = Lock.load(self.working_tree)
        latest = LatestRefs(self.tags)
        locked = tuple(
            LockedPackage(git=package.git, version=package.version, ref=latest.ref(package))
            for package in ConfigLoader(self.working_tree).load().packages
            if isinstance(package, VersionedPackageConfig)
        )
        updated = Lock(packages=locked)
        if updated != lock:
            updated.write(self.working_tree)
        return [
            LockUpdate(package.git, old, package.ref)
            for package in locked
            if (old := lock.ref(package.git, package.version)) != package.ref
        ]
