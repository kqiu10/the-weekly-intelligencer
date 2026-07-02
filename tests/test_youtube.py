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
                "channelTitle": "AI Cinema",
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
        {
            "id": "aaa111",
            "statistics": {"viewCount": "12345678", "likeCount": "543210", "commentCount": "6083"},
        },
        # bbb222 intentionally absent -> no stats available
    ]
}


def test_map_results_builds_items_with_engagement_stats():
    items = map_results(SEARCH, VIDEOS, group="YouTube Shorts")
    assert len(items) == 2  # the id-less and blank-title entries are dropped

    first = items[0]
    assert first.title == "Insane AI-generated cat pilots a jet"
    assert first.url == "https://www.youtube.com/shorts/aaa111"
    assert first.source == "youtube.com"
    assert first.published == "2026-06-28"
    assert first.image == "https://i.ytimg.com/vi/aaa111/oardefault.jpg"  # portrait Short frame
    assert first.origin == "youtube"
    assert first.group == "YouTube Shorts"
    assert first.creator == "AI Cinema"  # channelTitle, overlaid on the tile
    assert first.stats == {"views": 12345678, "likes": 543210, "comments": 6083}
    assert first.raw_text == "Made with Sora. Goes viral."  # description only, no count prefix

    second = items[1]
    assert second.published == "2026-06-27"
    assert second.stats == {}  # missing statistics -> empty stats, no crash
    assert second.image == "https://i.ytimg.com/vi/bbb222/oardefault.jpg"


def test_fetch_youtube_without_key_is_a_no_op():
    # No key -> returns [] without any HTTP (the graceful-skip contract).
    for key in (None, ""):
        assert (
            fetch_youtube(
                "AI video", published_after="2026-06-24T00:00:00Z", max_results=6, api_key=key
            )
            == []
        )
