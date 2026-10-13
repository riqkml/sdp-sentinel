from sdp_sentinel_mvp.config import Settings
from sdp_sentinel_mvp.transform import normalize_hostname, to_asset_row


def test_normalize_hostname_removes_domain_and_lowercases():
    assert normalize_hostname(" SRV-01.EXAMPLE.COM ") == "srv-01"


def test_to_asset_row_maps_mvp_fields():
    settings = Settings(
        sdp_token_url="https://accounts.zoho.com/oauth/v2/token",
        sdp_api_base_url="https://sdpondemand.manageengine.com/api/v3",
        sdp_ci_type="ci_computers",
        sdp_client_id="id",
        sdp_client_secret="secret",
        sdp_refresh_token="refresh",
        sdp_ip_field_key="txt_ip_address",
        sdp_os_field_key="txt_os",
        sdp_site_field_key="site_key",
        sdp_criticality_field_key="ref_business_impact",
        sdp_page_size=100,
        sdp_timeout_seconds=30,
        sdp_max_retries=4,
        sentinel_endpoint="",
        sentinel_dcr_id="",
        sentinel_stream_name="Custom-SDP_CMDB_Asset",
        sentinel_batch_size=500,
    )
    record = {
        "id": "123",
        "name": "SRV-01.example.com",
        "description": "Test server",
        "ci_type": {"name": "Computer"},
        "site": {"name": "Jakarta"},
        "ci_attributes": {
            "txt_ip_address": "10.0.0.1",
            "txt_os": {"name": "Windows"},
        },
    }

    row = to_asset_row(record, "ci_computers", "run-1", "2026-10-12T00:00:00+00:00", settings)

    assert row["CiId"] == "123"
    assert row["CiType"] == "Computer"
    assert row["HostnameNorm"] == "srv-01"
    assert row["IpAddress"] == "10.0.0.1"
    assert row["OsName"] == "Windows"
    assert row["Site"] == "Jakarta"
    assert len(row["RowHash"]) == 64
