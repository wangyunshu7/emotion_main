import argparse
import json
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Activity, SupportResource
from app.schemas import ActivityImport, SupportImport


def load_content(path: Path, validate_only=False):
    files = sorted((path / "activities").glob("*.json"))
    support_files = sorted((path / "support").glob("*.json"))
    if not files and not support_files:
        raise ValueError("No JSON records found under activities/ or support/")
    records = []
    for file in files:
        data = json.loads(file.read_text(encoding="utf-8"))
        records.extend(
            ActivityImport.model_validate(item)
            for item in (data if isinstance(data, list) else [data])
        )
    if len({r.slug for r in records}) != len(records):
        raise ValueError("Duplicate slugs in input")
    support_records = []
    for file in support_files:
        data = json.loads(file.read_text(encoding="utf-8"))
        support_records.extend(
            SupportImport.model_validate(item)
            for item in (data if isinstance(data, list) else [data])
        )
    if validate_only:
        print(
            f"Validated {len(records)} activities and {len(support_records)} support records; no changes."
        )
        return
    with SessionLocal.begin() as db:
        for record in records:
            existing = db.scalar(select(Activity).where(Activity.slug == record.slug))
            data = record.model_dump()
            if existing and existing.status == "published":
                snapshot = {k: getattr(existing, k) for k in data}
                if snapshot == data:
                    continue
                if data["status"] == "archived" and all(
                    snapshot[k] == v for k, v in data.items() if k != "status"
                ):
                    existing.status = "archived"
                    continue
                raise ValueError(
                    f"Published activity {record.slug} is immutable; use a new versioned slug and archive old version"
                )
            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
            else:
                db.add(Activity(**data))
        for record in support_records:
            existing = db.scalar(
                select(SupportResource).where(
                    SupportResource.region_code == record.region_code,
                    SupportResource.title == record.title,
                )
            )
            if existing:
                for key, value in record.model_dump().items():
                    setattr(existing, key, value)
            else:
                db.add(SupportResource(**record.model_dump()))
    print(f"Imported {len(records)} activity records. Drafts remain unpublished.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    load_content(args.path.resolve(), args.validate_only)


if __name__ == "__main__":
    main()
