from git_repo import GitRepo

NO_PRINT_RULE = (
    "id: no-print\n"
    "language: python\n"
    "severity: error\n"
    "message: Use logging, not print.\n"
    "rule:\n"
    "  pattern: print($$$ARGS)\n"
)
PLACEMENT_SKILL = "# Responsibility placement\n\nA method lives on the type whose data it reads.\n"


def write_package(repo: GitRepo, prefix: str = "") -> None:
    repo.write(f"{prefix}codeguard-package.yaml", "name: example\nrulesets: [python]\n")
    repo.write(f"{prefix}python/rules/pattern/no-print.yml", NO_PRINT_RULE)
    repo.write(
        f"{prefix}python/skills/responsibility-placement/SKILL.md",
        f"---\nname: responsibility-placement\n---\n{PLACEMENT_SKILL}",
    )
    repo.write(
        f"{prefix}python/bindings/responsibility-placement.yaml",
        'skill: python/skills/responsibility-placement\npaths: ["**/*.py"]\ntriggers: [any]\n',
    )
