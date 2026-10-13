from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .config import Settings
from .sdp_client import SdpCloudClient
from .transform import TransformError, to_asset_row, to_ticket_row


def _new_client(settings: Settings) -> SdpCloudClient:
    client = SdpCloudClient(settings)
    client.authenticate()
    return client


def _collect_assets(
    client: SdpCloudClient,
    settings: Settings,
    run_id: str,
    run_timestamp: str,
    limit: int | None,
) -> list[dict[str, Any]]:
    records = client.list_ci(limit=limit)
    return [
        to_asset_row(
            record,
            settings.sdp_ci_type,
            run_id,
            run_timestamp,
            settings,
        )
        for record in records
    ]


def _collect_tickets(
    client: SdpCloudClient,
    run_id: str,
    run_timestamp: str,
    limit: int | None,
) -> list[dict[str, Any]]:
    summaries = client.list_requests(limit=limit)
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        ticket_id = summary.get("id")
        if ticket_id is None:
            raise TransformError("Ticket record is missing id")
        detail = client.get_request(str(ticket_id))
        rows.append(to_ticket_row(detail, run_id, run_timestamp))
    return rows


def collect_assets(
    settings: Settings, limit: int | None = None
) -> list[dict[str, Any]]:
    run_id = str(uuid.uuid4())
    run_timestamp = datetime.now(timezone.utc).isoformat()
    return _collect_assets(
        _new_client(settings), settings, run_id, run_timestamp, limit
    )


def collect_tickets(
    settings: Settings, limit: int | None = None
) -> list[dict[str, Any]]:
    run_id = str(uuid.uuid4())
    run_timestamp = datetime.now(timezone.utc).isoformat()
    return _collect_tickets(
        _new_client(settings), run_id, run_timestamp, limit
    )


def collect_snapshot(
    settings: Settings,
    include_tickets: bool = False,
    asset_limit: int | None = None,
    ticket_limit: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    run_id = str(uuid.uuid4())
    run_timestamp = datetime.now(timezone.utc).isoformat()
    client = _new_client(settings)
    assets = _collect_assets(
        client, settings, run_id, run_timestamp, asset_limit
    )
    tickets = (
        _collect_tickets(client, run_id, run_timestamp, ticket_limit)
        if include_tickets
        else []
    )
    return assets, tickets
