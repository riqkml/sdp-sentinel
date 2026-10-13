from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from .config import Settings

log = logging.getLogger(__name__)


class CollectorError(RuntimeError):
    """Raised when an external collector dependency cannot be used."""

    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type


class SdpCloudClient:
    def __init__(self, settings: Settings, session: requests.Session | None = None):
        self.settings = settings
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.manageengine.sdp.v3+json",
                "User-Agent": "sdp-cmdb-sentinel-mvp/0.1",
            }
        )

    def authenticate(self) -> None:
        try:
            response = self.session.post(
                self.settings.sdp_token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.settings.sdp_client_id,
                    "client_secret": self.settings.sdp_client_secret,
                    "refresh_token": self.settings.sdp_refresh_token,
                },
                timeout=self.settings.sdp_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise CollectorError("AuthError", f"Token request failed: {exc}") from exc

        try:
            body = response.json() if response.content else {}
        except ValueError as exc:
            raise CollectorError("AuthError", "Token endpoint returned invalid JSON") from exc

        access_token = body.get("access_token")
        if response.status_code != 200 or not access_token:
            reason = body.get("error") or body.get("message") or response.status_code
            raise CollectorError("AuthError", f"Token refresh failed: {reason}")

        self.session.headers.update(
            {"Authorization": f"Zoho-oauthtoken {access_token}"}
        )

    def list_ci(self, limit: int | None = None) -> list[dict[str, Any]]:
        url = f"{self.settings.sdp_api_base_url}/cmdb/{self.settings.sdp_ci_type}"
        start_index = 1
        records: list[dict[str, Any]] = []
        total_count: int | None = None

        while True:
            remaining = None if limit is None else max(limit - len(records), 0)
            if remaining == 0:
                break
            row_count = self.settings.sdp_page_size
            if remaining is not None:
                row_count = min(row_count, remaining)

            payload = self._get_page(
                url,
                {
                    "row_count": row_count,
                    "start_index": start_index,
                    "get_total_count": True,
                },
            )
            list_info = payload.get("list_info") or {}
            page_records = self._records(payload)
            records.extend(page_records)

            raw_total = list_info.get("total_count")
            if raw_total is not None:
                try:
                    total_count = int(raw_total)
                except (TypeError, ValueError) as exc:
                    raise CollectorError(
                        "ApiError", f"Invalid total_count from SDP: {raw_total!r}"
                    ) from exc

            has_more_rows = self._as_bool(list_info.get("has_more_rows"))
            if not has_more_rows:
                break
            if not page_records:
                raise CollectorError(
                    "ApiError", "SDP reported another page but returned no records"
                )
            start_index += row_count

        if limit is None and total_count is not None and total_count != len(records):
            raise CollectorError(
                "CountMismatch",
                f"{self.settings.sdp_ci_type}: expected {total_count}, got {len(records)}",
            )

        return records[:limit] if limit is not None else records

    def _get_page(self, url: str, list_info: dict[str, int | bool]) -> dict[str, Any]:
        params = {"input_data": json.dumps({"list_info": list_info})}
        last_status: int | None = None

        for attempt in range(self.settings.sdp_max_retries):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.settings.sdp_timeout_seconds,
                )
            except requests.RequestException as exc:
                if attempt + 1 == self.settings.sdp_max_retries:
                    raise CollectorError("ApiError", f"SDP request failed: {exc}") from exc
                self._backoff(attempt, "request error")
                continue

            last_status = response.status_code
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt + 1 == self.settings.sdp_max_retries:
                    break
                self._backoff(attempt, f"HTTP {response.status_code}")
                continue

            if response.status_code in (401, 403):
                raise CollectorError(
                    "AuthError", f"SDP returned HTTP {response.status_code}"
                )
            if response.status_code != 200:
                detail = response.text[:300].replace("\n", " ")
                raise CollectorError(
                    "ApiError", f"SDP returned HTTP {response.status_code}: {detail}"
                )

            try:
                body = response.json()
            except ValueError as exc:
                raise CollectorError("ApiError", "SDP returned invalid JSON") from exc
            if not isinstance(body, dict):
                raise CollectorError("ApiError", "SDP response must be a JSON object")
            return body

        raise CollectorError(
            "ApiError",
            f"SDP request retries exhausted (last status: {last_status})",
        )

    @staticmethod
    def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
        preferred_keys = ("ci_computer", "ci_computers", "data")
        for key in preferred_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

        for key, value in payload.items():
            if key in ("list_info", "response_status"):
                continue
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() == "true"

    @staticmethod
    def _backoff(attempt: int, reason: str) -> None:
        wait_seconds = 2**attempt
        log.warning("Retrying SDP request after %s; waiting %ss", reason, wait_seconds)
        time.sleep(wait_seconds)
