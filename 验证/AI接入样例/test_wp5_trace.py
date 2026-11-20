from check_trace import check_trace


def test_wp5_trace_has_no_missing_or_unknown_ids():
    assert check_trace() > 0
