import pytest

from codeguard.config import Binding, Config, ConfigError, ConfigLoader

CONFIG = ".codeguard/config.yaml"
BINDING = ".codeguard/bindings/placement.yaml"
SKILL = ".claude/skills/responsibility-placement/SKILL.md"
SKILL_TEXT = "# Responsibility placement\n\nA method lives on the type whose data it reads.\n"


class TestLoad:
    def test_binding_holds_its_skill_without_frontmatter(self, repo, make_skill):
        repo.write(CONFIG, "skill_roots: [.claude/skills]\n")
        repo.write(SKILL, f"---\nname: responsibility-placement\n---\n{SKILL_TEXT}")
        repo.write(BINDING, "skill: responsibility-placement\npaths: [app/**/*.py]\n")

        config = ConfigLoader(repo.root).load()

        assert config == Config(bindings=(Binding(skill=make_skill(), paths=("app/**/*.py",)),))

    def test_bindings_load_from_subdirectories(self, repo, make_skill):
        repo.write(CONFIG, "skill_roots: [.claude/skills]\n")
        repo.write(SKILL, SKILL_TEXT)
        repo.write(
            ".codeguard/bindings/python/placement.yaml",
            "skill: responsibility-placement\npaths: [app/**/*.py]\n",
        )

        config = ConfigLoader(repo.root).load()

        assert config == Config(bindings=(Binding(skill=make_skill(), paths=("app/**/*.py",)),))

    def test_project_without_config_has_no_bindings(self, repo):
        config = ConfigLoader(repo.root).load()

        assert config == Config(bindings=())

    def test_skill_in_two_roots_is_an_error(self, repo):
        repo.write(CONFIG, "skill_roots: [.claude/skills, .agents/skills]\n")
        repo.write(SKILL, SKILL_TEXT)
        repo.write(".agents/skills/responsibility-placement/SKILL.md", SKILL_TEXT)
        repo.write(BINDING, 'skill: responsibility-placement\npaths: ["**"]\n')

        with pytest.raises(ConfigError) as error:
            ConfigLoader(repo.root).load()

        assert str(error.value) == (
            f"{repo.root}/{BINDING}: skill responsibility-placement is in more than one "
            f"skill root: {repo.root}/.claude/skills, {repo.root}/.agents/skills"
        )

    def test_skill_in_no_root_is_an_error(self, repo):
        repo.write(CONFIG, "skill_roots: [.claude/skills]\n")
        repo.write(BINDING, 'skill: responsibility-placement\npaths: ["**"]\n')

        with pytest.raises(ConfigError) as error:
            ConfigLoader(repo.root).load()

        assert str(error.value) == (
            f"{repo.root}/{BINDING}: skill responsibility-placement is in no skill root: "
            f"{repo.root}/.claude/skills"
        )

    def test_empty_config_file_is_an_error(self, repo):
        repo.write(CONFIG, "")

        with pytest.raises(ConfigError) as error:
            ConfigLoader(repo.root).load()

        assert str(error.value) == (
            f"{repo.root}/{CONFIG} is invalid:\n"
            "  (file): Input should be a valid dictionary or instance of ConfigSchema"
        )

    def test_binding_with_misspelled_key_is_an_error(self, repo):
        repo.write(BINDING, 'skill: responsibility-placement\npath: ["**"]\n')

        with pytest.raises(ConfigError) as error:
            ConfigLoader(repo.root).load()

        assert str(error.value) == (
            f"{repo.root}/{BINDING} is invalid:\n"
            "  paths: Field required\n"
            "  path: Extra inputs are not permitted"
        )
