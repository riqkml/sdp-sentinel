from sdp_sentinel_mvp.transform import to_ticket_row


def test_to_ticket_row_maps_request_detail_fields():
    record = {
        "id": "req-1",
        "display_id": {"value": "REQ-1001"},
        "subject": "Laptop replacement",
        "status": {"name": "Open"},
        "priority": {"name": "High"},
        "category": {"name": "Hardware"},
        "subcategory": {"name": "Laptop"},
        "requester": {"name": "Sample User", "site": {"name": "Jakarta"}},
        "technician": {"name": "Sample Technician"},
        "assets": [{"id": "ci-1", "name": "LT-001"}],
        "created_time": {"value": "1735689600000"},
        "due_by_time": {"value": "1735776000000"},
        "last_updated_time": {"value": "1735689600000"},
        "is_overdue": False,
        "is_first_response_overdue": False,
    }

    row = to_ticket_row(
        record,
        "run-1",
        "2026-10-13T00:00:00+00:00",
    )

    assert row["TicketId"] == "req-1"
    assert row["TicketNumber"] == "REQ-1001"
    assert row["Status"] == "Open"
    assert row["Priority"] == "High"
    assert row["Requester"] == "Sample User"
    assert row["Site"] == "Jakarta"
    assert row["AssetCiId"] == "ci-1"
    assert row["AssetName"] == "LT-001"
    assert row["IsOpen"] is True
    assert row["IsOverdue"] is False
    assert len(row["RowHash"]) == 64
