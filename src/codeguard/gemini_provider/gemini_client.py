from dataclasses import dataclass
from functools import cached_property

from google import genai
from google.genai import models, types

# Backoff runs 1s doubling to about 2 minutes, past a per-minute quota reset after a 429.
_RETRIES = types.HttpRetryOptions(attempts=8)


def gemini_client(project: str | None = None, location: str | None = None) -> genai.Client:
    return genai.Client(
        enterprise=True,
        project=project,
        location=location,
        http_options=types.HttpOptions(retry_options=_RETRIES),
    )


@dataclass(frozen=True)
class DeferredGeminiClient:
    project: str | None = None
    location: str | None = None

    @property
    def models(self) -> models.Models:
        return self._client.models

    @cached_property
    def _client(self) -> genai.Client:
        return gemini_client(self.project, self.location)
