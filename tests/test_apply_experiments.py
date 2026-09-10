from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from hh_applicant_tool.automation.apply_experiments import (
    ApplyExperimentConfig,
    ApplyExperimentTracker,
    AssignmentRecord,
)

REPORT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "experiment_report.py"


def _config(profile: str = "account1") -> ApplyExperimentConfig:
    return ApplyExperimentConfig.from_mapping(
        {
            "enabled": True,
            "name": "frontend_sep_v1",
            "seed": "stable-v1",
            "cover_letters": {
                "variants": [
                    {"id": "ai", "mode": "ai", "weight": 50},
                    {"id": "template", "mode": "template", "weight": 50},
                ]
            },
            "resumes": {
                "variants": [
                    {"id": "resume_a", "resume_id": "secret-resume-a", "weight": 50},
                    {"id": "resume_b", "resume_id": "secret-resume-b", "weight": 50},
                ]
            },
        },
        profile_key=profile,
    )


def _record(
    *,
    vacancy: str,
    resume_id: str,
    resume_variant: str,
    cover_variant: str,
    assigned_mode: str,
    actual_mode: str,
    fallback: bool = False,
) -> AssignmentRecord:
    return AssignmentRecord(
        experiment="frontend_sep_v1",
        vacancy_id=vacancy,
        resume_id=resume_id,
        resume_variant=resume_variant,
        cover_variant=cover_variant,
        cover_assigned_mode=assigned_mode,
        cover_actual_mode=actual_mode,
        fallback_used=fallback,
    )


def test_assignment_is_deterministic_for_same_profile_and_vacancy() -> None:
    config = _config()

    resume = config.choose_resume("vacancy-42")
    cover = config.choose_cover("vacancy-42", resume.resume_id or "")

    assert config.choose_resume("vacancy-42") == resume
    assert config.choose_cover("vacancy-42", resume.resume_id or "") == cover


def test_config_rejects_resume_test_without_two_variants() -> None:
    with pytest.raises(ValueError, match="at least two variants"):
        ApplyExperimentConfig.from_mapping(
            {
                "enabled": True,
                "name": "bad_exp",
                "resumes": {
                    "variants": [{"id": "only", "resume_id": "resume-1"}]
                },
            },
            profile_key="account1",
        )


def test_tracker_keeps_one_immutable_assignment_per_vacancy() -> None:
    conn = sqlite3.connect(":memory:")
    tracker = ApplyExperimentTracker(conn)
    first = _record(
        vacancy="vacancy-secret-1",
        resume_id="resume-secret-a",
        resume_variant="resume_a",
        cover_variant="ai",
        assigned_mode="ai",
        actual_mode="ai",
    )
    tracker.ensure_assignment(first)
    tracker.mark_sent(first)

    conflicting = _record(
        vacancy="vacancy-secret-1",
        resume_id="resume-secret-b",
        resume_variant="resume_b",
        cover_variant="template",
        assigned_mode="template",
        actual_mode="template",
    )
    with pytest.raises(ValueError, match="use a new apply_experiments.name"):
        tracker.ensure_assignment(conflicting)

    row = conn.execute(
        "SELECT resume_id, resume_variant, cover_variant, send_status "
        "FROM apply_experiment_assignments"
    ).fetchone()
    assert row == ("resume-secret-a", "resume_a", "ai", "sent")


def test_experiment_report_aggregates_outcomes_without_exporting_raw_ids(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config" / "account1"
    config_dir.mkdir(parents=True)
    db_path = config_dir / "data"
    conn = sqlite3.connect(db_path)
    tracker = ApplyExperimentTracker(conn)
    conn.execute(
        """
        CREATE TABLE negotiations (
            id INTEGER PRIMARY KEY,
            state TEXT NOT NULL,
            vacancy_id INTEGER NOT NULL,
            employer_id INTEGER,
            chat_id INTEGER NOT NULL,
            resume_id TEXT
        )
        """
    )

    rows = [
        (
            _record(
                vacancy="910001",
                resume_id="secret-resume-a",
                resume_variant="resume_a",
                cover_variant="ai",
                assigned_mode="ai",
                actual_mode="ai",
            ),
            "invitation",
        ),
        (
            _record(
                vacancy="910002",
                resume_id="secret-resume-b",
                resume_variant="resume_b",
                cover_variant="template",
                assigned_mode="template",
                actual_mode="template",
            ),
            "discard",
        ),
        (
            _record(
                vacancy="910003",
                resume_id="secret-resume-a",
                resume_variant="resume_a",
                cover_variant="ai",
                assigned_mode="ai",
                actual_mode="fallback_template",
                fallback=True,
            ),
            "response",
        ),
    ]
    for index, (record, state) in enumerate(rows, 1):
        tracker.ensure_assignment(record)
        tracker.mark_sent(record)
        conn.execute(
            "INSERT INTO negotiations VALUES (?, ?, ?, ?, ?, ?)",
            (
                index,
                state,
                int(record.vacancy_id),
                700000 + index,
                800000 + index,
                record.resume_id,
            ),
        )
    conn.commit()
    conn.close()

    output = tmp_path / "ops" / "experiments.json"
    result = subprocess.run(
        [
            sys.executable,
            str(REPORT_SCRIPT),
            "--root",
            str(tmp_path),
            "--config-dir",
            str(tmp_path / "config"),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    report = json.loads(output.read_text(encoding="utf-8"))
    exp = report["profiles"]["account1"]["experiments"]["frontend_sep_v1"]
    assert exp["cover_letters"]["ai"]["sent"] == 2
    assert exp["cover_letters"]["ai"]["fallbacks"] == 1
    assert exp["cover_letters"]["ai"]["states"]["invitation"] == 1
    assert exp["cover_letters"]["template"]["states"]["discard"] == 1
    assert exp["resumes"]["resume_a"]["sent"] == 2
    assert exp["resumes"]["resume_b"]["sent"] == 1
    assert exp["cells"]["resume_a|ai"]["sent"] == 2
    assert exp["cells"]["resume_a|ai"]["fallbacks"] == 1
    assert exp["cells"]["resume_b|template"]["sent"] == 1
    assert exp["actual_cover_modes"]["fallback_template"]["sent"] == 1

    serialized = json.dumps(report, ensure_ascii=False)
    for secret in (
        "secret-resume-a",
        "secret-resume-b",
        "910001",
        "910002",
        "910003",
        "700001",
        "800001",
    ):
        assert secret not in serialized
