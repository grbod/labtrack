#!/usr/bin/env python3
"""Backfill immutable COA snapshots for already released COAs.

Dry-run is the default. Use ``--commit`` to write snapshot PDFs and rows.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session, joinedload  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.coa_release import COARelease  # noqa: E402
from app.models.coa_snapshot import COASnapshot  # noqa: E402
from app.models.enums import COAReleaseStatus  # noqa: E402
from app.services.coa_snapshot_service import create_snapshot  # noqa: E402


def run_backfill(db: Session, *, commit: bool = False) -> dict[str, Any]:
    """Backfill released COA releases that do not have a snapshot."""
    report: dict[str, Any] = {
        "mode": "commit" if commit else "dry-run",
        "releases_seen": 0,
        "snapshots_created": 0,
        "would_create": 0,
        "skipped": [],
    }

    releases = (
        db.query(COARelease)
        .options(
            joinedload(COARelease.lot),
            joinedload(COARelease.product),
            joinedload(COARelease.customer),
            joinedload(COARelease.released_by),
        )
        .filter(COARelease.status == COAReleaseStatus.RELEASED)
        .order_by(COARelease.released_at.asc(), COARelease.id.asc())
        .all()
    )

    for release in releases:
        report["releases_seen"] += 1
        existing = (
            db.query(COASnapshot)
            .filter(COASnapshot.coa_release_id == release.id)
            .first()
        )
        if existing is not None:
            report["skipped"].append(
                {
                    "release_id": release.id,
                    "reason": "snapshot already exists",
                }
            )
            continue

        if not commit:
            report["would_create"] += 1
            continue

        try:
            create_snapshot(db, release, reconstructed=True)
            report["snapshots_created"] += 1
        except ValueError as exc:
            report["skipped"].append(
                {
                    "release_id": release.id,
                    "reason": str(exc),
                }
            )

    if commit:
        db.commit()
    else:
        db.rollback()

    return report


def print_report(report: dict[str, Any]) -> None:
    """Print a stable reconciliation report."""
    print("COA Snapshot Backfill Report")
    print(f"mode: {report['mode']}")
    print(f"releases_seen: {report['releases_seen']}")
    print(f"snapshots_created: {report['snapshots_created']}")
    print(f"would_create: {report['would_create']}")
    print(f"skipped: {len(report['skipped'])}")
    for item in report["skipped"]:
        print(f"- release {item['release_id']}: {item['reason']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Write snapshot PDFs and rows. Default is dry-run.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = run_backfill(db, commit=args.commit)
        print_report(report)
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
