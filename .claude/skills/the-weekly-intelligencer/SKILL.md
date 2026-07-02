---
name: the-weekly-intelligencer
description: Generate this week's issue of The Weekly Intelligencer — a New York Times–style AI-industry digest rendered as a self-contained HTML page. Use when the user asks to build, generate, or refresh the weekly AI issue. Deterministic feed/site sources are gathered by Python scripts (zero tokens); you fill `search` sources with web search and write the editorial summaries.
---

# The Weekly Intelligencer — issue orchestrator

You are producing **one weekly issue**. The deterministic work (RSS `feed` and `site`
sources) is done by Python scripts and costs no tokens — you only spend effort on
`search` sources and on writing summaries. Work from the project root and follow these
steps in order.

## 0. Preconditions
- Run `uv run intelligencer validate`. If it reports errors, stop and show them.
- Read `config/dimensions.yaml`. Note, per dimension: its `summary` mode
  (`raw` / `rewrite` / `synthesize`), its `max_items`, and any `search` sources (their
  `query`).

## 1. Gather deterministic sources (no tokens)
Run `uv run intelligencer fetch`. This writes `out/manifest.json` with the issue metadata
and the items already gathered from `feed`, `site` (scraped official newsrooms), and
`youtube` (the YouTube Data API — the YouTube Shorts card, when `YOUTUBE_API_KEY` is set)
sources. `search` sources contribute nothing yet — you fill them next.

## 2. Fill `search` sources (web search)
For each dimension that has a `search` source, use the **WebSearch** tool with that
source's `query`, scoped to the past week. Choose the most relevant items, up to the
dimension's `max_items`. Use **WebFetch** when you need to confirm the headline, link,
publisher, date, or preview image. Each item you add must have this exact shape:

```json
{"title": "...", "url": "https://...", "source": "domain.com",
 "published": "YYYY-MM-DD", "image": "https://... or null",
 "raw_text": "", "summary": "", "origin": "search", "group": ""}
```

Only use an `image` URL that is the article's real preview image (`og:image`). If you
can't find one, use `null`.

### The "Trending Social Video & Images" dimension
Surface the **1–2 most-popular** videos or images **per platform** this week — **any topic**
(not AI-only; AI-generated content counts only when it's genuinely among the most popular).
Each card is **metrics-forward**: show the post's real engagement counts in `stats`, not a
thumbnail (`image: null`). **Add an item only if you can record its real counts; if you can't
verify a popular post for a platform this week, skip that platform.**
- **YouTube** is filled by `fetch` (free official Data API) with the week's top videos, each
  already carrying `stats` = {views, likes, comments}. Keep the 1–2 most popular; leave `stats`
  as-is.
- **TikTok, Instagram, Facebook** (`type: search`) — no free trending API, so **you** find each
  platform's 1–2 most-popular posts by web search, open each post, and record its **visible**
  counts into `stats` (a TikTok → {likes, comments, saves, shares}; a photo → {likes, comments}).
  Set `group` to the platform label and `image: null`. Skip a platform if the numbers aren't
  verifiable.

## 3. Write summaries per the dimension's `summary` mode
- **`raw`** — leave `summary` empty (the feed/snippet text is shown as-is).
- **`rewrite`** — write a faithful 1–2 sentence NYT-style summary for each item.
- **`synthesize`** — write one combined 2–4 sentence editorial paragraph for the
  dimension and place it as the `summary` of that dimension's first item.

Apply the same mode to the deterministic (`feed`/`site`) items already in the manifest.

## 4. Patch the manifest
Rewrite `out/manifest.json` with the **Write** tool. Keep `issue` and every existing
item; add your `search` items into their dimensions; fill in summaries. Also:

- **Issue TL;DR** — write `issue.tldr`: a one-paragraph, ~`defaults.tldr_words` (≈100-word)
  executive summary of the whole issue across all dimensions (NYT briefing register). It may
  open with what's heating up this week.
- **Trend topics** — for each dimension with `trends: true` (the social-video one), add a
  `trends` list of the week's key contexts. For each: use the posts' titles + descriptions
  to write a canonical `descriptor` + `tags` of *what the media
  depicts*; assign a stable `id` by semantic-matching against recent descriptors already in
  `data/trends.json` — **reuse the same `id`** when it's the same context as a prior week so
  the streak builds; estimate a `magnitude` (distinct posts/sources found + real view counts
  where available) and list a few `samples` (permalinks). Leave `heat_tier`/`direction`/
  `recurring` out — step 5 computes them.

Preserve the schema exactly:

```
issue:      { date, title, subtitle, week, tldr }
dimensions: [ { name, blurb, summary_mode, layout, items: [ ... ], notes: [ ... ],
                logos: { ... }, trends: [ { id, descriptor, tags: [...], magnitude, samples: [...] } ] } ]
item:       { title, url, source, published, image, raw_text, summary, origin, group, stats }
            (stats: social-video only — {views,likes,comments,saves,shares} → the metrics row)
```

If a dimension's `layout` is `by-source`, items are rendered grouped by their `group`
field (one card per source) — set `group` on any item you add there, and a source that
yields nothing is simply skipped. Each card shows the source's logo and name in a left
rail; the `logos` map (group label → packaged logo path) is produced by `fetch` from the
config's per-source `logo` slug — **keep it as-is, don't hand-edit it.** For the default
`grid` layout, leave `group` as `""`.

## 5. Fold in the 🔥 trend signal
Run `uv run intelligencer trends`. This records each context's `magnitude` into the committed
`data/trends.json` time-series and annotates every trend topic with its `heat_tier` (0–3
flames), `direction`, and `recurring` flag by comparing against prior weeks. Commit
`data/trends.json` afterward so the history persists (trends need a few weeks to warm up) —
use a Conventional-Commits subject like `chore(trends): record week N magnitudes` (a bare
`data:` type is rejected by the commit-message hook).

## 6. Render
Run `uv run intelligencer render` (add `--open` to open it). Report the output path,
e.g. `dist/2026-06-26.html`.

## Boundaries (non-negotiable)
- **Attribute everything.** Every item links to a real source you actually found.
- **Never fabricate** headlines, quotes, numbers, dates, or links. If you can't verify
  it, drop it.
- **No AI-generated images** — only a real article preview image, or `null`. (The social-video
  dimension is metrics-forward: its items carry `stats`, not pictures, so use `image: null`.)
- **Never call the Anthropic API** — all writing happens here in this session.
- **Social posts & hotness:** link the real permalink; never fabricate a post, a view count,
  or a virality/hotness figure — the 🔥 signal is an editorial estimate over time, not
  measured analytics.
