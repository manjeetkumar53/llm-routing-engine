from __future__ import annotations

TIER_MODEL: dict[str, str] = {
    "cheap": "claude-haiku-4-5",
    "premium": "claude-opus-4-5",
}


class AnthropicProvider:
    """Route to Claude Haiku (cheap) or Claude Opus (premium).

    Requires:
        pip install anthropic
        ANTHROPIC_API_KEY env var set
    """

    def __init__(self) -> None:
        try:
            import anthropic  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "anthropic package is required: pip install anthropic"
            ) from exc
        self._client = anthropic.Anthropic()

    def complete(self, tier: str, prompt: str) -> tuple[str, int, int]:
        import anthropic  # type: ignore[import]

        model = TIER_MODEL[tier]
        message = self._client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        content = message.content[0].text if message.content else ""
        return content, message.usage.input_tokens, message.usage.output_tokens
