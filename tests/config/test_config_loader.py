import pytest

from codeguard.config import BindingConfig, Config, ConfigError, ConfigLoader

CONFIG = ".codeguard/config.yaml"
BINDING = ".codeguard/bindings/placement.yaml"
SKILL = ".claude/skills/responsibility-placement/SKILL.md"


class TestConfigLoader:
    def test_loads_bindings_by_file(self, repo, make_skill):
        repo.write(SKILL, make_skill().text)
        repo.write(
            ".codeguard/bindings/python/placement.yaml",
            "skill: .claude/skills/responsibility-placement\n"
            "paths: [app/**/*.py]\nseverity: warning\n",
        )

        config = ConfigLoader(repo.root).load()

        assert config == Config(
            bindings={
                "python/placement.yaml": BindingConfig(
                    skill=repo.root / ".claude/skills/responsibility-placement",
                    paths=("app/**/*.py",),
                    severity="warning",
                )
            },
        )

    def test_project_without_config_has_no_bindings(self, repo):
        config = ConfigLoader(repo.root).load()

        assert config == Config()

    def test_errors_name_the_binding_file(self, repo, make_skill):
        repo.write(SKILL, make_skill().text)
        repo.write(
            BINDING,
            'skill: .claude/skills/responsibility-placement\npath: ["**"]\nseverity: fatal\n',
        )

        with pytest.raises(ConfigError) as error:
            ConfigLoader(repo.root).load()

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
            ConfigLoader(repo.root).load()

        assert str(error.value) == (
            f"{repo.root}/.codeguard is invalid:\n"
            "  bindings.placement.yaml.skill: Path does not point to a directory"
        )

    def test_empty_config_file_is_an_error(self, repo):
        repo.write(CONFIG, "")

        with pytest.raises(ConfigError) as error:
            ConfigLoader(repo.root).load()

        assert str(error.value) == (
            f"{repo.root}/.codeguard is invalid:\n"
            "  Input should be a valid dictionary or instance of Config"
        )
