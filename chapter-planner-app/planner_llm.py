"""
PlannerLLM — the LLM backend interface for CPE (D-3).

One protocol, one real impl this round: `AgentSdkPlannerLLM` wrapping
`claude-agent-sdk` against the dev's Claude Code OAuth session. The SDK is
lazily imported so the app boots / tests run without it installed.

Carries forward the in-dars planner's D-13 bug fixes:
  - assistant text lives in `message.content[].text` blocks, NOT `message.text`
  - the SDK requires a `ClaudeAgentOptions(...)` object, NOT a raw dict
"""
from typing import Protocol, runtime_checkable

from logging_config import get_logger

logger = get_logger(__name__)


class PlannerLLMError(RuntimeError):
    """Raised when the LLM call fails (transport, SDK, or empty response)."""


@runtime_checkable
class PlannerLLM(Protocol):
    async def complete(self, system: str, user: str) -> str:
        """Return the model's raw text response to (system, user)."""
        ...


class AgentSdkPlannerLLM:
    """Development backend (D-3): claude-agent-sdk over the Claude Code session.

    Lazy-imports the SDK so the service boots without it; raises
    PlannerLLMError with a clear message if it isn't installed.
    """

    async def complete(self, system: str, user: str) -> str:
        try:
            from claude_agent_sdk import (  # type: ignore[import-not-found]
                ClaudeAgentOptions,
                query,
            )
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise PlannerLLMError(
                "claude-agent-sdk is not installed — `pip install claude-agent-sdk`"
            ) from exc

        logger.info(
            "[LLM] complete entry — system_chars=%d user_chars=%d", len(system), len(user)
        )
        chunks: list[str] = []
        try:
            async for message in query(
                prompt=user,
                options=ClaudeAgentOptions(system_prompt=system),
            ):
                # D-13: assistant text is in content blocks (TextBlock.text),
                # not a top-level .text attribute.
                for block in getattr(message, "content", None) or []:
                    text = getattr(block, "text", None)
                    if isinstance(text, str):
                        chunks.append(text)
        except Exception as exc:  # pragma: no cover - dev path
            logger.error("[LLM] query failed", exc_info=True)
            raise PlannerLLMError(f"agent-sdk query failed: {exc}") from exc

        out = "".join(chunks)
        logger.info("[LLM] complete exit — response_chars=%d", len(out))
        if not out.strip():
            raise PlannerLLMError("LLM returned an empty response")
        return out
