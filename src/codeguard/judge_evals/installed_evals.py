from importlib.metadata import requires, version

from packaging.requirements import Requirement

_DISTRIBUTION = "codeguard"
_EVALS = "pydantic-evals"


class IncompatibleEvalsError(Exception):
    pass


def check_installed_evals() -> None:
    requirement = next(
        parsed
        for parsed in map(Requirement, requires(_DISTRIBUTION) or ())
        if parsed.name == _EVALS
    )
    installed = version(_EVALS)
    if not requirement.specifier.contains(installed, prereleases=True):
        raise IncompatibleEvalsError(
            f"{_EVALS} {installed} is installed; codeguard needs {_EVALS}{requirement.specifier}. "
            "Reinstall codeguard."
        )
