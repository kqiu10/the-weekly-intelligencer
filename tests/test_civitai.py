"""Civitai images API source (SPEC §10.1): mapping, NSFW filter, graceful keyless skip."""

import httpx
import pytest

from intelligencer.civitai import fetch_civitai, map_images

SAMPLE = {
    "items": [
        {
            "id": 111,
            "url": "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/aaa/width=450/1.jpeg",
            "nsfw": False,
            "nsfwLevel": "None",
            "createdAt": "2026-07-03T12:34:56.000Z",
            "postId": 900,
            "stats": {
                "likeCount": 5100,
                "heartCount": 1200,
                "commentCount": 44,
                "laughCount": 10,
                "cryCount": 2,
            },
            "meta": {"prompt": "a photorealistic cyberpunk cat piloting a fighter jet, 8k"},
            "username": "artist_one",
        },
        {
            # NSFW-flagged → must never reach the issue, regardless of the request filter
            "id": 222,
            "url": "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/bbb/width=450/2.jpeg",
            "nsfw": True,
            "nsfwLevel": "Mature",
            "createdAt": "2026-07-02T00:00:00.000Z",
            "stats": {"likeCount": 9000, "commentCount": 1},
            "meta": {"prompt": "x"},
            "username": "artist_two",
        },
        {
            # missing url → dropped (nothing to show on a portrait tile)
            "id": 333,
            "nsfw": False,
            "nsfwLevel": "None",
            "createdAt": "2026-07-01T00:00:00.000Z",
            "stats": {},
            "username": "artist_three",
        },
    ],
    "metadata": {"nextCursor": None},
}


def test_map_images_maps_fields_and_drops_nsfw_and_imageless():
    items = map_images(SAMPLE)
    assert len(items) == 1  # NSFW + imageless dropped
    it = items[0]
    assert it.url == "https://civitai.com/images/111"  # links to the image page
    assert it.image.startswith("https://image.civitai.com/")  # real hosted image
    assert it.published == "2026-07-03"
    assert it.creator == "artist_one"
    assert it.origin == "civitai"
    assert it.group == "Civitai"
    assert it.stats == {"likes": 5100, "comments": 44}
    # the creator's own prompt doubles as title + raw_text (never an invented headline)
    assert it.title.startswith("a photorealistic cyberpunk cat")
    assert "cyberpunk cat" in it.raw_text


def test_fetch_without_key_is_a_no_op_with_no_http(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("no HTTP call may happen without an api key")

    monkeypatch.setattr(httpx, "Client", boom)
    assert fetch_civitai(max_results=10, api_key=None) == []


def test_fetch_requests_safe_week_most_reactions(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return SAMPLE

    class FakeClient:
        def __init__(self, *a, **k):
            captured["headers"] = k.get("headers", {})

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            captured["url"] = url
            captured["params"] = params or {}
            return FakeResp()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    items = fetch_civitai(max_results=10, api_key="secret-key")
    assert len(items) == 1
    assert "civitai.com/api/v1/images" in captured["url"]
    assert captured["params"]["sort"] == "Most Reactions"
    assert captured["params"]["period"] == "Week"
    assert captured["params"]["nsfw"] == "None"  # safe-rated only, at the API level
    assert captured["headers"]["Authorization"] == "Bearer secret-key"


@pytest.mark.parametrize("bad_level", ["Soft", "Mature", "X"])
def test_defensive_nsfw_drop_even_if_api_leaks(bad_level):
    sample = {
        "items": [
            {
                "id": 5,
                "url": "https://image.civitai.com/x/5.jpeg",
                "nsfw": False,  # claims safe…
                "nsfwLevel": bad_level,  # …but level says otherwise → drop
                "createdAt": "2026-07-03T00:00:00.000Z",
                "stats": {},
                "username": "u",
            }
        ]
    }
    assert map_images(sample) == []
