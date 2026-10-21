import factory

from codeguard.config import JudgeModel, JudgeProvider
from codeguard.review import Binding, Severity, Skill


class MakeSkill(factory.Factory):
    class Meta:
        model = Skill

    class Params:
        no_print = factory.Trait(name="no-print", text="# No print\n")

    name = "responsibility-placement"
    text = "# Responsibility placement\n\nA method lives on the type whose data it reads.\n"


class MakeBinding(factory.Factory):
    class Meta:
        model = Binding

    rule = factory.LazyAttribute(lambda binding: binding.skill.name)
    skill = factory.SubFactory(MakeSkill)
    paths = ("**",)
    severity = Severity.ERROR
    model = JudgeModel(provider=JudgeProvider.CLAUDE_CLI, name="claude-sonnet-5-5")
    triggers = frozenset({"any"})
