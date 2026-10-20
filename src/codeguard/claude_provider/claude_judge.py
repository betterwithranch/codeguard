import json
import subprocess
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path

import logfire

from codeguard.claude_provider.claude_result import ClaudeResult
from codeguard.claude_provider.prompt_cache_warmup import PromptCacheWarmup
from codeguard.review import Deadline, JudgeError, JudgeRequest, Verdict

_EXECUTABLE = "claude"
_READ_ONLY_TOOLS = "Read,Grep,Glob"
_VERDICT_SCHEMA = json.dumps(Verdict.model_json_schema())


@dataclass(frozen=True)
class ClaudeJudge:
    root: Path
    model: str
    processes: AbstractContextManager[object]
    executable: str = _EXECUTABLE
    warmup: PromptCacheWarmup = field(default_factory=PromptCacheWarmup)
    deadline: Deadline | None = None

    @property
    def identity(self) -> str:
        return "\0".join((_EXECUTABLE, self.model))

    def judge(self, request: JudgeRequest) -> Verdict:
        with logfire.span(
            "claude judges {rule} on {file}",
            rule=request.skill.name,
            file=request.file,
            model=self.model,
        ) as span:
            instructions = request.instructions((self.root / request.file).read_text())
            with self.warmup.after_first_call((self.model, instructions)), self.processes:
                process = self._run(instructions, request.prompt)
            span.set_attribute("returncode", process.returncode)
            if process.returncode != 0:
                raise JudgeError(
                    f"{self.executable} exited with {process.returncode}.\n"
                    f"stdout:\n{process.stdout}\nstderr:\n{process.stderr}"
                )
            result = ClaudeResult.from_stream(process.stdout)
            span.set_attributes(result.telemetry)
            if result.structured_output is None:
                raise JudgeError(f"{self.executable} returned no verdict:\n{process.stdout}")
            return result.structured_output

    def _run(self, instructions: str, prompt: str) -> subprocess.CompletedProcess[str]:
        if self.deadline is None:
            return self._run_until(instructions, prompt, None)
        remaining = self.deadline.remaining_seconds()
        if remaining <= 0:
            raise self.deadline.reached()
        try:
            return self._run_until(instructions, prompt, remaining)
        except subprocess.TimeoutExpired as error:
            raise self.deadline.reached() from error

    def _run_until(
        self, instructions: str, prompt: str, timeout: float | None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                self.executable,
                "--safe-mode",
                "-p",
                "--model",
                self.model,
                "--output-format",
                "stream-json",
                "--verbose",
                "--json-schema",
                _VERDICT_SCHEMA,
                "--tools",
                _READ_ONLY_TOOLS,
                "--permission-prompts",
                "none",
                "--system-prompt",
                instructions,
                "--no-session-persistence",
            ],
            input=prompt,
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
