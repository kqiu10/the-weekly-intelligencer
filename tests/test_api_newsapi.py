"""C1: NewsAPI source — mapping, hard daily cap, response cache, fail-soft. All mocked."""

import json
from pathlib import Path

from intelligencer.providers.newsapi import NewsApiClient


def _fake_response(n=2):
    return {
        "articles": [
            {
                "title": f"Headline {i}",
                "url": f"https://ex/{i}",
                "source": {"name": "Ex"},
                "publishedAt": "2026-06-25T00:00:00Z",
                "description": f"desc {i}",
                "urlToImage": f"https://ex/{i}.jpg",
            }
            for i in range(n)
        ]
    }


class FakeFetch:
    def __init__(self, payload=None, exc=None):
        self.calls = 0
        self.payload = payload if payload is not None else _fake_response()
        self.exc = exc

    def __call__(self, query, page_size):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.payload


def test_mocked_fetch_returns_items(tmp_path):
    fetch = FakeFetch()
    client = NewsApiClient(api_key="k", daily_limit=100, work_dir=tmp_path, fetch_json=fetch)
    res = client.fetch("ai")
    assert len(res.items) == 2
    assert res.items[0].title == "Headline 0"
    assert res.items[0].origin == "api"
    assert res.items[0].image == "https://ex/0.jpg"
    assert fetch.calls == 1


def test_daily_limit_is_hard(tmp_path):
    fetch = FakeFetch()
    client = NewsApiClient(api_key="k", daily_limit=2, work_dir=tmp_path, fetch_json=fetch)
    assert client.fetch("q1").items
    assert client.fetch("q2").items
    blocked = client.fetch("q3")
    assert blocked.items == []
    assert "limit" in (blocked.note or "").lower()
    assert fetch.calls == 2  # third request never hit the network


def test_cache_hit_does_not_increment(tmp_path):
    fetch = FakeFetch()
    client = NewsApiClient(api_key="k", daily_limit=100, work_dir=tmp_path, fetch_json=fetch)
    client.fetch("same")
    client.fetch("same")  # served from cache
    assert fetch.calls == 1
    usage = json.loads((Path(tmp_path) / "newsapi_usage.json").read_text())
    assert usage["count"] == 1


def test_missing_key_skips(tmp_path):
    fetch = FakeFetch()
    client = NewsApiClient(api_key="", daily_limit=100, work_dir=tmp_path, fetch_json=fetch)
    res = client.fetch("q")
    assert res.items == []
    assert res.note
    assert fetch.calls == 0


def test_request_failure_is_noted(tmp_path):
    fetch = FakeFetch(exc=RuntimeError("boom"))
    client = NewsApiClient(api_key="k", daily_limit=100, work_dir=tmp_path, fetch_json=fetch)
    res = client.fetch("q")
    assert res.items == []
    assert "failed" in (res.note or "").lower()
    assert fetch.calls == 1
