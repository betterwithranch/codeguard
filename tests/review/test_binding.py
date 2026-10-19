import pytest
from pydantic import ValidationError

from codeguard.config import (
    BindingConfig,
    BindingsConfig,
    RuleOverride,
    Ruleset,
    RulesetConfig,
    Skip,
)
from codeguard.review import Binding, Bindings, Severity, Skill

SKILL_NAME = "responsibility-placement"


def write_skill(tmp_path, text: str):
    (tmp_path / SKILL_NAME).mkdir()
    (tmp_path / SKILL_NAME / "SKILL.md").write_text(text)
    return tmp_path / SKILL_NAME


def ruleset(tmp_path, skill, name=None, selection=RulesetConfig()) -> Ruleset:
    bindings = BindingsConfig({"placement.yaml": BindingConfig(skill=skill, paths=("**",))})
    return Ruleset(name=name, root=tmp_path, bindings=bindings, selection=selection)


class TestBinding:
    def test_files_matching_its_paths(self, make_binding):
        binding = make_binding(paths=("app/**/*.py",))

        files = binding.files(["app/a.py", "app/models/b.py", "scripts/c.py"])

        assert files == ["app/a.py", "app/models/b.py"]

    def test_files_matching_its_exclude_paths_are_left_out(self, make_binding):
        binding = make_binding(paths=("**/*.py",), exclude_paths=("**/test_*.py",))

        files = binding.files(["app/a.py", "app/test_a.py", "app/b.rb"])

        assert files == ["app/a.py"]

    def test_from_config_has_its_exclude_paths(self, tmp_path, make_binding, make_skill):
        skill = write_skill(tmp_path, make_skill().text)
        config = BindingConfig(skill=skill, paths=("**",), exclude_paths=("tests/**",))

        binding = Binding.from_config(SKILL_NAME, config)

        assert binding == make_binding(exclude_paths=("tests/**",))

    def test_preset_binding_matches_every_file(self, make_binding):
        binding = make_binding()

        files = binding.files(["a.py", "app/b.rb"])

        assert files == ["a.py", "app/b.rb"]

    def test_from_config_builds_its_skill(self, tmp_path, make_binding, make_skill):
        skill = write_skill(tmp_path, make_skill().text)
        config = BindingConfig(skill=skill, paths=("**",), severity=Severity.WARNING)

        binding = Binding.from_config(SKILL_NAME, config)

        assert binding == make_binding(severity=Severity.WARNING)

    def test_from_config_has_its_model(self, tmp_path, make_binding, make_skill):
        skill = write_skill(tmp_path, make_skill().text)
        config = BindingConfig(skill=skill, paths=("**",), model="claude-haiku-5-5")

        binding = Binding.from_config(SKILL_NAME, config)

        assert binding == make_binding(model="claude-haiku-5-5")

    def test_skips_every_change_kind_by_default(self, make_binding):
        assert make_binding().skips == (Skip.RENAMES, Skip.COMMENTS, Skip.IMPORTS)

    def test_disabled_skips_are_left_out(self, tmp_path, make_skill):
        skill = write_skill(tmp_path, make_skill().text)
        config = BindingConfig.model_validate(
            {"skill": skill, "paths": ["**"], "disable_skips": ["renames"]}
        )

        binding = Binding.from_config(SKILL_NAME, config)

        assert binding.skips == (Skip.COMMENTS, Skip.IMPORTS)

    def test_unknown_skip_is_rejected(self, tmp_path, make_skill):
        skill = write_skill(tmp_path, make_skill().text)

        with pytest.raises(ValidationError, match="disable_skips"):
            BindingConfig.model_validate(
                {"skill": skill, "paths": ["**"], "disable_skips": ["names"]}
            )


class TestBindings:
    def test_from_rulesets_builds_each_binding(self, tmp_path, make_binding, make_skill):
        skill = write_skill(tmp_path, make_skill().text)

        bindings = Bindings.from_rulesets([ruleset(tmp_path, skill)])

        assert bindings == (make_binding(),)

    def test_packaged_binding_is_named_by_its_ruleset(self, tmp_path, make_binding, make_skill):
        skill = write_skill(tmp_path, make_skill().text)

        bindings = Bindings.from_rulesets([ruleset(tmp_path, skill, name="example/python")])

        assert bindings == (make_binding(rule=f"example/python/{SKILL_NAME}"),)

    def test_excluded_binding_is_dropped(self, tmp_path, make_skill):
        skill = write_skill(tmp_path, make_skill().text)
        selection = RulesetConfig(exclude=(SKILL_NAME,))

        bindings = Bindings.from_rulesets([ruleset(tmp_path, skill, "example/python", selection)])

        assert bindings == ()

    def test_override_replaces_the_binding_fields(self, tmp_path, make_binding, make_skill):
        skill = write_skill(tmp_path, make_skill().text)
        override = RuleOverride(
            paths=("app/**",), severity=Severity.WARNING, model="claude-haiku-5-5"
        )
        selection = RulesetConfig(rules={SKILL_NAME: override})

        bindings = Bindings.from_rulesets([ruleset(tmp_path, skill, "example/python", selection)])

        assert bindings == (
            make_binding(
                rule=f"example/python/{SKILL_NAME}",
                paths=("app/**",),
                severity=Severity.WARNING,
                model="claude-haiku-5-5",
            ),
        )

    def test_override_replaces_the_excluded_paths(self, tmp_path, make_binding, make_skill):
        skill = write_skill(tmp_path, make_skill().text)
        binding = BindingConfig(skill=skill, paths=("**",), exclude_paths=("tests/**",))
        bindings = BindingsConfig({"placement.yaml": binding})
        selection = RulesetConfig(rules={SKILL_NAME: RuleOverride(exclude_paths=())})
        ruleset = Ruleset(name=None, root=tmp_path, bindings=bindings, selection=selection)

        assert Bindings.from_rulesets([ruleset]) == (make_binding(),)


class TestSkill:
    def test_from_file_drops_the_frontmatter(self, tmp_path, make_skill):
        file = tmp_path / "SKILL.md"
        file.write_text(f"---\nname: {SKILL_NAME}\n---\n{make_skill().text}")

        skill = Skill.from_file(SKILL_NAME, file)

        assert skill == make_skill()
