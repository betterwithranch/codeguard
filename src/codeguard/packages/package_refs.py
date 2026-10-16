from dataclasses import dataclass, field
from typing import Protocol

from codeguard.config import LOCK_FILE, ConfigError, Lock, VersionedPackageConfig
from codeguard.packages.remote_tags import RemoteTags


class PackageRefs(Protocol):
    def ref(self, package: VersionedPackageConfig) -> str: ...


@dataclass(frozen=True)
class LockedRefs:
    lock: Lock

    def ref(self, package: VersionedPackageConfig) -> str:
        locked = self.lock.ref(package.git, package.version)
        if locked is None:
            raise ConfigError(
                f"{LOCK_FILE} has no ref for {package.git} {package.version}. Run codeguard update."
            )
        return locked


@dataclass(frozen=True)
class LatestRefs:
    tags: RemoteTags = field(default_factory=RemoteTags)

    def ref(self, package: VersionedPackageConfig) -> str:
        latest = self.tags.latest(package.git, package.version)
        if latest is None:
            raise ConfigError(f"{package.git} has no version tag in {package.version}")
        return latest
