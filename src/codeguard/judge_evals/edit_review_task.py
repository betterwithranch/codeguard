import tempfile
from dataclasses import dataclass
from pathlib import Path

from codeguard.judge_evals.judge_factory import JudgeFactory
from codeguard.review import Binding, JudgeRequest
from codeguard.rule_tests import EditCase, EditReview, JudgedViolation, Outcome, ScratchRepo
from codeguard.syntax import ChangeClassifier, SyntaxScanner
from codeguard.working_tree import WorkingTree


@dataclass(frozen=True)
class EditReviewTask:
    binding: Binding
    judges: JudgeFactory
    confidence_threshold: float
    scanner: SyntaxScanner

    def __call__(self, inputs: EditCase) -> EditReview:
        if not self.binding.files([inputs.file]):
            return EditReview(outcome=Outcome.SKIPPED)
        with tempfile.TemporaryDirectory() as directory:
            repo = ScratchRepo.init(Path(directory))
            if inputs.before is not None:
                repo.write({inputs.file: inputs.before})
            repo.commit()
            repo.write({inputs.file: inputs.after})
            working_tree = WorkingTree(repo.root)
            classifier = ChangeClassifier(self.scanner, working_tree)
            changed = classifier.classify(working_tree.changed_lines("HEAD"))
            if not self.binding.is_triggered(changed, inputs.file):
                return EditReview(outcome=Outcome.SKIPPED)
            judge = self.judges(repo.root, self.binding.model)
            verdict = judge.judge(JudgeRequest(self.binding.skill, inputs.file))
            parsed = self.scanner.scan_files(repo.root, [inputs.file]).get(inputs.file)
        violations = tuple(
            JudgedViolation(
                line=violation.line,
                confidence=violation.confidence,
                message=violation.message,
                kinds=None if parsed is None else tuple(sorted(parsed.kinds_on(violation.line))),
            )
            for violation in verdict.violations
            if violation.file == inputs.file
        )
        return EditReview(outcome=self._outcome(violations), violations=violations)

    def _outcome(self, violations: tuple[JudgedViolation, ...]) -> Outcome:
        if any(violation.confidence >= self.confidence_threshold for violation in violations):
            return Outcome.INVALID
        return Outcome.UNCERTAIN if violations else Outcome.VALID
