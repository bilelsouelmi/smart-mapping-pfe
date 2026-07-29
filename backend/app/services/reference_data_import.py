import csv
import logging
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.reference_data import ReferenceData

logger = logging.getLogger(__name__)

# backend/app/services/reference_data_import.py -> backend/dataset/
DATASET_DIR = Path(__file__).resolve().parent.parent.parent / "dataset"
CURRENCIES_CSV = DATASET_DIR / "lookup_currencies.csv"
COUNTRIES_CSV = DATASET_DIR / "lookup_country_codes.csv"


def _upsert(db: Session, category: str, code: str, name: str, meta: dict, updated_by: int) -> str:
    """Insert a new (category, code) row or update the existing one in
    place — never a duplicate, so re-running the import after the CSV
    gains a new row or a corrected name is always safe."""
    existing = db.query(ReferenceData).filter(
        ReferenceData.category == category,
        ReferenceData.code == code
    ).first()
    if existing:
        existing.name = name
        existing.meta_data = meta
        existing.updated_by = updated_by
        return "updated"
    db.add(ReferenceData(
        category=category, code=code, name=name,
        meta_data=meta, is_active=True, updated_by=updated_by,
    ))
    return "inserted"


def import_reference_data_csvs(db: Session, updated_by: int) -> dict:
    """Loads lookup_currencies.csv (-> ISO_CURRENCY) and
    lookup_country_codes.csv (-> COUNTRY) into ReferenceData. Caller is
    responsible for committing and audit-logging — this only stages the
    changes on the given session so both datasets land in one
    transaction."""
    result = {
        "currencies": {"inserted": 0, "updated": 0},
        "countries": {"inserted": 0, "updated": 0},
    }

    if CURRENCIES_CSV.exists():
        with open(CURRENCIES_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                meta = {
                    "symbol": row.get("currency_symbol") or None,
                    "to_eur_rate": float(row["to_eur_rate"]) if row.get("to_eur_rate") else None,
                    "to_usd_rate": float(row["to_usd_rate"]) if row.get("to_usd_rate") else None,
                    "decimal_places": int(row["decimal_places"]) if row.get("decimal_places") not in (None, "") else None,
                }
                outcome = _upsert(db, "ISO_CURRENCY", row["currency_code"], row["currency_name"], meta, updated_by)
                result["currencies"][outcome] += 1
    else:
        logger.warning(f"Currencies dataset not found at {CURRENCIES_CSV}")

    if COUNTRIES_CSV.exists():
        with open(COUNTRIES_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                meta = {
                    "iso3": row.get("country_code_iso3") or None,
                    "numeric_code": row.get("numeric_code") or None,
                }
                outcome = _upsert(db, "COUNTRY", row["country_code_iso2"], row["country_name"], meta, updated_by)
                result["countries"][outcome] += 1
    else:
        logger.warning(f"Countries dataset not found at {COUNTRIES_CSV}")

    return result
