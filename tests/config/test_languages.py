import pytest
from general_rule import SKILL_DIR, write_general_rule

from codeguard.config import ConfigError, RulesetLoader, language_of, named_languages
from codeguard.config.languages import covers_language


class TestLanguages:
    @pytest.mark.parametrize(
        ("file", "language"),
        [("orders.py", "python"), ("app/view.tsx", "typescript"), ("README.md", None)],
    )
    def test_a_file_language_is_its_extension(self, file, language):
        assert language_of(file) == language

    def test_paths_name_the_languages_of_their_extensions(self):
        assert named_languages(("src/**/*.py", "**/*.[jt]s", "docs/**")) == {
            "python",
            "javascript",
            "typescript",
        }

    def test_a_pattern_without_an_extension_covers_every_language(self):
        assert covers_language(("src/**",), "ruby")

    def test_a_pattern_with_another_extension_does_not_cover_a_language(self):
        assert not covers_language(("**/*.py",), "typescript")


class TestSupplements:
    def test_a_supplement_named_after_a_covered_language_loads(self, repo):
        write_general_rule(repo)

        (binding,) = RulesetLoader.local(repo.root).load().bindings.root.values()

        assert binding.supplements == {"python": repo.root / SKILL_DIR / "python.md"}

    def test_a_supplement_that_names_no_language_is_an_error(self, repo):
        write_general_rule(repo)
        repo.write(f"{SKILL_DIR}/pyhton.md", "## In Python\n")

        with pytest.raises(ConfigError) as error:
            RulesetLoader.local(repo.root).load()

        assert str(error.value) == (
            f"{repo.root}/.codeguard is invalid:\n"
            f"  bindings.knowledge-stated-once.yaml: Value error, {repo.root}/{SKILL_DIR}/"
            "pyhton.md names no language codeguard knows; a supplement is one of: "
            "javascript.md, python.md, ruby.md, typescript.md"
        )

    def test_a_supplement_for_a_language_the_paths_miss_is_an_error(self, repo):
        write_general_rule(repo, binding='paths: ["**/*.ts"]\ntriggers: [string-literal]\n')

        with pytest.raises(ConfigError) as error:
            RulesetLoader.local(repo.root).load()

        assert str(error.value) == (
            f"{repo.root}/.codeguard is invalid:\n"
            f"  bindings.knowledge-stated-once.yaml: Value error, {repo.root}/{SKILL_DIR}/"
            "python.md is for python, but paths match no python file"
        )
