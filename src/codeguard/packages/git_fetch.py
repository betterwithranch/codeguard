import hashlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitFetch:
    cache: Path

    def fetch(self, url: str, ref: str) -> Path:
        checkout = self.cache / _digest(f"{url}\0{ref}")
        if checkout.is_dir():
            return checkout
        self.cache.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(dir=self.cache, prefix=".fetch-"))
        try:
            _git(staging, "init", "--quiet")
            _git(staging, "fetch", "--quiet", "--depth", "1", url, ref)
            _git(staging, "checkout", "--quiet", "--detach", "FETCH_HEAD")
            staging.rename(checkout)
        except OSError:
            if not checkout.is_dir():
                raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return checkout


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
