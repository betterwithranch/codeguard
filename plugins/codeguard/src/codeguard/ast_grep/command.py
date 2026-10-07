import subprocess
import sysconfig
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from codeguard.ast_grep.layout import Layout

AST_GREP = Path(sysconfig.get_path("scripts")) / "ast-grep"
NO_ERROR_FINDINGS = 0
ERROR_FINDINGS = 1


@dataclass(frozen=True)
class AstGrepCommand:
    layout: Layout

    def scan(self, files: Sequence[str]) -> str:
        with self._command("scan", "--json=stream", *files) as command:
            result = subprocess.run(
                command, cwd=self.layout.root, capture_output=True, text=True
            )
        if result.returncode not in (NO_ERROR_FINDINGS, ERROR_FINDINGS):
            raise subprocess.CalledProcessError(
                result.returncode, result.args, result.stdout, result.stderr
            )
        return result.stdout

    def test(self) -> bool:
        return self._test()

    def update_snapshots(self) -> bool:
        return self._test("--update-all")

    def _test(self, *options: str) -> bool:
        with self._command("test", *options) as command:
            return subprocess.run(command, cwd=self.layout.root).returncode == 0

    @contextmanager
    def _command(self, subcommand: str, *args: str) -> Iterator[list[str | Path]]:
        with self.layout.config() as config:
            yield [AST_GREP, subcommand, "--config", config, *args]
