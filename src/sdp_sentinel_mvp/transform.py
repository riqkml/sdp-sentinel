from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .config import Settings


class TransformError(ValueError):
    """Raised when a CI record cannot be transformed safely."""


def _value(value: Any) -> Any:
    if isinstance(value, dict):
        if "name" in value:
            return value["name"]
        if "value" in value:
            return value["value"]
    return value


def _epoch_to_iso(value: Any) -> str | None:
    raw = value.get("value") if isinstance(value, dict) else value
    if raw in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def normalize_hostname(value: Any) -> str | None:
    if value is None:
        return None
    hostname = str(_value(value)).strip().lower()
    return hostname.split(".", 1)[0] if hostname else None


def to_asset_row(
    record: dict[str, Any],
    ci_type: str,
    run_id: str,
    run_timestamp: str,
    settings: Settings,
) -> dict[str, Any]:
    ci_id = record.get("id")
    if ci_id is None:
        raise TransformError("CI record is missing id")

    attributes = record.get("ci_attributes") or record.get("attributes") or {}
    if not isinstance(attributes, dict):
        attributes = {}

    name = _value(record.get("name"))
    site = record.get("site")
    if site is None and settings.sdp_site_field_key:
        site = attributes.get(settings.sdp_site_field_key)

    os_name = None
    if settings.sdp_os_field_key:
        os_name = attributes.get(settings.sdp_os_field_key)
    criticality = (
        record.get("business_impact")
        or record.get("impact")
        or attributes.get(settings.sdp_criticality_field_key)
    )
    status = (
        record.get("status")
        or record.get("lifecycle")
        or record.get("state")
        or attributes.get("status")
    )

    ip_address = attributes.get(settings.sdp_ip_field_key)
    row: dict[str, Any] = {
        "TimeGenerated": run_timestamp,
        "RunId": run_id,
        "CiId": str(ci_id),
        "CiType": _value(record.get("ci_type")) or ci_type,
        "CiName": name,
        "Description": _value(record.get("description")),
        "HostnameNorm": normalize_hostname(name),
        "IpAddress": _value(ip_address),
        "OsName": _value(os_name),
        "Site": _value(site),
        "Criticality": _value(criticality),
        "CiStatus": _value(status),
        "SourceCreatedTime": _epoch_to_iso(record.get("created_time")),
        "SourceLastUpdated": _epoch_to_iso(record.get("last_updated_time")),
        "RawAttributes": record,
    }

    hash_fields = (
        "CiName",
        "Description",
        "IpAddress",
        "OsName",
        "Site",
        "Criticality",
        "CiStatus",
    )
    hash_basis = json.dumps(
        {field: row.get(field) for field in hash_fields},
        sort_keys=True,
        default=str,
    )
    row["RowHash"] = hashlib.sha256(hash_basis.encode("utf-8")).hexdigest()
    return row
