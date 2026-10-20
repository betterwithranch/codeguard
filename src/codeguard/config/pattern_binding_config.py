from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator

from codeguard.config.path_scope import PathScope


class PatternBindingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule: str
    paths: tuple[str, ...] = Field(min_length=1)
    exclude_paths: tuple[str, ...] = ()

    @property
    def scope(self) -> PathScope:
        return PathScope(self.paths, self.exclude_paths)


class PatternBindingsConfig(RootModel[dict[str, PatternBindingConfig]]):
    model_config = ConfigDict(frozen=True)

    @field_validator("root")
    @classmethod
    def validate_rules_bound_once(
        cls, bindings: dict[str, PatternBindingConfig]
    ) -> dict[str, PatternBindingConfig]:
        files: defaultdict[str, list[str]] = defaultdict(list)
        for file, binding in bindings.items():
            files[binding.rule].append(file)
        for rule, bound_in in files.items():
            if len(bound_in) > 1:
                raise ValueError(f"rule {rule} is bound more than once: {', '.join(bound_in)}")
        return bindings

    def scope(self, rule: str) -> PathScope:
        return next(
            (binding.scope for binding in self.root.values() if binding.rule == rule),
            PathScope(),
        )
