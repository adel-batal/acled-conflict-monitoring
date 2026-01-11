from __future__ import annotations

import csv
import logging
from decimal import Decimal
from pathlib import Path
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.normalize import norm
from app.models import ConflictData

log = logging.getLogger("app.importer")


def _parse_int_optional(val: str) -> Optional[int]:
    v = val.strip()
    if not v:
        return None
    return int(v)


def import_sample_csv_if_empty(db: Session, csv_path: Path) -> None:
    existing = db.execute(select(func.count()).select_from(ConflictData)).scalar_one()
    if existing > 0:
        log.info("CSV import skipped (conflict_data already has rows)", extra={"rows": existing})
        return

    if not csv_path.exists():
        log.error("CSV import failed: file not found", extra={"path": str(csv_path)})
        return

    rows = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            country_raw = r["country"]
            admin1_raw = r["admin1"]

            events = int(r["events"])
            if events < 0:
                raise ValueError("events must be non-negative")

            rows.append(
                ConflictData(
                    country_raw=country_raw.strip(),
                    country_norm=norm(country_raw),
                    admin1_raw=admin1_raw.strip(),
                    admin1_norm=norm(admin1_raw),
                    population=_parse_int_optional(r.get("population", "")),
                    events=events,
                    score=Decimal(r["score"]),
                )
            )

    db.add_all(rows)
    db.commit()
    log.info("CSV import completed", extra={"inserted": len(rows), "path": str(csv_path)})
