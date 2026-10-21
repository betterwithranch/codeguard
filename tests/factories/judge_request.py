import factory

from codeguard.review import JudgeRequest
from factories.skill import MakeSkill


class MakeJudgeRequest(factory.Factory):
    class Meta:
        model = JudgeRequest

    skill = factory.SubFactory(MakeSkill)
    file = "a.py"
    content = "print(1)\n"
