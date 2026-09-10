from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

VARIANT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,47}$")
EXPERIMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class WeightedVariant:
    id: str
    weight: int
    mode: str = ""
    resume_id: str | None = None
    template: str | None = None
    system_prompt: str | None = None
    message_prompt: str | None = None


@dataclass(frozen=True)
class ApplyExperimentConfig:
    enabled: bool
    name: str
    seed: str
    profile_key: str
    cover_variants: tuple[WeightedVariant, ...]
    resume_variants: tuple[WeightedVariant, ...]

    @property
    def cover_enabled(self) -> bool:
        return self.enabled and bool(self.cover_variants)

    @property
    def resume_enabled(self) -> bool:
        return self.enabled and bool(self.resume_variants)

    @classmethod
    def disabled(cls, profile_key: str = "default") -> ApplyExperimentConfig:
        return cls(
            enabled=False,
            name="",
            seed="",
            profile_key=profile_key,
            cover_variants=(),
            resume_variants=(),
        )

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any] | None,
        *,
        profile_key: str,
    ) -> ApplyExperimentConfig:
        if not raw:
            return cls.disabled(profile_key)
        if not isinstance(raw, Mapping):
            raise ValueError("apply_experiments must be a JSON object")
        if not bool(raw.get("enabled", False)):
            return cls.disabled(profile_key)

        name = str(raw.get("name") or "").strip()
        if not EXPERIMENT_ID_RE.fullmatch(name):
            raise ValueError(
                "apply_experiments.name must use letters, numbers, dot, dash or underscore"
            )
        seed = str(raw.get("seed") or name).strip()
        if not seed:
            raise ValueError("apply_experiments.seed must not be empty")

        cover_variants = _parse_variants(raw.get("cover_letters"), dimension="cover")
        resume_variants = _parse_variants(raw.get("resumes"), dimension="resume")
        if not cover_variants and not resume_variants:
            raise ValueError(
                "enabled apply_experiments must define cover_letters and/or resumes"
            )

        return cls(
            enabled=True,
            name=name,
            seed=seed,
            profile_key=profile_key or "default",
            cover_variants=cover_variants,
            resume_variants=resume_variants,
        )

    def choose_cover(self, vacancy_id: str | int, resume_id: str) -> WeightedVariant:
        if not self.cover_enabled:
            raise ValueError("cover-letter experiment is disabled")
        return choose_weighted(
            self.cover_variants,
            key=self._assignment_key("cover", vacancy_id, resume_id),
        )

    def choose_resume(self, vacancy_id: str | int) -> WeightedVariant:
        if not self.resume_enabled:
            raise ValueError("resume experiment is disabled")
        return choose_weighted(
            self.resume_variants,
            key=self._assignment_key("resume", vacancy_id),
        )

    def _assignment_key(
        self,
        dimension: str,
        vacancy_id: str | int,
        resume_id: str = "",
    ) -> str:
        return "|".join(
            (
                self.name,
                self.seed,
                self.profile_key,
                dimension,
                str(vacancy_id),
                str(resume_id),
            )
        )


def _raw_variant_items(raw: Any, *, dimension: str) -> Sequence[Mapping[str, Any]]:
    if raw is None:
        return ()
    if isinstance(raw, Mapping):
        raw = raw.get("variants", ())
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError(f"apply_experiments.{dimension} variants must be a list")
    if any(not isinstance(item, Mapping) for item in raw):
        raise ValueError(f"apply_experiments.{dimension} variants must be objects")
    return raw


def _parse_variants(raw: Any, *, dimension: str) -> tuple[WeightedVariant, ...]:
    items = _raw_variant_items(raw, dimension=dimension)
    if not items:
        return ()
    if len(items) < 2:
        raise ValueError(f"{dimension} experiment needs at least two variants")

    variants: list[WeightedVariant] = []
    ids: set[str] = set()
    resume_ids: set[str] = set()
    for item in items:
        variant_id = str(item.get("id") or "").strip()
        if not VARIANT_ID_RE.fullmatch(variant_id):
            raise ValueError(
                f"invalid {dimension} variant id {variant_id!r}; use a short slug"
            )
        if variant_id in ids:
            raise ValueError(f"duplicate {dimension} variant id: {variant_id}")
        ids.add(variant_id)

        try:
            weight = int(item.get("weight", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid weight for {variant_id}") from exc
        if weight <= 0:
            raise ValueError(f"weight for {variant_id} must be positive")

        if dimension == "cover":
            mode = str(item.get("mode") or "").strip().lower()
            if mode not in {"ai", "template"}:
                raise ValueError(
                    f"cover variant {variant_id} mode must be 'ai' or 'template'"
                )
            resume_id = None
        else:
            mode = "resume"
            resume_id = str(item.get("resume_id") or "").strip()
            if not resume_id:
                raise ValueError(f"resume variant {variant_id} needs resume_id")
            if resume_id in resume_ids:
                raise ValueError(f"duplicate resume_id in experiment: {resume_id}")
            resume_ids.add(resume_id)

        variants.append(
            WeightedVariant(
                id=variant_id,
                weight=weight,
                mode=mode,
                resume_id=resume_id,
                template=(
                    str(item["template"]) if item.get("template") is not None else None
                ),
                system_prompt=(
                    str(item["system_prompt"])
                    if item.get("system_prompt") is not None
                    else None
                ),
                message_prompt=(
                    str(item["message_prompt"])
                    if item.get("message_prompt") is not None
                    else None
                ),
            )
        )
    return tuple(variants)


def choose_weighted(variants: Sequence[WeightedVariant], *, key: str) -> WeightedVariant:
    if not variants:
        raise ValueError("cannot choose from an empty variant list")
    total = sum(variant.weight for variant in variants)
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") % total
    cursor = 0
    for variant in variants:
        cursor += variant.weight
        if bucket < cursor:
            return variant
    raise AssertionError("weighted assignment fell outside the configured range")


@dataclass(frozen=True)
class AssignmentRecord:
    experiment: str
    vacancy_id: str
    resume_id: str
    resume_variant: str
    cover_variant: str
    cover_assigned_mode: str
    cover_actual_mode: str
    fallback_used: bool


class ApplyExperimentTracker:
    """Persist assignment facts without storing cover-letter or vacancy text."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS apply_experiment_assignments (
                experiment TEXT NOT NULL,
                vacancy_id TEXT NOT NULL,
                resume_id TEXT NOT NULL,
                resume_variant TEXT NOT NULL,
                cover_variant TEXT NOT NULL,
                cover_assigned_mode TEXT NOT NULL,
                cover_actual_mode TEXT NOT NULL,
                fallback_used INTEGER NOT NULL DEFAULT 0,
                send_status TEXT NOT NULL DEFAULT 'assigned',
                failure_kind TEXT,
                assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                sent_at DATETIME,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (experiment, vacancy_id)
            );
            CREATE INDEX IF NOT EXISTS idx_apply_exp_vac_resume
                ON apply_experiment_assignments(vacancy_id, resume_id);
            CREATE INDEX IF NOT EXISTS idx_apply_exp_name_status
                ON apply_experiment_assignments(experiment, send_status);
            """
        )
        self.conn.commit()

    def ensure_assignment(self, record: AssignmentRecord) -> None:
        existing = self.conn.execute(
            """
            SELECT resume_id, resume_variant, cover_variant, cover_assigned_mode
            FROM apply_experiment_assignments
            WHERE experiment = ? AND vacancy_id = ?
            """,
            (record.experiment, record.vacancy_id),
        ).fetchone()
        expected = (
            record.resume_id,
            record.resume_variant,
            record.cover_variant,
            record.cover_assigned_mode,
        )
        if existing is not None and tuple(existing) != expected:
            raise ValueError(
                "experiment assignment changed for an existing vacancy; "
                "use a new apply_experiments.name when changing variants or weights"
            )
        if existing is not None:
            return

        self.conn.execute(
            """
            INSERT INTO apply_experiment_assignments (
                experiment, vacancy_id, resume_id, resume_variant,
                cover_variant, cover_assigned_mode, cover_actual_mode,
                fallback_used, send_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'assigned')
            """,
            (
                record.experiment,
                record.vacancy_id,
                record.resume_id,
                record.resume_variant,
                record.cover_variant,
                record.cover_assigned_mode,
                record.cover_actual_mode,
                int(record.fallback_used),
            ),
        )
        self.conn.commit()

    def mark_sent(self, record: AssignmentRecord) -> None:
        self._update_result(record, send_status="sent", failure_kind=None, sent=True)

    def mark_failed(self, record: AssignmentRecord, failure_kind: str = "send_error") -> None:
        self._update_result(
            record,
            send_status="failed",
            failure_kind=failure_kind,
            sent=False,
        )

    def _update_result(
        self,
        record: AssignmentRecord,
        *,
        send_status: str,
        failure_kind: str | None,
        sent: bool,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            UPDATE apply_experiment_assignments
            SET cover_actual_mode = ?, fallback_used = ?, send_status = ?,
                failure_kind = ?, sent_at = CASE WHEN ? THEN COALESCE(sent_at, ?) ELSE sent_at END,
                updated_at = ?
            WHERE experiment = ? AND vacancy_id = ?
            """,
            (
                record.cover_actual_mode,
                int(record.fallback_used),
                send_status,
                failure_kind,
                int(sent),
                now,
                now,
                record.experiment,
                record.vacancy_id,
            ),
        )
        self.conn.commit()
