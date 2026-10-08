import factory

from codeguard.review import Concern, Skill


class MakeSkill(factory.Factory):
    class Meta:
        model = Skill

    name = "responsibility-placement"
    text = "# Responsibility placement\n\nA method lives on the type whose data it reads.\n"


class MakeConcern(factory.Factory):
    class Meta:
        model = Concern

    skill = factory.SubFactory(MakeSkill)
    files = ("a.py",)
