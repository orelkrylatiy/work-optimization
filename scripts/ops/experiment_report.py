#!/usr/bin/env python3
"""Build a privacy-safe cumulative A/B report from profile SQLite databases."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

KNOWN_STATES = {"response", "invitation", "discard", "hidden"}


def _profile_databases(config_dir: Path) -> list[tuple[str, Path]]:
    result: list[tuple[str, Path]] = []
    direct = config_dir / "data"
    if direct.is_file():
        result.append(("default", direct))
    if config_dir.is_dir():
        for child in sorted(config_dir.iterdir()):
            db_path = child / "data"
            if child.is_dir() and db_path.is_file():
                result.append((child.name, db_path))
    return result


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _new_metrics() -> dict[str, Any]:
    return {
        "assigned": 0,
        "sent": 0,
        "send_failed": 0,
        "fallbacks": 0,
        "states": {
            "response": 0,
            "invitation": 0,
            "discard": 0,
            "hidden": 0,
            "unknown": 0,
        },
    }


def _finalize(metrics: dict[str, Any]) -> dict[str, Any]:
    sent = metrics["sent"]
    states = metrics["states"]
    invitations = states["invitation"]
    discards = states["discard"]
    decisions = invitations + discards
    metrics["invitation_rate"] = round(invitations / sent, 4) if sent else None
    metrics["decision_rate"] = round(decisions / sent, 4) if sent else None
    metrics["invitation_given_decision"] = (
        round(invitations / decisions, 4) if decisions else None
    )
    return metrics


def _accumulate(metrics: dict[str, Any], row: sqlite3.Row) -> None:
    metrics["assigned"] += 1
    state = str(row["state"] or "unknown")
    effective_sent = row["send_status"] == "sent" or state in KNOWN_STATES
    if effective_sent:
        metrics["sent"] += 1
        metrics["states"][state if state in KNOWN_STATES else "unknown"] += 1
    elif row["send_status"] == "failed":
        metrics["send_failed"] += 1
    if bool(row["fallback_used"]):
        metrics["fallbacks"] += 1


def _read_profile(db_path: Path) -> dict[str, Any]:
    uri = f"file:{db_path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if not _table_exists(conn, "apply_experiment_assignments"):
            return {"experiments": {}}

        has_negotiations = _table_exists(conn, "negotiations")
        if has_negotiations:
            rows = conn.execute(
                """
                SELECT a.experiment, a.resume_variant, a.cover_variant,
                       a.cover_assigned_mode, a.cover_actual_mode,
                       a.fallback_used, a.send_status,
                       n.state AS state
                FROM apply_experiment_assignments AS a
                LEFT JOIN negotiations AS n
                  ON CAST(n.vacancy_id AS TEXT) = a.vacancy_id
                 AND n.resume_id = a.resume_id
                ORDER BY a.experiment, a.assigned_at
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT experiment, resume_variant, cover_variant,
                       cover_assigned_mode, cover_actual_mode,
                       fallback_used, send_status, NULL AS state
                FROM apply_experiment_assignments
                ORDER BY experiment, assigned_at
                """
            ).fetchall()
    finally:
        conn.close()

    experiments: dict[str, Any] = {}
    buckets: dict[str, dict[str, defaultdict[str, dict[str, Any]]]] = {}
    for row in rows:
        experiment = str(row["experiment"])
        if experiment not in buckets:
            buckets[experiment] = {
                "cover_letters": defaultdict(_new_metrics),
                "resumes": defaultdict(_new_metrics),
                "actual_cover_modes": defaultdict(_new_metrics),
            }
        _accumulate(buckets[experiment]["cover_letters"][row["cover_variant"]], row)
        _accumulate(buckets[experiment]["resumes"][row["resume_variant"]], row)
        _accumulate(
            buckets[experiment]["actual_cover_modes"][row["cover_actual_mode"]], row
        )

    for experiment, dimensions in buckets.items():
        experiments[experiment] = {
            dimension: {
                variant: _finalize(metrics)
                for variant, metrics in sorted(variants.items())
            }
            for dimension, variants in dimensions.items()
        }
    return {"experiments": experiments}


def build_report(config_dir: Path) -> dict[str, Any]:
    profiles: dict[str, Any] = {}
    totals = {"profiles": 0, "experiments": 0, "assignments": 0, "sent": 0}
    for profile, db_path in _profile_databases(config_dir):
        try:
            data = _read_profile(db_path)
            data["read_error"] = False
        except sqlite3.Error:
            data = {"experiments": {}, "read_error": True}
        profiles[profile] = data
        if data["experiments"]:
            totals["profiles"] += 1
            totals["experiments"] += len(data["experiments"])
            for experiment in data["experiments"].values():
                resume_metrics = experiment["resumes"].values()
                totals["assignments"] += sum(m["assigned"] for m in resume_metrics)
                totals["sent"] += sum(m["sent"] for m in resume_metrics)

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "cumulative_current_state",
        "privacy": {
            "aggregate_only": True,
            "resume_ids_included": False,
            "vacancy_ids_included": False,
            "letter_text_included": False,
            "vacancy_titles_included": False,
            "employer_names_included": False,
        },
        "totals": totals,
        "profiles": profiles,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2]
    parser.add_argument("--root", type=Path, default=root)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    config_dir = (
        args.config_dir.resolve()
        if args.config_dir
        else Path(os.environ.get("CONFIG_DIR", root / "config")).resolve()
    )
    output = (
        args.output.resolve() if args.output else (root / "ops" / "experiments.json")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_report(config_dir)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
