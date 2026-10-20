from dataclasses import dataclass

from google.genai import types


@dataclass
class GeminiUsage:
    num_turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    thinking_tokens: int = 0

    def add(self, response: types.GenerateContentResponse) -> None:
        self.num_turns += 1
        usage = response.usage_metadata
        if usage is None:
            return
        self.input_tokens += usage.prompt_token_count or 0
        self.output_tokens += usage.candidates_token_count or 0
        self.cache_read_input_tokens += usage.cached_content_token_count or 0
        self.thinking_tokens += usage.thoughts_token_count or 0

    @property
    def telemetry(self) -> dict[str, object]:
        return {
            "num_turns": self.num_turns,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "thinking_tokens": self.thinking_tokens,
        }
