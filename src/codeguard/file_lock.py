import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    with path.open("a") as file:
        fcntl.flock(file, fcntl.LOCK_EX)
        yield
