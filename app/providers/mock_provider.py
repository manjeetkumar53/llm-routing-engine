from __future__ import annotations


class MockLLMProvider:
    def complete(self, tier: str, prompt: str) -> tuple[str, int, int]:
        if tier == "cheap" and "FORCE_FAIL_CHEAP" in prompt:
            raise RuntimeError("Simulated cheap model failure")

        input_tokens = max(1, len(prompt) // 4)
        output_tokens = max(8, min(220, len(prompt) // 6))

        if tier == "premium":
            completion = (
                "[premium] Detailed response with stronger reasoning depth and tighter structure."
            )
        else:
            completion = "[cheap] Concise response for straightforward prompt."

        return completion, input_tokens, output_tokens
