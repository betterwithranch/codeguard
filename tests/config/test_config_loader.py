import pytest

from codeguard.config import (
    BindingConfig,
    BindingsConfig,
    Config,
    ConfigError,
    ConfigLoader,
    PathPackageConfig,
    Ruleset,
    RulesetConfig,
    RulesetLoader,
)

CONFIG = ".codeguard/config.yaml"
BINDING = ".codeguard/bindings/placement.yaml"
SKILL = ".claude/skills/responsibility-placement/SKILL.md"


class TestConfigLoader:
    def test_project_without_config_has_the_defaults(self, repo):
        config = ConfigLoader(repo.root).load()

        assert config == Config()

    def test_confidence_threshold_defaults_to_0_9(self, repo):
        assert ConfigLoader(repo.root).load().confidence_threshold == 0.9

    def test_loads_the_confidence_threshold(self, repo):
        repo.write(CONFIG, "confidence_threshold: 0.75\n")

        assert ConfigLoader(repo.root).load().confidence_threshold == 0.75

    def test_confidence_threshold_above_1_is_an_error(self, repo):
        repo.write(CONFIG, "confidence_threshold: 1.5\n")

        with pytest.raises(ConfigError) as error:
            ConfigLoader(repo.root).load()

        assert str(error.value) == (
            f"{repo.root}/.codeguard is invalid:\n"
            "  confidence_threshold: Input should be less than or equal to 1"
        )

    def test_loads_a_path_package(self, repo):
        repo.write("rules/codeguard-package.yaml", "name: example\nrulesets: [python]\n")
        repo.write(
            CONFIG,
            "packages:\n"
            "  - kind: path\n"
            "    path: rules\n"
            "    rulesets:\n"
            "      python:\n"
            "        exclude: [no-print]\n",
        )

        config = ConfigLoader(repo.root).load()

        assert config.packages == (
            PathPackageConfig(
                path=repo.root / "rules",
                rulesets={"python": RulesetConfig(exclude=("no-print",))},
            ),
        )

    def test_empty_config_file_is_an_error(self, repo):
        repo.write(CONFIG, "")

        with pytest.raises(ConfigError) as error:
            ConfigLoader(repo.root).load()

        assert str(error.value) == (
            f"{repo.root}/.codeguard is invalid:\n"
            "  Input should be a valid dictionary or instance of Config"
        )


class TestRulesetLoader:
    def test_local_ruleset_loads_bindings_by_file(self, repo, make_skill):
        repo.write(SKILL, make_skill().text)
        repo.write(
            ".codeguard/bindings/python/placement.yaml",
            "skill: .claude/skills/responsibility-placement\n"
            "paths: [app/**/*.py]\nseverity: warning\n",
        )

        ruleset = RulesetLoader.local(repo.root).load()

        assert ruleset == Ruleset(
            name=None,
            root=repo.root / ".codeguard",
            bindings=BindingsConfig(
                {
                    "python/placement.yaml": BindingConfig(
                        skill=repo.root / ".claude/skills/responsibility-placement",
                        paths=("app/**/*.py",),
                        severity="warning",
                    )
                }
            ),
        )

    def test_binding_model_defaults_to_sonnet(self, repo, make_skill):
        repo.write(SKILL, make_skill().text)
        repo.write(BINDING, 'skill: .claude/skills/responsibility-placement\npaths: ["**"]\n')

        ruleset = RulesetLoader.local(repo.root).load()

        assert ruleset.bindings.root["placement.yaml"].model == "claude-sonnet-5-5"

    def test_loads_the_binding_model(self, repo, make_skill):
        repo.write(SKILL, make_skill().text)
        repo.write(
            BINDING,
            'skill: .claude/skills/responsibility-placement\npaths: ["**"]\n'
            "model: claude-haiku-5-5\n",
        )

        ruleset = RulesetLoader.local(repo.root).load()

        assert ruleset.bindings.root["placement.yaml"].model == "claude-haiku-5-5"

    def test_project_without_bindings_has_none(self, repo):
        ruleset = RulesetLoader.local(repo.root).load()

        assert ruleset.bindings == BindingsConfig({})

    def test_package_skill_is_under_the_package(self, tmp_path, make_skill):
        (tmp_path / "python/skills/placement").mkdir(parents=True)
        (tmp_path / "python/skills/placement/SKILL.md").write_text(make_skill().text)
        (tmp_path / "python/bindings").mkdir()
        (tmp_path / "python/bindings/placement.yaml").write_text(
            'skill: python/skills/placement\npaths: ["**"]\n'
        )

        ruleset = RulesetLoader(repo=tmp_path, root=tmp_path / "python").load()

        assert ruleset == Ruleset(
            name=None,
            root=tmp_path / "python",
            bindings=BindingsConfig(
                {
                    "placement.yaml": BindingConfig(
                        skill=tmp_path / "python/skills/placement", paths=("**",)
                    )
                }
            ),
        )

    def test_errors_name_the_binding_file(self, repo, make_skill):
        repo.write(SKILL, make_skill().text)
        repo.write(
            BINDING,
            'skill: .claude/skills/responsibility-placement\npath: ["**"]\nseverity: fatal\n',
        )

        with pytest.raises(ConfigError) as error:
            RulesetLoader.local(repo.root).load()

        assert str(error.value) == (
            f"{repo.root}/.codeguard is invalid:\n"
            "  bindings.placement.yaml.paths: Field required\n"
            "  bindings.placement.yaml.severity: "
            "Input should be 'error', 'warning', 'info' or 'hint'\n"
            "  bindings.placement.yaml.path: Extra inputs are not permitted"
        )

    def test_missing_skill_is_an_error(self, repo):
        repo.write(BINDING, 'skill: .claude/skills/responsibility-placement\npaths: ["**"]\n')

        with pytest.raises(ConfigError) as error:
            RulesetLoader.local(repo.root).load()

        assert str(error.value) == (
            f"{repo.root}/.codeguard is invalid:\n"
            "  bindings.placement.yaml.skill: Path does not point to a directory"
        )
