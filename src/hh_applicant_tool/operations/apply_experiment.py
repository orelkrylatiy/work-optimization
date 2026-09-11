# ruff: noqa: I001
from __future__ import annotations

import logging
import os
from typing import Any

from ..ai.base import AIError
from ..api import datatypes
from ..automation.apply_experiments import (
    ApplyExperimentConfig,
    ApplyExperimentTracker,
    AssignmentRecord,
    WeightedVariant,
)
from ..storage.repositories.errors import RepositoryError
from ..utils.misc import expand_env_placeholders, load_prompt
from ..utils.string import rand_text
from .apply_vacancies import Namespace, Operation as BaseApplyOperation

logger = logging.getLogger(__package__)


class Operation(BaseApplyOperation):
    """Apply with deterministic A/B experiments and fail-open cover-letter fallback."""

    __aliases__ = ("apply-ab",)

    def run(self, tool, args: Namespace) -> int | None:
        self.tool = tool
        self._args = args
        args.system_prompt = load_prompt(args.system_prompt) or ""
        args.message_prompt = load_prompt(args.message_prompt) or ""
        self.cover_letter = (
            expand_env_placeholders(args.letter_file.read_text(encoding="utf-8", errors="ignore"))
            if args.letter_file
            else self.cover_letter
        )
        self._assign_args(args)
        if self.max_responses is not None and self.max_responses < 0:
            raise ValueError("max_responses must be a non-negative integer")
        self.responses_sent = 0
        self.response_delay_min, self.response_delay_max = self._parse_response_delay(
            args.response_delay
        )

        profile_key = (
            getattr(tool, "profile_id", None) or os.environ.get("HH_PROFILE_ID") or "default"
        )
        raw_experiment = tool.config.get("apply_experiments")
        self.experiment = ApplyExperimentConfig.from_mapping(
            raw_experiment,
            profile_key=str(profile_key),
        )
        if self.experiment.resume_enabled and not args.search:
            raise ValueError(
                "resume A/B testing requires --search so all resume variants use "
                "the same vacancy universe"
            )

        if self.experiment.resume_enabled:
            published = {
                str(resume.get("id"))
                for resume in tool.get_resumes()
                if (resume.get("status") or {}).get("id") == "published"
            }
            required = {str(variant.resume_id) for variant in self.experiment.resume_variants}
            missing = required - published
            if missing:
                raise ValueError(
                    "one or more resume experiment variants are not published; "
                    "check apply_experiments.resumes"
                )

        self.experiment_tracker = (
            ApplyExperimentTracker(tool.db)
            if self.experiment.enabled and not self.dry_run
            else None
        )
        self._cover_outcomes: dict[tuple[str, str], tuple[str, str, str, bool]] = {}
        self._cover_variant_clients: dict[str, Any] = {}
        self.cover_fallback_count = 0
        self.ai_error_count = 0
        self.ai_filter = args.ai_filter
        self.vacancy_filter_ai = None
        self._resume_analysis_cache: dict[tuple[str | None, str], str] = {}
        self._vacancy_context_cache: dict[str, dict[str, Any]] = {}

        wants_ai = (
            any(variant.mode == "ai" for variant in self.experiment.cover_variants)
            if self.experiment.cover_enabled
            else bool(args.use_ai)
        )
        self.cover_letter_ai_requested = wants_ai
        if wants_ai:
            try:
                self.cover_letter_ai = tool.get_cover_letter_ai(args.system_prompt)
            except (OSError, ValueError) as exc:
                self.cover_letter_ai = None
                logger.warning(
                    "Cover-letter AI unavailable during initialization; "
                    "template fallback is armed: %s",
                    exc,
                )
        else:
            self.cover_letter_ai = None

        logger.info(
            "Application experiment: enabled=%s name=%s cover=%d resume=%d",
            self.experiment.enabled,
            self.experiment.name or "-",
            len(self.experiment.cover_variants),
            len(self.experiment.resume_variants),
        )
        self._apply_vacancies()

        if self.cover_fallback_count:
            logger.warning(
                "HH_COVER_FALLBACK_SUMMARY count=%d",
                self.cover_fallback_count,
            )
        if self.ai_error_count:
            logger.error(
                "AI failed outside the cover-letter fallback path for %d vacancies",
                self.ai_error_count,
            )
            return 1
        return None

    def _apply_vacancies(self) -> None:
        super()._apply_vacancies()
        if self.dry_run or not self.experiment.enabled:
            return

        # Experiment outcomes can change days after the application. Persist all
        # applicant-visible states, not only the active subset used by the legacy
        # sync, so the ops report can join assignments to response/invitation/discard.
        for negotiation in self.tool.get_negotiations(status="all"):
            vacancy = negotiation.get("vacancy")
            if not vacancy or not vacancy.get("employer"):
                continue
            try:
                self.tool.storage.negotiations.save(negotiation)
            except RepositoryError as exc:
                logger.warning("Could not sync experiment negotiation state: %s", exc)

    def _resume_quotas(self, limit: int) -> dict[str, int]:
        variants = self.experiment.resume_variants
        total_weight = sum(variant.weight for variant in variants)
        quotas = {variant.id: limit * variant.weight // total_weight for variant in variants}
        remainder = limit - sum(quotas.values())
        ranked = sorted(
            enumerate(variants),
            key=lambda item: (-(limit * item[1].weight % total_weight), item[0]),
        )
        for _, variant in ranked[:remainder]:
            quotas[variant.id] += 1
        return quotas

    def _apply_resume(
        self,
        resume: datatypes.Resume,
        user: datatypes.User,
        seen_employers: set[str],
    ) -> None:
        if not self.experiment.resume_enabled:
            super()._apply_resume(resume, user, seen_employers)
            return

        variant = next(
            (
                item
                for item in self.experiment.resume_variants
                if item.resume_id == resume.get("id")
            ),
            None,
        )
        if variant is None:
            logger.debug("Skipping resume outside active experiment")
            return

        original_limit = self.max_responses
        if original_limit is None:
            super()._apply_resume(resume, user, seen_employers)
            return

        quota = self._resume_quotas(original_limit)[variant.id]
        if quota == 0:
            logger.info(
                "Experiment %s allocated zero responses to resume variant %s",
                self.experiment.name,
                variant.id,
            )
            return

        # Base apply processes resumes sequentially and uses a global cap. Without
        # this per-variant cap the first resume could consume the entire run and
        # invalidate a resume A/B test. Do not reallocate an under-filled quota:
        # keeping planned weights is more important than maximizing volume.
        self.max_responses = self.responses_sent + quota
        try:
            logger.info(
                "Experiment %s resume variant %s quota=%d",
                self.experiment.name,
                variant.id,
                quota,
            )
            super()._apply_resume(resume, user, seen_employers)
        finally:
            self.max_responses = original_limit

    def _should_skip_vacancy_basic(
        self,
        vacancy: dict[str, Any],
        resume_id: str,
    ) -> bool:
        if self.experiment.resume_enabled:
            assigned = self.experiment.choose_resume(vacancy["id"])
            if assigned.resume_id != resume_id:
                logger.debug(
                    "Experiment %s assigned vacancy to resume variant %s; current resume skipped",
                    self.experiment.name,
                    assigned.id,
                )
                return True
        return super()._should_skip_vacancy_basic(vacancy, resume_id)

    def _cover_variant(
        self,
        vacancy: dict[str, Any],
        resume: datatypes.Resume,
    ) -> WeightedVariant | None:
        if not self.experiment.cover_enabled:
            return None
        return self.experiment.choose_cover(vacancy["id"], str(resume["id"]))

    def _resume_variant_id(self, vacancy_id: str | int) -> str:
        if not self.experiment.resume_enabled:
            return "default"
        return self.experiment.choose_resume(vacancy_id).id

    def _template_letter(
        self,
        variant: WeightedVariant | None,
        placeholders: dict[str, str],
    ) -> str:
        template = variant.template if variant and variant.template else self.cover_letter
        return rand_text(expand_env_placeholders(template)) % placeholders

    def _ai_client_for_variant(self, variant: WeightedVariant | None):
        if variant is None or not variant.system_prompt:
            return self.cover_letter_ai
        if variant.id in self._cover_variant_clients:
            return self._cover_variant_clients[variant.id]

        prompt = load_prompt(variant.system_prompt) or ""
        client = self.tool.get_cover_letter_ai(prompt)
        self._cover_variant_clients[variant.id] = client
        return client

    def _build_ai_letter(
        self,
        vacancy: dict[str, Any],
        resume: datatypes.Resume,
        variant: WeightedVariant | None,
    ) -> str:
        client = self._ai_client_for_variant(variant)
        if client is None:
            raise AIError("cover-letter AI client is unavailable")
        context = self._build_cover_letter_context(vacancy, resume)
        message_prompt = (
            variant.message_prompt if variant and variant.message_prompt else self.message_prompt
        )
        msg = message_prompt + "\n\n"
        msg += (
            "Напиши уникальное сопроводительное письмо под эту конкретную вакансию. "
            "Не ограничивайся повторением названия вакансии. Используй только факты "
            "из контекста, не выдумывай опыт и не используй placeholder'ы.\n\n"
        )
        msg += context
        logger.debug("prompt: %s", msg)
        return client.complete(msg)

    def _build_cover_letter(
        self,
        vacancy: dict[str, Any],
        resume: datatypes.Resume,
        message_placeholders: dict[str, str],
    ) -> str:
        key = (str(vacancy["id"]), str(resume["id"]))
        if not (self.force_message or vacancy.get("response_letter_required")):
            self._cover_outcomes[key] = ("none", "none", "none", False)
            return ""

        variant = self._cover_variant(vacancy, resume)
        assigned_variant = variant.id if variant else "default"
        assigned_mode = (
            variant.mode if variant else ("ai" if self.cover_letter_ai_requested else "template")
        )

        if assigned_mode == "template":
            letter = self._template_letter(variant, message_placeholders)
            self._cover_outcomes[key] = (
                assigned_variant,
                assigned_mode,
                "template",
                False,
            )
            return letter

        try:
            letter = self._build_ai_letter(vacancy, resume, variant)
            self._cover_outcomes[key] = (
                assigned_variant,
                assigned_mode,
                "ai",
                False,
            )
            return letter
        except (AIError, OSError, ValueError) as exc:
            self.cover_fallback_count += 1
            logger.warning(
                "HH_COVER_FALLBACK experiment=%s variant=%s reason=ai_unavailable: %s",
                self.experiment.name or "none",
                assigned_variant,
                exc,
            )
            letter = self._template_letter(None, message_placeholders)
            self._cover_outcomes[key] = (
                assigned_variant,
                assigned_mode,
                "fallback_template",
                True,
            )
            return letter

    def _assignment_record(
        self,
        vacancy: dict[str, Any],
        resume_id: str,
    ) -> AssignmentRecord:
        key = (str(vacancy["id"]), str(resume_id))
        cover_variant, assigned_mode, actual_mode, fallback_used = self._cover_outcomes.get(
            key,
            ("none", "none", "none", False),
        )
        return AssignmentRecord(
            experiment=self.experiment.name,
            vacancy_id=str(vacancy["id"]),
            resume_id=str(resume_id),
            resume_variant=self._resume_variant_id(vacancy["id"]),
            cover_variant=cover_variant,
            cover_assigned_mode=assigned_mode,
            cover_actual_mode=actual_mode,
            fallback_used=fallback_used,
        )

    def _send_vacancy_response(
        self,
        vacancy: dict[str, Any],
        resume_id: str,
        letter: str,
    ):
        if not self.experiment.enabled or self.dry_run:
            return super()._send_vacancy_response(vacancy, resume_id, letter)

        record = self._assignment_record(vacancy, resume_id)
        assert self.experiment_tracker is not None
        self.experiment_tracker.ensure_assignment(record)
        try:
            result = super()._send_vacancy_response(vacancy, resume_id, letter)
        except Exception:
            self.experiment_tracker.mark_failed(record, "send_exception")
            raise

        if getattr(result, "accepted", bool(result)):
            self.experiment_tracker.mark_sent(record)
        else:
            self.experiment_tracker.mark_failed(record, "not_accepted")
        return result
