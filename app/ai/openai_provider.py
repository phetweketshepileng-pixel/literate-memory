"""OpenAI implementation of AIProvider. Uses JSON-mode/structured-output
where a schema is supplied, per docs/ai-architecture.md section 4
("Structured output enforcement")."""
from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI, APIStatusError, APITimeoutError

from app.ai.base import AICompletionResult, AIProvider, _NonRetriableProviderError, _RetriableProviderError
from app.core.config import settings

# Model tiers: cheaper/faster model for classification-shaped tasks (match
# pre-filtering assist), larger model for generation-shaped tasks (CV
# rewriting, cover letters) — see ai-architecture.md section 5.
MODEL_TIERS = {
    "classification": "gpt-4o-mini",
    "generation": "gpt-4o",
    "default": "gpt-4o-mini",
}


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def _call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any] | None,
        max_tokens: int,
        model: str,
    ) -> AICompletionResult:
        resolved_model = MODEL_TIERS.get(model, model if model != "default" else MODEL_TIERS["default"])

        response_format: dict[str, Any] = {"type": "text"}
        if json_schema is not None:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_response",
                    "schema": json_schema,
                    "strict": True,
                },
            }

        try:
            response = await self._client.chat.completions.create(
                model=resolved_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                response_format=response_format,
                temperature=0.3,  # low temperature: these are scoring/structured
                                    # tasks, not creative writing, except cover
                                    # letters which tolerate the same setting fine
            )
        except APITimeoutError as exc:
            raise _RetriableProviderError(str(exc)) from exc
        except APIStatusError as exc:
            if exc.status_code >= 500 or exc.status_code == 429:
                raise _RetriableProviderError(str(exc)) from exc
            raise _NonRetriableProviderError(str(exc)) from exc

        choice = response.choices[0]
        return AICompletionResult(
            content=choice.message.content or "",
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            model=resolved_model,
        )
