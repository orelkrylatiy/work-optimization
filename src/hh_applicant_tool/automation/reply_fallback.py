from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from hh_applicant_tool.ai.openai import ChatOpenAI, OpenAIError
from hh_applicant_tool.automation.reply_worker import reply_quality_issues

logger = logging.getLogger(__name__)

DEFAULT_REPLY_FALLBACK_MESSAGE = (
    "Здравствуйте! Спасибо за сообщение. Я разработчик, вакансия мне интересна. "
    "Готов обсудить задачи, формат работы и ответить на вопросы."
)


@dataclass(frozen=True)
class ReplyFallbackConfig:
    enabled: bool = True
    message: str = DEFAULT_REPLY_FALLBACK_MESSAGE


def load_reply_fallback_config(config: dict[str, Any]) -> ReplyFallbackConfig:
    """Load the optional reply fallback from a profile config.

    The fallback is enabled by default so a transient LLM outage does not lose
    an employer conversation. It can be disabled per profile with
    ``reply_fallback.enabled = false``.
    """
    raw = config.get("reply_fallback")
    if raw is None:
        fallback = ReplyFallbackConfig()
    else:
        if not isinstance(raw, dict):
            raise ValueError("'reply_fallback' must be a JSON object")
        enabled = raw.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError("'reply_fallback.enabled' must be a boolean")
        message = raw.get("message", DEFAULT_REPLY_FALLBACK_MESSAGE)
        if not isinstance(message, str):
            raise ValueError("'reply_fallback.message' must be a string")
        fallback = ReplyFallbackConfig(enabled=enabled, message=" ".join(message.split()))

    if fallback.enabled:
        issues = reply_quality_issues(fallback.message)
        if issues:
            raise ValueError(
                "'reply_fallback.message' failed reply quality checks: " + ", ".join(issues)
            )
    return fallback


class FallbackChatAI:
    """Use a static reply only after the primary LLM raises OpenAIError.

    ChatOpenAI already performs its configured provider/network retries. This
    wrapper therefore runs only after those retries have been exhausted (or a
    provider response is otherwise unusable). Normal AI text is returned
    unchanged and still goes through ReplyWorker's humanizer.
    """

    def __init__(self, primary: ChatOpenAI, fallback: ReplyFallbackConfig) -> None:
        self.primary = primary
        self.fallback = fallback
        self.fallback_uses = 0

    def complete(self, prompt: str) -> str:
        try:
            return self.primary.complete(prompt)
        except OpenAIError as exc:
            if not self.fallback.enabled:
                raise

            issues = reply_quality_issues(self.fallback.message)
            if issues:
                raise OpenAIError(
                    "Configured reply fallback failed quality checks: " + ", ".join(issues)
                ) from exc

            self.fallback_uses += 1
            logger.warning(
                "LLM unavailable after retries; using configured reply fallback: %s",
                exc,
            )
            return self.fallback.message
