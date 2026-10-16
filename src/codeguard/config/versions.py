from typing import Annotated

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import BeforeValidator


def _version(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        return Version(value)
    except InvalidVersion as error:
        raise ValueError(str(error)) from error


def _version_range(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        return SpecifierSet(value)
    except InvalidSpecifier as error:
        raise ValueError(str(error)) from error


ExactVersion = Annotated[Version, BeforeValidator(_version)]
VersionRange = Annotated[SpecifierSet, BeforeValidator(_version_range)]
