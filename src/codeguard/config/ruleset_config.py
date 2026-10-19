from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from codeguard.config.binding_config import BindingConfig, Severity


class RuleOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    paths: tuple[str, ...] | None = Field(default=None, min_length=1)
    severity: Severity | None = None
    model: str | None = None

    def apply(self, binding: BindingConfig) -> BindingConfig:
        return binding.model_copy(
            update={
                "paths": self.paths or binding.paths,
                "severity": self.severity or binding.severity,
                "model": self.model or binding.model,
            }
        )


class RulesetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    severity: Severity | None = None
    exclude: tuple[str, ...] = ()
    rules: dict[str, RuleOverride] = {}

    @model_validator(mode="after")
    def validate_excluded_rules_not_overridden(self) -> Self:
        overridden = [rule for rule in self.exclude if rule in self.rules]
        if overridden:
            raise ValueError(f"excluded rules are also overridden: {', '.join(overridden)}")
        return self

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return (*self.exclude, *self.rules)

    def excludes(self, rule: str) -> bool:
        return rule in self.exclude

    def apply(self, rule: str, binding: BindingConfig) -> BindingConfig:
        override = self.rules.get(rule, RuleOverride())
        if override.severity is None:
            override = override.model_copy(update={"severity": self.severity})
        return override.apply(binding)
