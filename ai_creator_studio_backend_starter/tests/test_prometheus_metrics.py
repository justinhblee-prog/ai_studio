"""B-22: the Prometheus text exposition of the operational snapshot (escaping, optional parts, the 'status:phase' keys)."""
from app.services.prometheus_metrics import _label, render_operational_metrics


def test_an_empty_snapshot_still_renders_the_header_and_ends_with_a_newline():
    text = render_operational_metrics({})
    assert text.endswith("\n") and text.splitlines() == ["# HELP acs_worker_healthy Worker heartbeat health (1=healthy).", "# TYPE acs_worker_healthy gauge"]


def test_labels_are_escaped_so_a_value_cannot_break_out_of_its_quotes():
    assert _label('a"b\\c\nd') == 'a\\"b\\\\c\\nd' and _label(7) == "7"
    text = render_operational_metrics({"workers": [{"worker_type": 'x"} 1\n# evil', "healthy": True}]})
    assert 'worker_type="x\\"} 1\\n# evil"' in text and "\n# evil" not in text


def test_workers_outbox_and_poll_counts():
    text = render_operational_metrics({"workers": [{"worker_type": "outbox", "healthy": True}, {"worker_type": "poll", "healthy": False}, {}],
                                       "outbox_counts": {"pending": 3, "done": 10},
                                       "poll_task_counts": {"pending:submit": 2, "failed": 1}})
    lines = text.splitlines()
    assert 'acs_worker_healthy{worker_type="outbox"} 1' in lines and 'acs_worker_healthy{worker_type="poll"} 0' in lines and 'acs_worker_healthy{worker_type="unknown"} 0' in lines
    assert lines.index('acs_outbox_tasks{status="done"} 10') < lines.index('acs_outbox_tasks{status="pending"} 3'), "sorted by status"
    assert 'acs_poll_tasks{status="pending",phase="submit"} 2' in lines and 'acs_poll_tasks{status="failed",phase="unknown"} 1' in lines


def test_ages_are_printed_only_when_known_and_alerts_split_status_and_severity():
    text = render_operational_metrics({"oldest_pending_outbox_age_seconds": 12.3456, "oldest_pending_poll_age_seconds": None,
                                       "alerts": {"open:critical": 2, "ack": 1}})
    lines = text.splitlines()
    assert "acs_oldest_pending_outbox_age_seconds 12.346" in lines and not any(line.startswith("acs_oldest_pending_poll_age_seconds") for line in lines)
    assert 'acs_ops_alerts{status="open",severity="critical"} 2' in lines and 'acs_ops_alerts{status="ack",severity="unknown"} 1' in lines
