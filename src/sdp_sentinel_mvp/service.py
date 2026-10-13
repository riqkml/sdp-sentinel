from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .config import Settings
from .sdp_client import SdpCloudClient
from .transform import to_asset_row


def collect_assets(
    settings: Settings, limit: int | None = None
) -> list[dict[str, Any]]:
    run_id = str(uuid.uuid4())
    run_timestamp = datetime.now(timezone.utc).isoformat()

    client = SdpCloudClient(settings)
    client.authenticate()
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
