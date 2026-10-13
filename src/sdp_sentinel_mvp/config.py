from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Raised when required collector configuration is missing or invalid."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"Missing required environment variable: {name}")
    return value


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True)
class Settings:
    sdp_token_url: str
    sdp_api_base_url: str
    sdp_ci_type: str
    sdp_client_id: str
    sdp_client_secret: str
    sdp_refresh_token: str
    sdp_ip_field_key: str
    sdp_os_field_key: str
    sdp_site_field_key: str
    sdp_criticality_field_key: str
    sdp_page_size: int
    sdp_timeout_seconds: int
    sdp_max_retries: int
    sentinel_endpoint: str
    sentinel_dcr_id: str
    sentinel_stream_name: str
    sentinel_batch_size: int
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""

    @classmethod
    def from_env(cls, require_sentinel: bool = False) -> "Settings":
        load_dotenv()

        sentinel_endpoint = os.getenv("AZURE_DCR_ENDPOINT", "").strip()
        sentinel_dcr_id = os.getenv("AZURE_DCR_IMMUTABLE_ID", "").strip()
        if require_sentinel and not sentinel_endpoint:
            raise ConfigurationError("Missing required environment variable: AZURE_DCR_ENDPOINT")
        if require_sentinel and not sentinel_dcr_id:
            raise ConfigurationError(
                "Missing required environment variable: AZURE_DCR_IMMUTABLE_ID"
            )

        azure_tenant_id = os.getenv("AZURE_TENANT_ID", "").strip()
        azure_client_id = os.getenv("AZURE_CLIENT_ID", "").strip()
        azure_client_secret = os.getenv("AZURE_CLIENT_SECRET", "").strip()
        azure_credentials = (azure_tenant_id, azure_client_id, azure_client_secret)
        if any(azure_credentials) and not all(azure_credentials):
            raise ConfigurationError(
                "AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET "
                "must be provided together"
            )

        return cls(
            sdp_token_url=_required("SDP_TOKEN_URL"),
            sdp_api_base_url=_required("SDP_API_BASE_URL").rstrip("/"),
            sdp_ci_type=_required("SDP_CI_TYPE"),
            sdp_client_id=_required("SDP_CLIENT_ID"),
            sdp_client_secret=_required("SDP_CLIENT_SECRET"),
            sdp_refresh_token=_required("SDP_REFRESH_TOKEN"),
            sdp_ip_field_key=os.getenv("SDP_IP_FIELD_KEY", "txt_ip_address").strip(),
            sdp_os_field_key=os.getenv("SDP_OS_FIELD_KEY", "txt_os").strip(),
            sdp_site_field_key=os.getenv("SDP_SITE_FIELD_KEY", "txt_location").strip(),
            sdp_criticality_field_key=os.getenv(
                "SDP_CRITICALITY_FIELD_KEY", "ref_business_impact"
            ).strip(),
            sdp_page_size=_positive_int("SDP_PAGE_SIZE", 100),
            sdp_timeout_seconds=_positive_int("SDP_TIMEOUT_SECONDS", 30),
            sdp_max_retries=_positive_int("SDP_MAX_RETRIES", 4),
            sentinel_endpoint=sentinel_endpoint,
            sentinel_dcr_id=sentinel_dcr_id,
            sentinel_stream_name=os.getenv(
                "AZURE_DCR_STREAM_NAME", "Custom-SDP_CMDB_Asset"
            ).strip(),
            sentinel_batch_size=_positive_int("SENTINEL_BATCH_SIZE", 500),
            azure_tenant_id=azure_tenant_id,
            azure_client_id=azure_client_id,
            azure_client_secret=azure_client_secret,
        )
