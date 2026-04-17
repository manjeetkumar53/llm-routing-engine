from __future__ import annotations

TIER_MODEL: dict[str, str] = {
    "cheap": "gpt-4o-mini",
    "premium": "gpt-4o",
}


class OpenAIProvider:
    """Route to GPT-4o-mini (cheap) or GPT-4o (premium).

    Requires:
        pip install openai
        OPENAI_API_KEY env var set
    """

    def __init__(self) -> None:
        try:
            from openai import OpenAI  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "openai package is required: pip install openai"
            ) from exc
        self._client = OpenAI()

    def complete(self, tier: str, prompt: str) -> tuple[str, int, int]:
        model = TIER_MODEL[tier]
        response = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content or ""
        usage = response.usage
        return content, usage.prompt_tokens, usage.completion_tokens
