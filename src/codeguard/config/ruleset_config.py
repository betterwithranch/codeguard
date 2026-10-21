from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from codeguard.config.binding_config import BindingConfig
from codeguard.config.path_scope import PathScope
from codeguard.config.severity import Severity


class RuleOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    paths: tuple[str, ...] | None = Field(default=None, min_length=1)
    exclude_paths: tuple[str, ...] | None = None
    severity: Severity | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_model(cls, data: object) -> object:
        if isinstance(data, dict) and "model" in data:
            raise ValueError("model: a rule is judged with the model its binding names")
        return data

    def apply(self, binding: BindingConfig) -> BindingConfig:
        scope = self.apply_scope(PathScope(binding.paths, binding.exclude_paths))
        return binding.model_copy(
            update={
                "paths": scope.paths,
                "exclude_paths": scope.exclude_paths,
                "severity": self.severity or binding.severity,
            }
        )

    def apply_scope(self, scope: PathScope) -> PathScope:
        return PathScope(
            paths=self.paths or scope.paths,
            exclude_paths=scope.exclude_paths if self.exclude_paths is None else self.exclude_paths,
        )


class RulesetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    severity: Severity | None = None
    include: tuple[str, ...] | None = None
    exclude: tuple[str, ...] = ()
    rules: dict[str, RuleOverride] = {}

    @model_validator(mode="after")
    def validate_excluded_rules_not_overridden(self) -> Self:
        overridden = [rule for rule in self.exclude if rule in self.rules]
        if overridden:
            raise ValueError(f"excluded rules are also overridden: {', '.join(overridden)}")
        return self

    @model_validator(mode="after")
    def validate_include_or_exclude(self) -> Self:
        if self.include is not None and self.exclude:
            raise ValueError("set include or exclude, not both")
        return self

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return (*(self.include or ()), *self.exclude, *self.rules)

    def excludes(self, rule: str) -> bool:
        if self.include is not None:
            return rule not in self.include
        return rule in self.exclude

    def apply(self, rule: str, binding: BindingConfig) -> BindingConfig:
        override = self.rules.get(rule, RuleOverride())
        if override.severity is None:
            override = override.model_copy(update={"severity": self.severity})
        return override.apply(binding)

    def apply_scope(self, rule: str, scope: PathScope) -> PathScope:
        return self.rules.get(rule, RuleOverride()).apply_scope(scope)
