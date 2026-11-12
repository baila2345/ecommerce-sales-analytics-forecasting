import hashlib
import json
from dataclasses import dataclass
from datetime import date

from app.modules.data_quality.rules import ML_QUALITY_POLICY_VERSION


DAILY_SALES_RULES_VERSION = "daily-sales-v2"
SOURCE_TIMEZONE = "source-local-brazil"
REQUIRED_DATASET_TYPES = (
    "customers",
    "sellers",
    "product_categories",
    "products",
    "orders",
    "order_items",
    "order_payments",
    "order_reviews",
    "geolocations",
)


@dataclass(frozen=True)
class FingerprintDescriptor:
    fingerprint: str
    source_checksums: dict[str, str]
    rules_version: str
    quality_policy_version: str
    source_timezone: str
    maturity_days: int
    source_min_date: date
    source_max_date: date


def build_fingerprint(
    source_checksums: dict[str, str],
    *,
    maturity_days: int,
    source_min_date: date,
    source_max_date: date,
) -> FingerprintDescriptor:
    ordered_checksums = {
        dataset_type: source_checksums[dataset_type]
        for dataset_type in REQUIRED_DATASET_TYPES
    }
    payload = {
        "source_checksums": ordered_checksums,
        "rules_version": DAILY_SALES_RULES_VERSION,
        "quality_policy_version": ML_QUALITY_POLICY_VERSION,
        "source_timezone": SOURCE_TIMEZONE,
        "maturity_days": maturity_days,
        "source_min_date": source_min_date.isoformat(),
        "source_max_date": source_max_date.isoformat(),
    }
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return FingerprintDescriptor(
        fingerprint=hashlib.sha256(canonical_payload).hexdigest(),
        source_checksums=ordered_checksums,
        rules_version=DAILY_SALES_RULES_VERSION,
        quality_policy_version=ML_QUALITY_POLICY_VERSION,
        source_timezone=SOURCE_TIMEZONE,
        maturity_days=maturity_days,
        source_min_date=source_min_date,
        source_max_date=source_max_date,
    )
