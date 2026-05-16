"""
Async LLM wrapper for the breakdown engine.

Phase 2 only uses Anthropic (D-1: Claude-first), via the official anthropic
SDK in async mode. F2.5 may add a model-routing layer; for now keep it tight.
"""
import logging

from anthropic import AsyncAnthropic

from dars.config import settings

log = logging.getLogger("breakdown.llm")

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_MAX_TOKENS = 32000

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured — set it in dars/.env or env."
            )
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def call_llm(
    system_prompt: str,
    user_message: str,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Send a single message to Claude and return the assembled text."""
    log.info(
        "call_llm: model=%s system_chars=%d user_chars=%d",
        model, len(system_prompt), len(user_message),
    )
    client = _get_client()
    message = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    text = "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    )
    log.info("call_llm: response_chars=%d stop=%s", len(text), message.stop_reason)
    return text
