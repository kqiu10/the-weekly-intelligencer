"""YouTube Data API source: pure JSON→Item mapping + graceful skip (SPEC §3/§10.1)."""

from intelligencer.youtube import fetch_youtube, map_results

SEARCH = {
    "items": [
        {
            "id": {"videoId": "aaa111"},
            "snippet": {
                "publishedAt": "2026-06-28T12:00:00Z",
                "title": "Insane AI-generated cat pilots a jet",
                "description": "Made with Sora. Goes viral.",
            },
        },
        {
            "id": {"videoId": "bbb222"},
            "snippet": {
                "publishedAt": "2026-06-27T08:30:00Z",
                "title": "AI World Cup crowd deepfake",
                "description": "",
            },
        },
        {"id": {}, "snippet": {"title": "no video id -> dropped"}},
        {"id": {"videoId": "ccc333"}, "snippet": {"title": "   "}},  # blank title -> dropped
    ]
}

VIDEOS = {
    "items": [
        {"id": "aaa111", "statistics": {"viewCount": "12345678"}},
        # bbb222 intentionally absent -> no view count available
    ]
}


def test_map_results_builds_items_with_thumbnails_and_view_counts():
    items = map_results(SEARCH, VIDEOS, group="YouTube Shorts")
    assert len(items) == 2  # the id-less and blank-title entries are dropped

    first = items[0]
    assert first.title == "Insane AI-generated cat pilots a jet"
    assert first.url == "https://www.youtube.com/watch?v=aaa111"
    assert first.source == "youtube.com"
    assert first.published == "2026-06-28"
    assert first.image == "https://i.ytimg.com/vi/aaa111/hqdefault.jpg"
    assert first.origin == "youtube"
    assert first.group == "YouTube Shorts"
    assert "12,345,678 views" in first.raw_text  # real count folded in for the trend signal
    assert "Sora" in first.raw_text

    second = items[1]
    assert second.published == "2026-06-27"
    assert "views" not in second.raw_text  # missing statistics -> no count, no crash


def test_fetch_youtube_without_key_is_a_no_op():
    # No key -> returns [] without any HTTP (the graceful-skip contract).
    for key in (None, ""):
        assert (
            fetch_youtube(
                "AI video", published_after="2026-06-24T00:00:00Z", max_results=6, api_key=key
            )
            == []
        )
