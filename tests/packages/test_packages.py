import pytest
from git_repo import GitRepo
from packaging.version import Version
from rules_package import write_package

from codeguard.config import (
    BindingConfig,
    BindingsConfig,
    ConfigError,
    Lock,
    LockedPackage,
    PathPackageConfig,
    RuleOverride,
    Ruleset,
    RulesetConfig,
    VersionedPackageConfig,
)
from codeguard.packages import GitFetch, LatestRefs, LockedRefs, Packages

AST_GREP = Version("0.45.3")


@pytest.fixture
def no_lock() -> LockedRefs:
    return LockedRefs(Lock())


@pytest.fixture
def package(tmp_path_factory: pytest.TempPathFactory) -> GitRepo:
    repo = GitRepo.init(tmp_path_factory.mktemp("package").resolve())
    write_package(repo)
    repo.commit("Add rules")
    return repo


@pytest.fixture
def released(package) -> GitRepo:
    package.git("tag", "v1.0.0")
    package.write("codeguard-package.yaml", "name: renamed\nrulesets: [python]\n")
    package.commit("Rename")
    package.git("tag", "v1.1.0")
    return package


@pytest.fixture
def fetch(tmp_path) -> GitFetch:
    return GitFetch(tmp_path / "cache")


def versioned(package: GitRepo) -> VersionedPackageConfig:
    return VersionedPackageConfig.model_validate(
        {
            "git": package.file_url,
            "version": ">=1,<2",
            "rulesets": {"python": {}},
        }
    )


class TestVersionedPackages:
    def test_locked_ref_is_fetched(self, repo, released, fetch):
        config = versioned(released)
        lock = Lock(
            packages=(LockedPackage(git=released.file_url, version=config.version, ref="v1.0.0"),)
        )

        rulesets = Packages(repo.root, fetch, AST_GREP, LockedRefs(lock)).rulesets([config])

        assert [ruleset.name for ruleset in rulesets] == ["example/python"]

    def test_latest_tag_in_range_is_fetched(self, repo, released, fetch):
        rulesets = Packages(repo.root, fetch, AST_GREP, LatestRefs()).rulesets(
            [versioned(released)]
        )

        assert [ruleset.name for ruleset in rulesets] == ["renamed/python"]

    def test_unlocked_range_is_an_error(self, repo, released, fetch, no_lock):
        with pytest.raises(ConfigError) as error:
            Packages(repo.root, fetch, AST_GREP, no_lock).rulesets([versioned(released)])

        assert str(error.value) == (
            f".codeguard/lock.yaml has no ref for {released.file_url} <2,>=1. Run codeguard update."
        )

    def test_range_without_a_matching_tag_is_an_error(self, repo, package, fetch):
        with pytest.raises(ConfigError) as error:
            Packages(repo.root, fetch, AST_GREP, LatestRefs()).rulesets([versioned(package)])

        assert str(error.value) == f"{package.file_url} has no version tag in <2,>=1"


class TestPackages:
    def test_opted_in_ruleset_is_named_by_package_and_ruleset(self, repo, package, fetch, no_lock):
        config = PathPackageConfig(path=package.root, rulesets={"python": RulesetConfig()})

        rulesets = Packages(repo.root, fetch, AST_GREP, no_lock).rulesets([config])

        skill = package.root / "python/skills/responsibility-placement"
        assert rulesets == (
            Ruleset(
                name="example/python",
                root=package.root / "python",
                bindings=BindingsConfig(
                    {
                        "responsibility-placement.yaml": BindingConfig(
                            skill=skill, paths=("**/*.py",)
                        )
                    }
                ),
            ),
        )

    def test_ruleset_the_package_lacks_is_an_error(self, repo, package, fetch, no_lock):
        config = PathPackageConfig(path=package.root, rulesets={"ruby": RulesetConfig()})

        with pytest.raises(ConfigError) as error:
            Packages(repo.root, fetch, AST_GREP, no_lock).rulesets([config])

        assert str(error.value) == (
            f"{repo.root}/.codeguard is invalid:\n"
            "  packages.0.rulesets: example has no ruleset ruby"
        )

    def test_ast_grep_outside_the_package_range_is_an_error(self, repo, package, fetch, no_lock):
        package.write(
            "codeguard-package.yaml", "name: example\nrulesets: [python]\nast-grep: '>=0.46'\n"
        )
        config = PathPackageConfig(path=package.root, rulesets={"python": RulesetConfig()})

        with pytest.raises(ConfigError) as error:
            Packages(repo.root, fetch, AST_GREP, no_lock).rulesets([config])

        assert str(error.value) == (
            f"{repo.root}/.codeguard is invalid:\n"
            "  packages.0: example supports ast-grep >=0.46, not 0.45.3"
        )

    def test_ast_grep_inside_the_package_range_loads(self, repo, package, fetch, no_lock):
        package.write(
            "codeguard-package.yaml",
            "name: example\nrulesets: [python]\nast-grep: '>=0.45,<0.46'\n",
        )
        config = PathPackageConfig(path=package.root, rulesets={"python": RulesetConfig()})

        rulesets = Packages(repo.root, fetch, AST_GREP, no_lock).rulesets([config])

        assert [ruleset.name for ruleset in rulesets] == ["example/python"]

    def test_unknown_rule_is_an_error(self, repo, package, fetch, no_lock):
        selection = RulesetConfig(
            exclude=("no-prnt",), rules={"no-print": RuleOverride(severity="warning")}
        )
        config = PathPackageConfig(path=package.root, rulesets={"python": selection})

        with pytest.raises(ConfigError) as error:
            Packages(repo.root, fetch, AST_GREP, no_lock).rulesets([config])

        assert str(error.value) == (
            f"{repo.root}/.codeguard is invalid:\n"
            "  packages.0.rulesets.python: unknown rule no-prnt"
        )

    def test_model_on_a_pattern_rule_is_an_error(self, repo, package, fetch, no_lock):
        selection = RulesetConfig(rules={"no-print": RuleOverride(model="claude-haiku-5-5")})
        config = PathPackageConfig(path=package.root, rulesets={"python": selection})

        with pytest.raises(ConfigError) as error:
            Packages(repo.root, fetch, AST_GREP, no_lock).rulesets([config])

        assert str(error.value) == (
            f"{repo.root}/.codeguard is invalid:\n"
            "  packages.0.rulesets.python: rules.no-print.model: a pattern rule has no model"
        )

    def test_directory_without_a_manifest_is_an_error(self, repo, tmp_path, fetch, no_lock):
        config = PathPackageConfig(path=tmp_path, rulesets={"python": RulesetConfig()})

        with pytest.raises(ConfigError) as error:
            Packages(repo.root, fetch, AST_GREP, no_lock).rulesets([config])

        assert str(error.value) == f"{tmp_path} has no codeguard-package.yaml"
