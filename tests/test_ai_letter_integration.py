"""Opt-in integration check for the configured cover-letter provider.

This test is deliberately disabled unless RUN_AI_INTEGRATION=1.  Importing
the module and collecting the regular test suite must never contact a local
Ollama server or the configured AI provider.
"""

from __future__ import annotations

import os

import pytest


pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_network,
    pytest.mark.skipif(
        os.getenv("RUN_AI_INTEGRATION") != "1",
        reason="set RUN_AI_INTEGRATION=1 to exercise the configured AI provider",
    ),
]


def test_configured_cover_letter_provider_generates_a_response():
    """Validate the manually configured provider only in an opt-in run."""
    import requests

    from hh_applicant_tool.main import HHApplicantTool
    from hh_applicant_tool.utils.misc import load_prompt

    ollama_response = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
    ollama_response.raise_for_status()
    assert ollama_response.json().get("models"), "Ollama has no installed models"

    tool = HHApplicantTool()
    system_prompt = load_prompt("prompts/cover_letter_frontend.txt")
    message_prompt = load_prompt(
        "Сгенерируй сопроводительное письмо не более 5-7 предложений от моего имени для вакансии"
    )
    prompt = "\n\n".join(
        [
            message_prompt,
            "Название вакансии: Frontend-разработчик (React/TypeScript)",
            "Мое резюме: Frontend-разработчик (ReactJS, TypeScript, Redux)",
        ]
    )

    answer = tool.get_cover_letter_ai(system_prompt).complete(prompt).strip()

    assert answer, "The configured cover-letter provider returned an empty response"
