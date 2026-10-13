from __future__ import annotations

from typing import Any

from azure.core.exceptions import AzureError
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.monitor.ingestion import LogsIngestionClient

from .config import Settings
from .sdp_client import CollectorError


class SentinelSink:
    def __init__(self, settings: Settings):
        if not settings.sentinel_endpoint or not settings.sentinel_dcr_id:
            raise CollectorError(
                "ConfigError",
                "AZURE_DCR_ENDPOINT and AZURE_DCR_IMMUTABLE_ID are required for --send",
            )
        self.settings = settings
        if settings.azure_tenant_id:
            credential = ClientSecretCredential(
                tenant_id=settings.azure_tenant_id,
                client_id=settings.azure_client_id,
                client_secret=settings.azure_client_secret,
            )
        else:
            credential = DefaultAzureCredential()

        self.client = LogsIngestionClient(
            endpoint=settings.sentinel_endpoint,
            credential=credential,
        )

    def upload_assets(self, rows: list[dict[str, Any]]) -> int:
        uploaded = 0
        for start in range(0, len(rows), self.settings.sentinel_batch_size):
            batch = rows[start : start + self.settings.sentinel_batch_size]
            try:
                self.client.upload(
                    rule_id=self.settings.sentinel_dcr_id,
                    stream_name=self.settings.sentinel_stream_name,
                    logs=batch,
                )
            except AzureError as exc:
                raise CollectorError(
                    "IngestError",
                    f"Sentinel ingestion failed for batch starting at {start}: {exc}",
                ) from exc
            uploaded += len(batch)
        return uploaded
