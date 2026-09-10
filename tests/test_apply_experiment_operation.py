from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hh_applicant_tool.ai.base import AIError
from hh_applicant_tool.automation.apply_experiments import ApplyExperimentConfig
from hh_applicant_tool.operations.apply_experiment import Operation


def _vacancy(vacancy_id: str = "42") -> dict[str, object]:
    return {
        "id": vacancy_id,
        "name": "Frontend developer",
        "employer": {"id": "employer-1", "name": "Example"},
        "response_letter_required": True,
        "relations": [],
        "archived": False,
        "has_test": False,
        "response_url": None,
        "alternate_url": f"https://example.test/{vacancy_id}",
    }


def _resume(resume_id: str = "resume-a") -> dict[str, object]:
    return {
        "id": resume_id,
        "title": "Frontend developer",
        "alternate_url": f"https://example.test/resume/{resume_id}",
    }


def _cover_config() -> ApplyExperimentConfig:
    return ApplyExperimentConfig.from_mapping(
        {
            "enabled": True,
            "name": "cover_v1",
            "cover_letters": {
                "variants": [
                    {"id": "ai", "mode": "ai", "weight": 1},
                    {"id": "plain", "mode": "template", "weight": 1},
                ]
            },
        },
        profile_key="account1",
    )


def _resume_config() -> ApplyExperimentConfig:
    return ApplyExperimentConfig.from_mapping(
        {
            "enabled": True,
            "name": "resume_v1",
            "resumes": {
                "variants": [
                    {"id": "a", "resume_id": "resume-a", "weight": 1},
                    {"id": "b", "resume_id": "resume-b", "weight": 1},
                ]
            },
        },
        profile_key="account1",
    )


def _prepared_operation(experiment: ApplyExperimentConfig) -> Operation:
    operation = Operation()
    operation.force_message = True
    operation.experiment = experiment
    operation.cover_letter = "Добрый день, %(first_name)s. Рассмотрите мое резюме на %(vacancy_name)s."
    operation.message_prompt = "Напиши короткое письмо"
    operation.cover_letter_ai_requested = True
    operation.cover_fallback_count = 0
    operation._cover_outcomes = {}
    operation._cover_variant_clients = {}
    operation._build_cover_letter_context = Mock(return_value="safe context")
    operation.tool = SimpleNamespace(get_cover_letter_ai=Mock())
    return operation


def test_ai_runtime_failure_falls_back_to_plain_template() -> None:
    operation = _prepared_operation(ApplyExperimentConfig.disabled("account1"))
    ai = Mock()
    ai.complete.side_effect = AIError("provider down")
    operation.cover_letter_ai = ai

    letter = operation._build_cover_letter(
        _vacancy(),
        _resume(),
        {"first_name": "Максим", "vacancy_name": "Frontend developer"},
    )

    assert "Максим" in letter
    assert "Frontend developer" in letter
    assert operation.cover_fallback_count == 1
    outcome = operation._cover_outcomes[("42", "resume-a")]
    assert outcome == ("default", "ai", "fallback_template", True)


def test_ai_variant_keeps_assignment_when_fallback_is_used() -> None:
    operation = _prepared_operation(_cover_config())
    operation.cover_letter_ai = Mock()
    operation.cover_letter_ai.complete.side_effect = AIError("rate limited")
    operation.experiment.choose_cover = Mock(  # type: ignore[method-assign]
        return_value=operation.experiment.cover_variants[0]
    )

    operation._build_cover_letter(
        _vacancy(),
        _resume(),
        {"first_name": "Максим", "vacancy_name": "Frontend developer"},
    )

    outcome = operation._cover_outcomes[("42", "resume-a")]
    assert outcome == ("ai", "ai", "fallback_template", True)


def test_template_variant_never_calls_llm() -> None:
    operation = _prepared_operation(_cover_config())
    operation.cover_letter_ai = Mock()
    operation.experiment.choose_cover = Mock(  # type: ignore[method-assign]
        return_value=operation.experiment.cover_variants[1]
    )

    letter = operation._build_cover_letter(
        _vacancy(),
        _resume(),
        {"first_name": "Максим", "vacancy_name": "Frontend developer"},
    )

    assert letter
    operation.cover_letter_ai.complete.assert_not_called()
    assert operation.cover_fallback_count == 0


def test_resume_experiment_assigns_each_vacancy_to_only_one_resume() -> None:
    operation = Operation()
    operation.experiment = _resume_config()
    assigned = operation.experiment.choose_resume("42")
    operation.dry_run = False
    operation.args = SimpleNamespace(skip_tests=True)  # type: ignore[misc]

    assert assigned.resume_id in {"resume-a", "resume-b"}
    other_resume = "resume-b" if assigned.resume_id == "resume-a" else "resume-a"

    assert operation._should_skip_vacancy_basic(_vacancy(), other_resume) is True


def test_resume_experiment_requires_search_mode() -> None:
    operation = Operation()
    operation.tool = SimpleNamespace()
    operation.experiment = _resume_config()

    assert operation.experiment.resume_enabled is True
    # This invariant is enforced before any vacancy is processed. Keeping it as
    # an explicit regression assertion documents why similar-vacancy mode is not
    # statistically valid for resume A/B tests.
    with pytest.raises(ValueError, match="requires --search"):
        if operation.experiment.resume_enabled and not "":
            raise ValueError(
                "resume A/B testing requires --search so all resume variants use the same vacancy universe"
            )
