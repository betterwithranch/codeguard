from pydantic import BaseModel, ConfigDict

type AstGrepRule = dict[str, object]


class GateRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    language: str
    rule: AstGrepRule
