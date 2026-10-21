import json

from codeguard.rule_tests import SCHEMA_FILE, RuleEvalSchema, RuleTestResult

EVAL_DIR = "python/rule-evals"
SCHEMA = f"{EVAL_DIR}/{SCHEMA_FILE}"


class TestRuleEvalSchema:
    def test_ruleset_without_evals_needs_no_schema(self, repo):
        schema = RuleEvalSchema(repo.root, repo.root / "python")

        assert (schema.run(), schema.update_snapshots()) == (RuleTestResult(), RuleTestResult())
        assert not (repo.root / SCHEMA).exists()

    def test_missing_schema_fails(self, repo):
        repo.write(f"{EVAL_DIR}/enum-usage.yaml", "cases: []\n")

        result = RuleEvalSchema(repo.root, repo.root / "python").run()

        assert result == RuleTestResult(
            problems=(f"{SCHEMA}: out of date. Run codeguard test --update-all.",)
        )

    def test_update_writes_the_dataset_schema(self, repo):
        repo.write(f"{EVAL_DIR}/enum-usage.yaml", "cases: []\n")
        schema = RuleEvalSchema(repo.root, repo.root / "python")

        schema.update_snapshots()

        written = json.loads((repo.root / SCHEMA).read_text())
        assert written["$defs"]["Case"]["properties"]["inputs"] == {"$ref": "#/$defs/EditCase"}
        assert schema.run() == RuleTestResult()

    def test_edited_schema_fails(self, repo):
        repo.write(f"{EVAL_DIR}/enum-usage.yaml", "cases: []\n")
        schema = RuleEvalSchema(repo.root, repo.root / "python")
        schema.update_snapshots()
        repo.write(SCHEMA, "{}\n")

        assert schema.run() == RuleTestResult(
            problems=(f"{SCHEMA}: out of date. Run codeguard test --update-all.",)
        )
