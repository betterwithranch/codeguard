import pytest

from codeguard.judge_evals import IncompatibleEvalsError, check_installed_evals, installed_evals


class TestCheckInstalledEvals:
    def test_installed_version_in_the_required_range_passes(self):
        check_installed_evals()

    def test_installed_version_outside_the_required_range_is_an_error(self, monkeypatch):
        monkeypatch.setattr(installed_evals, "version", lambda _: "3.0.0")

        with pytest.raises(IncompatibleEvalsError) as error:
            check_installed_evals()

        assert str(error.value).startswith(
            "pydantic-evals 3.0.0 is installed; codeguard needs pydantic-evals~="
        )
