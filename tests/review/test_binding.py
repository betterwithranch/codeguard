from codeguard.config import BindingConfig, BindingsConfig
from codeguard.review import Binding, Bindings, Severity, Skill

SKILL_NAME = "responsibility-placement"


def write_skill(tmp_path, text: str):
    (tmp_path / SKILL_NAME).mkdir()
    (tmp_path / SKILL_NAME / "SKILL.md").write_text(text)
    return tmp_path / SKILL_NAME


class TestBinding:
    def test_files_matching_its_paths(self, make_binding):
        binding = make_binding(paths=("app/**/*.py",))

        files = binding.files(["app/a.py", "app/models/b.py", "scripts/c.py"])

        assert files == ["app/a.py", "app/models/b.py"]

    def test_preset_binding_matches_every_file(self, make_binding):
        binding = make_binding()

        files = binding.files(["a.py", "app/b.rb"])

        assert files == ["a.py", "app/b.rb"]

    def test_from_config_builds_its_skill(self, tmp_path, make_binding, make_skill):
        skill = write_skill(tmp_path, make_skill().text)
        config = BindingConfig(skill=skill, paths=("**",), severity="warning")

        binding = Binding.from_config(config)

        assert binding == make_binding(severity=Severity.WARNING)

    def test_from_config_has_its_model(self, tmp_path, make_binding, make_skill):
        skill = write_skill(tmp_path, make_skill().text)
        config = BindingConfig(skill=skill, paths=("**",), model="claude-haiku-5-5")

        binding = Binding.from_config(config)

        assert binding == make_binding(model="claude-haiku-5-5")


class TestBindings:
    def test_from_config_builds_each_binding(self, tmp_path, make_binding, make_skill):
        skill = write_skill(tmp_path, make_skill().text)
        config = BindingsConfig({"placement.yaml": BindingConfig(skill=skill, paths=("**",))})

        bindings = Bindings.from_config(config)

        assert bindings == (make_binding(),)


class TestSkill:
    def test_from_file_drops_the_frontmatter(self, tmp_path, make_skill):
        file = tmp_path / "SKILL.md"
        file.write_text(f"---\nname: {SKILL_NAME}\n---\n{make_skill().text}")

        skill = Skill.from_file(SKILL_NAME, file)

        assert skill == make_skill()
