"""A dead source is skipped with a visible note, never fatal."""

from intelligencer.config import Config, Dimension, Output, Publication, Source
from intelligencer.gather import build_manifest


def test_dead_feed_is_noted_not_fatal():
    cfg = Config(
        publication=Publication(title="T"),
        output=Output(),
        dimensions=[
            Dimension(name="D", sources=[Source(type="feed", url="file:///nonexistent/x.xml")])
        ],
    )
    manifest = build_manifest(cfg)
    dim = manifest.dimensions[0]
    assert dim.items == []
    assert dim.notes, "a dead source should leave a visible note"
