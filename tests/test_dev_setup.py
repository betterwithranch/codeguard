import os
import subprocess
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def test_puts_this_clones_cli_on_path_and_installs_its_plugin_for_every_project(tmp_path):
    fake_bin, user_bin, calls = tmp_path / "fake-bin", tmp_path / "user-bin", tmp_path / "calls"
    fake_bin.mkdir()
    claude = fake_bin / "claude"
    claude.write_text(f'#!/bin/sh\necho "$*" >> {calls}\n')
    claude.chmod(0o755)

    subprocess.run(
        [PROJECT / "dev-setup.sh"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "XDG_BIN_HOME": str(user_bin),
        },
        check=True,
        capture_output=True,
    )

    assert (user_bin / "codeguard").resolve() == (PROJECT / ".venv/bin/codeguard").resolve()
    assert calls.read_text().splitlines() == [
        f"plugin marketplace add {PROJECT}",
        "plugin install codeguard@codeguard --scope user",
    ]
