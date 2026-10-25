"""Assignments feed parser (Blackboard / Gradescope calendar links). No network: text in, items out."""
import assignments

FEED = (
    "BEGIN:VCALENDAR\r\n"
    "BEGIN:VEVENT\r\nUID:abc\r\nSUMMARY:Problem Set 4\\, part 1\r\nDTSTART:20261101T235900Z\r\nCATEGORIES:CS 111\r\nEND:VEVENT\r\n"
    "BEGIN:VEVENT\r\nUID:long\r\nSUMMARY:A very long title that the calendar\r\n  program folded onto a second line\r\nDTSTART;VALUE=DATE:20261102\r\nEND:VEVENT\r\n"
    "BEGIN:VEVENT\r\nUID:nodate\r\nSUMMARY:No due date\r\nEND:VEVENT\r\n"
    "BEGIN:VTODO\r\nUID:todo\r\nSUMMARY:Reading\r\nDUE;TZID=America/New_York:20261103T170000\r\nEND:VTODO\r\n"
    "END:VCALENDAR\r\n"
)


def test_parse_ics_reads_events_and_todos_and_skips_undated_ones():
    items = assignments.parse_ics(FEED, "Blackboard")
    titles = [i["title"] for i in items]
    assert titles == ["Problem Set 4, part 1", "A very long title that the calendar program folded onto a second line", "Reading"]
    assert items[0]["course"] == "CS 111" and items[0]["all_day"] is False and items[0]["source"] == "Blackboard"
    assert items[1]["all_day"] is True  # a date without a time is an all-day item
    assert items[2]["due"].startswith("2026-11-03T17:00:00")  # TZID respected


def test_with_no_feed_links_a_labelled_sample_list_is_returned(monkeypatch):
    monkeypatch.setenv("BLACKBOARD_ICS_URL", "")
    monkeypatch.setenv("GRADESCOPE_ICS_URL", "")
    result = assignments.upcoming(days=14)
    assert result["sample"] is True and result["feeds"] == {"Blackboard": "not_set", "Gradescope": "not_set"}
