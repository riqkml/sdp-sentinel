from __future__ import annotations

import hashlib
import ipaddress
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
    if not hostname:
        return None
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return hostname.split(".", 1)[0]
    return None


def _is_ip_address(value: Any) -> bool:
    if value in (None, ""):
        return False
    try:
        ipaddress.ip_address(str(_value(value)).strip())
    except ValueError:
        return False
    return True


def _string(value: Any) -> str | None:
    value = _value(value)
    if value in (None, ""):
        return None
    return str(value)


def _boolean_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _person_name(value: Any) -> str | None:
    if not isinstance(value, dict):
        return _string(value)
    name = value.get("name")
    if name:
        return _string(name)
    parts = [value.get("first_name"), value.get("last_name")]
    return " ".join(str(part).strip() for part in parts if part).strip() or None


def _asset_reference(record: dict[str, Any]) -> tuple[str | None, str | None]:
    assets = record.get("assets") or record.get("asset")
    if isinstance(assets, dict):
        assets = [assets]
    if not isinstance(assets, list):
        return None, None

    for asset in assets:
        if not isinstance(asset, dict):
            continue
        asset_id = asset.get("id") or asset.get("ci_id")
        asset_name = asset.get("name") or asset.get("display_name")
        if asset_id is not None or asset_name is not None:
            return _string(asset_id), _string(asset_name)
    return None, None


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

    ip_address = _value(attributes.get(settings.sdp_ip_field_key))
    if not _is_ip_address(ip_address) and _is_ip_address(name):
        ip_address = name
    row: dict[str, Any] = {
        "TimeGenerated": run_timestamp,
        "RunId": run_id,
        "CiId": str(ci_id),
        "CiType": _value(record.get("ci_type")) or ci_type,
        "CiName": name,
        "Description": _value(record.get("description")),
        "HostnameNorm": normalize_hostname(name),
        "IpAddress": ip_address,
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


def to_ticket_row(
    record: dict[str, Any],
    run_id: str,
    run_timestamp: str,
) -> dict[str, Any]:
    ticket_id = record.get("id")
    if ticket_id is None:
        raise TransformError("Ticket record is missing id")

    status = _string(record.get("status"))
    is_open = status not in {None, "Closed", "Resolved", "Cancelled"}
    is_overdue = _boolean_value(record.get("is_overdue"))
    sla_breached = _boolean_value(
        record.get("is_first_response_overdue") or record.get("is_overdue")
    )
    asset_ci_id, asset_name = _asset_reference(record)
    site = record.get("site")
    if site is None:
        requester = record.get("requester")
        if isinstance(requester, dict):
            site = requester.get("site")
    if site is None:
        group = record.get("group")
        if isinstance(group, dict):
            site = group.get("site")

    row: dict[str, Any] = {
        "TimeGenerated": run_timestamp,
        "RunId": run_id,
        "TicketId": str(ticket_id),
        "TicketNumber": _string(record.get("display_id") or record.get("display_key")),
        "Subject": _string(record.get("subject")),
        "Status": status,
        "Priority": _string(record.get("priority")),
        "Category": _string(record.get("category")),
        "Subcategory": _string(record.get("subcategory")),
        "Requester": _person_name(record.get("requester")),
        "Technician": _person_name(record.get("technician")),
        "Site": _string(site),
        "AssetCiId": asset_ci_id,
        "AssetName": asset_name,
        "CreatedTime": _epoch_to_iso(record.get("created_time")),
        "DueTime": _epoch_to_iso(record.get("due_by_time")),
        "ResolvedTime": _epoch_to_iso(
            record.get("resolved_time") or record.get("completed_time")
        ),
        "LastUpdatedTime": _epoch_to_iso(record.get("last_updated_time")),
        "IsOpen": is_open,
        "IsOverdue": is_overdue,
        "SlaBreached": sla_breached,
        "ChangeType": "Snapshot",
        "RawAttributes": record,
    }

    hash_fields = (
        "TicketNumber",
        "Subject",
        "Status",
        "Priority",
        "Category",
        "Subcategory",
        "Requester",
        "Technician",
        "Site",
        "AssetCiId",
        "AssetName",
        "CreatedTime",
        "DueTime",
        "ResolvedTime",
        "LastUpdatedTime",
        "IsOpen",
        "IsOverdue",
        "SlaBreached",
    )
    hash_basis = json.dumps(
        {field: row.get(field) for field in hash_fields},
        sort_keys=True,
        default=str,
    )
    row["RowHash"] = hashlib.sha256(hash_basis.encode("utf-8")).hexdigest()
    return row
