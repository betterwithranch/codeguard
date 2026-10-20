from google import genai
from google.genai import types

_RETRIES = types.HttpRetryOptions(attempts=5)


def gemini_client(project: str | None = None, location: str | None = None) -> genai.Client:
    return genai.Client(
        enterprise=True,
        project=project,
        location=location,
        http_options=types.HttpOptions(retry_options=_RETRIES),
    )
