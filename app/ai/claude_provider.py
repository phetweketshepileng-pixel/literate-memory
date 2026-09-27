"""Claude implementation stub, same AIProvider interface as OpenAIProvider.
Not wired into AI_PROVIDER selection until Phase 2 (see V1.1 phased plan).
Kept here now so activating it later is a config change, not new code."""
from __future__ import annotations

from typing import Any

from app.ai.base import AICompletionResult, AIProvider


class ClaudeProvider(AIProvider):
    name = "claude"

    async def _call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any] | None,
        max_tokens: int,
        model: str,
    ) -> AICompletionResult:
        raise NotImplementedError(
            "ClaudeProvider is scaffolded for Phase 2 activation (see "
            "docs/ai-architecture.md section 7.3). Implement using the "
            "Anthropic SDK's messages.create with tool-use or a JSON-forcing "
            "system prompt for structured output, matching the same "
            "AICompletionResult contract as OpenAIProvider._call."
        )
