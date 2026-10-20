import sysconfig
from pathlib import Path

import pytest
from packaging.version import Version

from codeguard.ast_grep import AstGrep
from codeguard.config import ConfigError

BUNDLED = Path(sysconfig.get_path("scripts")) / "ast-grep"


class TestAstGrep:
    def test_unpinned_runs_the_bundled_ast_grep(self):
        assert AstGrep().executable == [BUNDLED]

    def test_pinned_runs_that_version_through_uv(self):
        assert AstGrep(Version("0.46.0")).executable == [
            "uv",
            "tool",
            "run",
            "--quiet",
            "--from",
            "ast-grep-cli==0.46.0",
            "ast-grep",
        ]

    def test_version_codeguard_does_not_support_is_an_error(self):
        with pytest.raises(ConfigError) as error:
            AstGrep(Version("0.44.0")).check_supported()

        assert str(error.value) == "codeguard supports ast-grep >=0.45, not 0.44.0"
