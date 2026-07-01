"""Trend store + heat computation (SPEC §10.2)."""

from intelligencer.trends import TrendStore, load_store, save_store


def test_store_round_trips_records_and_reloads(tmp_path):
    p = tmp_path / "trends.json"
    assert load_store(p).topics == []  # missing file → empty store
    store = TrendStore()
    store.record(
        "t1", "AI cats flying jets", ["cats"], week=2, issue_date="2026-06-29", magnitude=3
    )
    store.record(
        "t1", "AI cats flying jets", ["cats"], week=3, issue_date="2026-07-06", magnitude=7
    )
    save_store(store, p)
    back = load_store(p)
    assert back.magnitudes("t1") == [3, 7]
    assert back.get("t1").descriptor == "AI cats flying jets"


def test_record_same_week_updates_in_place(tmp_path):
    store = TrendStore()
    store.record("t1", "d", [], week=3, issue_date="2026-07-06", magnitude=3)
    store.record("t1", "d", [], week=3, issue_date="2026-07-06", magnitude=9)  # rerun same issue
    assert store.magnitudes("t1") == [9]
