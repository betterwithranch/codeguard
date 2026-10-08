from codeguard.config import Binding, Config
from codeguard.review import Concern


class TestConcerns:
    def test_binding_selects_files_matching_its_paths(self, make_skill):
        config = Config(bindings=(Binding(skill=make_skill(), paths=("app/**/*.py",)),))

        concerns = config.concerns(["app/a.py", "app/models/b.py", "scripts/c.py"])

        assert concerns == [Concern(skill=make_skill(), files=("app/a.py", "app/models/b.py"))]

    def test_preset_binding_selects_every_file(self, make_skill):
        config = Config(bindings=(Binding(skill=make_skill(), paths=("**",)),))

        concerns = config.concerns(["a.py", "app/b.rb"])

        assert concerns == [Concern(skill=make_skill(), files=("a.py", "app/b.rb"))]

    def test_binding_matching_no_file_gives_no_concern(self, make_skill):
        config = Config(bindings=(Binding(skill=make_skill(), paths=("app/**/*.py",)),))

        concerns = config.concerns(["scripts/c.py"])

        assert concerns == []
