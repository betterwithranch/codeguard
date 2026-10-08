import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from codeguard.config.binding import Binding
from codeguard.config.config import Config
from codeguard.review import Skill

CONFIG_FILE = ".codeguard/config.yaml"
BINDING_DIR = ".codeguard/bindings"
SKILL_FILE = "SKILL.md"
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


class ConfigError(Exception):
    pass


class ConfigSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    skill_roots: tuple[str, ...] = ()


class BindingSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    skill: str
    paths: tuple[str, ...] = Field(min_length=1)


@dataclass(frozen=True)
class ConfigLoader:
    root: Path

    def load(self) -> Config:
        config_file = self.root / CONFIG_FILE
        config = _parse(ConfigSchema, config_file) if config_file.is_file() else ConfigSchema()
        binding_files = sorted((self.root / BINDING_DIR).rglob("*.yaml"))
        return Config(
            bindings=tuple(self._binding(path, config.skill_roots) for path in binding_files)
        )

    def _binding(self, path: Path, skill_roots: tuple[str, ...]) -> Binding:
        binding = _parse(BindingSchema, path)
        return Binding(skill=self._skill(path, binding.skill, skill_roots), paths=binding.paths)

    def _skill(self, binding_path: Path, name: str, skill_roots: tuple[str, ...]) -> Skill:
        roots = [self.root / skill_root for skill_root in skill_roots]
        found = [path for root in roots if (path := root / name / SKILL_FILE).is_file()]
        if len(found) != 1:
            where = "no skill root" if not found else "more than one skill root"
            listed = ", ".join(str(root) for root in roots)
            raise ConfigError(f"{binding_path}: skill {name} is in {where}: {listed}")
        return Skill(name=name, text=FRONTMATTER.sub("", found[0].read_text(), count=1))


def _parse[Model: BaseModel](model: type[Model], path: Path) -> Model:
    try:
        return model.model_validate(yaml.safe_load(path.read_text()))
    except ValidationError as error:
        problems = "".join(
            f"\n  {'.'.join(str(part) for part in problem['loc']) or '(file)'}: {problem['msg']}"
            for problem in error.errors(include_url=False)
        )
        raise ConfigError(f"{path} is invalid:{problems}") from error
