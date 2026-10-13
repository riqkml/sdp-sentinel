from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import ConfigurationError, Settings
from .service import collect_assets
from .sdp_client import CollectorError
from .sentinel_sink import SentinelSink
from .transform import TransformError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pull SDP Cloud CMDB CI records and optionally send them to Sentinel."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--send",
        action="store_true",
        help="Upload transformed records to the configured Sentinel DCR.",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and transform records, but do not call Sentinel.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Only fetch this many records; useful for a safe connection test.",
    )
    parser.add_argument(
        "--output",
        default="data/assets-latest.json",
        help="Local JSON output path (default: data/assets-latest.json).",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    settings = Settings.from_env(require_sentinel=args.send)
    rows = collect_assets(settings, limit=args.limit)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if args.send:
        uploaded = SentinelSink(settings).upload_assets(rows)
        print(f"Fetched {len(rows)} CI records and uploaded {uploaded} to Sentinel.")
    else:
        print(f"Fetched and transformed {len(rows)} CI records. Sentinel upload skipped.")
    print(f"Local output: {output_path}")
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = _parser().parse_args()
    try:
        return run(args)
    except (ConfigurationError, CollectorError, TransformError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
