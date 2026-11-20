"""API timestamps must carry an explicit UTC offset so browsers convert them to local time."""

from datetime import UTC, datetime

from app.models.schema import ActivityLogOut


def test_naive_datetimes_are_serialized_as_utc():
    out = ActivityLogOut(id=1, event_type="x", message="m", created_at=datetime(2026, 1, 2, 3, 4, 5))
    assert out.model_dump_json().count("2026-01-02T03:04:05Z") == 1


def test_activity_endpoint_returns_utc_offsets(client, admin_headers):
    entries = client.get("/activity/", headers=admin_headers).json()
    assert entries, "logging in should have produced an activity entry"
    parsed = datetime.fromisoformat(entries[0]["created_at"].replace("Z", "+00:00"))
    assert parsed.tzinfo is not None and parsed.utcoffset() == UTC.utcoffset(None)
    assert abs((datetime.now(UTC) - parsed).total_seconds()) < 3600
