import logging
import sys
from pathlib import Path

import azure.functions as func

# The repository uses a src layout; Azure Functions loads this file from its root.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from sdp_sentinel_mvp.config import Settings
from sdp_sentinel_mvp.service import collect_snapshot
from sdp_sentinel_mvp.sentinel_sink import SentinelSink


logger = logging.getLogger(__name__)
app = func.FunctionApp()


@app.timer_trigger(
    schedule="0 0 * * * *",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def sdp_cmdb_sync(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logger.warning("The SDP CMDB timer trigger is past due.")

    settings = Settings.from_env(require_sentinel=True)
    rows, ticket_rows = collect_snapshot(
        settings,
        include_tickets=settings.sdp_tickets_enabled,
    )
    sink = SentinelSink(settings)
    uploaded_assets = sink.upload_assets(rows)
    uploaded_tickets = (
        sink.upload_tickets(ticket_rows) if settings.sdp_tickets_enabled else 0
    )
    logger.info(
        "Fetched %s CI records and uploaded %s assets; "
        "fetched %s tickets and uploaded %s tickets to Sentinel.",
        len(rows),
        uploaded_assets,
        len(ticket_rows),
        uploaded_tickets,
    )
