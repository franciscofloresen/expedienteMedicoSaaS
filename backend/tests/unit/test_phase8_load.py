from scripts.run_phase8_load import _local_target, percentile, summarize


def test_percentile_uses_nearest_rank() -> None:
    assert percentile([10, 20, 30, 40], 0.50) == 20
    assert percentile([10, 20, 30, 40], 0.99) == 40


def test_summary_enforces_roadmap_slo() -> None:
    passing = summarize([100.0] * 99 + [1200.0], errors=0, elapsed=10)
    assert passing.passed is True
    failing = summarize([100.0] * 98 + [3200.0, 3500.0], errors=2, elapsed=10)
    assert failing.passed is False


def test_load_target_is_strictly_local() -> None:
    assert _local_target("http://127.0.0.1:8000") is True
    assert _local_target("http://localhost:8000") is True
    assert _local_target("https://api.cloudmedrecord.com") is False
