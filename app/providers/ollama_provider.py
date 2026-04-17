from __future__ import annotations

import httpx

TIER_MODEL: dict[str, str] = {
    "cheap": "llama3.2:1b",
    "premium": "llama3.1:8b",
}

OLLAMA_BASE_URL = "http://localhost:11434/api/chat"


class OllamaProvider:
    """Route to local Ollama models (no API key required).

    Requires:
        ollama serve  (running locally on port 11434)
        ollama pull llama3.2:1b
        ollama pull llama3.1:8b

    Override models via OLLAMA_CHEAP_MODEL / OLLAMA_PREMIUM_MODEL env vars.
    Override base URL via OLLAMA_BASE_URL env var.
    """

    def __init__(self) -> None:
        import os

        self._base_url = os.getenv("OLLAMA_BASE_URL", OLLAMA_BASE_URL)
        self._models = {
            "cheap": os.getenv("OLLAMA_CHEAP_MODEL", TIER_MODEL["cheap"]),
            "premium": os.getenv("OLLAMA_PREMIUM_MODEL", TIER_MODEL["premium"]),
        }

    def complete(self, tier: str, prompt: str) -> tuple[str, int, int]:
        model = self._models[tier]
        response = httpx.post(
            self._base_url,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        content: str = data["message"]["content"]
        input_tokens: int = data.get("prompt_eval_count", max(1, len(prompt) // 4))
        output_tokens: int = data.get("eval_count", max(8, len(content) // 4))
        return content, input_tokens, output_tokens
