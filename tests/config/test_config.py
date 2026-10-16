import pytest
from pydantic import ValidationError

from codeguard.config import Config


def messages(error: pytest.ExceptionInfo[ValidationError]) -> list[str]:
    return [problem["msg"] for problem in error.value.errors()]


def write_skill(tmp_path, name: str = "placement"):
    (tmp_path / name).mkdir()
    (tmp_path / name / "SKILL.md").write_text("# Placement\n")
    return tmp_path / name


class TestConfig:
    def test_relative_skill_is_under_the_working_tree(self, tmp_path):
        skill = write_skill(tmp_path)

        config = Config.model_validate(
            {"bindings": {"placement.yaml": {"skill": "placement", "paths": ["**"]}}},
            context={"working_tree": tmp_path},
        )

        assert config.bindings.root["placement.yaml"].skill == skill

    def test_skill_without_skill_file_is_an_error(self, tmp_path):
        (tmp_path / "placement").mkdir()

        with pytest.raises(ValidationError) as error:
            Config.model_validate(
                {"bindings": {"placement.yaml": {"skill": "placement", "paths": ["**"]}}},
                context={"working_tree": tmp_path},
            )

        assert messages(error) == [f"Value error, {tmp_path}/placement has no SKILL.md"]

    def test_skill_bound_twice_is_an_error(self, tmp_path):
        skill = write_skill(tmp_path)
        binding = {"skill": skill, "paths": ["**"]}

        with pytest.raises(ValidationError) as error:
            Config.model_validate({"bindings": {"a.yaml": binding, "b.yaml": binding}})

        assert messages(error) == [
            f"Value error, skill {skill} is bound more than once: a.yaml, b.yaml"
        ]
