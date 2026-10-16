import factory

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

    skill = factory.SubFactory(MakeSkill)
    paths = ("**",)
    severity = Severity.ERROR
    model = "claude-sonnet-5-5"
