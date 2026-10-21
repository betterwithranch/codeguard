from dataclasses import dataclass, field
from typing import Protocol

from codeguard.config import ConfigError, Lock, VersionedPackageConfig
from codeguard.packages.remote_tags import RemoteTags


class PackageRefs(Protocol):
    def ref(self, package: VersionedPackageConfig) -> str: ...


@dataclass(frozen=True)
class LatestRefs:
    tags: RemoteTags = field(default_factory=RemoteTags)

    def ref(self, package: VersionedPackageConfig) -> str:
        latest = self.tags.latest(package.git, package.version)
        if latest is None:
            raise ConfigError(f"{package.git} has no version tag in {package.version}")
        return latest


@dataclass(frozen=True)
class LockedRefs:
    lock: Lock
    unlocked: PackageRefs = field(default_factory=LatestRefs)

    def ref(self, package: VersionedPackageConfig) -> str:
        return self.lock.ref(package.git, package.version) or self.unlocked.ref(package)
