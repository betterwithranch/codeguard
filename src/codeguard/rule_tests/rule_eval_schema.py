from dataclasses import dataclass
from pathlib import Path

from pydantic_core import to_json
from pydantic_evals import Dataset

from codeguard.config import JUDGE_EVAL_DIR
from codeguard.rule_tests.rule_eval import EVAL_FILE_GLOB, EditCase, EditReview
from codeguard.rule_tests.rule_test_result import RuleTestResult

SCHEMA_FILE = "rule-eval-schema.json"


@dataclass(frozen=True)
class RuleEvalSchema:
    root: Path
    ruleset: Path

    def run(self) -> RuleTestResult:
        if not self._needed() or self._current():
            return RuleTestResult()
        return RuleTestResult(
            problems=(
                f"{self._path.relative_to(self.root)}: out of date. "
                "Run codeguard test --update-all.",
            )
        )

    def update_snapshots(self) -> RuleTestResult:
        if self._needed() and not self._current():
            self._path.write_text(_schema())
        return RuleTestResult()

    @property
    def _path(self) -> Path:
        return self.ruleset / JUDGE_EVAL_DIR / SCHEMA_FILE

    def _needed(self) -> bool:
        return any((self.ruleset / JUDGE_EVAL_DIR).glob(EVAL_FILE_GLOB))

    def _current(self) -> bool:
        return self._path.is_file() and self._path.read_text() == _schema()


def _schema() -> str:
    # pydantic-evals can't build the schema with None as the metadata type, only NoneType.
    dataset = Dataset[EditCase, EditReview, type(None)]
    return to_json(dataset.model_json_schema_with_evaluators(), indent=2).decode() + "\n"
