"""Trend store + heat computation (SPEC §10.2)."""

import pytest

from intelligencer.trends import TrendStore, direction, heat_tier, load_store, recurring, save_store


@pytest.mark.parametrize(
    "history, tier",
    [
        ([], 0),  # nothing
        ([5], 0),  # first appearance — nothing to be hotter than
        ([5, 5], 0),  # flat
        ([7, 3], 0),  # cooling
        ([3, 4], 1),  # small rise
        ([3, 6], 2),  # doubled
        ([3, 7], 2),  # +4 jump
        ([2, 4, 6, 8], 3),  # sustained strong climb (>=3 rising weeks, magnitude >=5)
        ([1, 2, 3, 4, 5], 3),
    ],
)
def test_heat_tier(history, tier):
    assert heat_tier(history) == tier


def test_direction_and_recurring():
    assert direction([3, 7]) == "up"
    assert direction([7, 3]) == "down"
    assert direction([5, 5]) == "flat"
    assert direction([5]) == "flat"
    assert recurring([5]) is False
    assert recurring([3, 7]) is True


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
