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

### The "Intelligent Factory" dimension
Surface stories of a named industrial/manufacturing company **adopting** a major AI
vendor's technology — a signed partnership, a live deployment, a disclosed expansion. The
`feed` candidates are **not** pre-filtered — Google News keyword matching is a broad, cheap
net, not an editorial judgment — so **prune them** with the same bar below before counting
them, the same way the YouTube Shorts candidates get pruned to the genuinely AI-generated
ones. Add at most 2–3 `search` items on top of whatever survives pruning; never pad to
reach `max_items`, and ending up with **zero** in a quiet week is correct, not a failure.
- **Qualify:** the AI side is a major AI vendor — OpenAI, Anthropic, Google DeepMind, xAI,
  Meta, DeepSeek, Qwen, Microsoft, NVIDIA, or another frontier/infrastructure AI company.
  This is **broader** than the Frontier AI Research Labs dimension's own roster above — this
  beat is about frontier AI landing in the wider economy, not limited to which labs that
  other dimension happens to track. The industry side must be a **named**
  manufacturer/industrial company **adopting** that AI for its own operations; the story
  must describe a **concrete action** (deal signed, product shipped, deployment live,
  results disclosed) with an on-record source — an executive quote, an official press
  release, or a reputable outlet naming its sources. HP × OpenAI's "Frontier" partnership is
  the reference example.
- **Reject — confirmed false-positive patterns from this feed, watch for these
  specifically:** (1) an AI vendor **sourcing** hardware/chip manufacturing for *itself*
  (e.g. "Anthropic in talks with Samsung to manufacture a custom AI chip") — that's supply
  chain, the AI vendor is the *customer*, the wrong direction entirely; (2) NVIDIA-branded
  **"AI Factory"** data-center/compute-campus stories — marketing language for a GPU data
  center, not a real factory adopting AI. Also reject opinion/thought-leadership pieces,
  market-size forecasts, conference/webinar announcements, unconfirmed ("sources say")
  reports, and anything where "AI" is a passing mention rather than the substance of the
  story.
- **Verify with WebFetch** before adding: confirm the named companies, that the date is
  inside the issue window, and that the link resolves to the real article, not a
  redirect/paywall stub.
- **Dedup** against this issue's Frontier AI Research Labs dimension — if the same
  announcement already appears there (e.g. the lab's own newsroom post), don't add it
  again here; this dimension is for the industry-adoption angle, usually reported by
  business/trade press or the customer company, not the lab's own blog.
- **Silently** skip when nothing verifiable qualifies — leave `notes` empty, same as the
  social platforms below. `group` stays `""` (grid layout, not by-source).

### The "Trending Social Video & Images" dimension
Surface the **1–2 most-shared AI-generated** videos/images **per platform** this week — the ones
newly going viral (recently posted, spiking now, not evergreen). Every card is a **portrait media
tile**: the post's thumbnail with its **creator**, **title**, and **likes + comments** overlaid on
the image (like the native app); the text beside it is the editorial `summary` only.
- **YouTube** is filled by `fetch` (free official Data API) with the week's most-viewed Shorts
  matching "AI generated" — each a `youtube.com/shorts/` link with an `i.ytimg` thumbnail, `creator`
  (channel name), and `stats` = {views, likes, comments}. **Prune** to the genuinely **AI-generated**
  ones (drop the rest, down to `max_per_source`); leave the fields as-is.
- **TikTok, Instagram, Facebook** (`type: search`) — find each platform's 1–2 **AI-generated
  entertainment** posts going viral this week (funny / creative / artful clips or images — **not**
  misinformation, violence, gore, or harmful deepfakes). The live pages are login-gated, so when you
  can, take the **thumbnail from the post's *coverage*** (a roundup/write-up that embeds a still) and
  set `image` to that article's `og:image`/still (`cache` downloads it). But a thumbnail is
  **optional** — if a genuinely popular AI post has no usable image, **still include it** (it renders
  in the standard by-source card, no portrait tile). For each set the post permalink (`url`),
  `creator` (@handle), `group` = platform, a short `summary` (mention its reach), and `stats`
  (likes / comments) only if stated. **Silently** skip a platform with no verifiable AI-gen
  entertainment hit — leave `notes` empty; never add a note explaining the absence.

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
item:       { title, url, source, published, image, raw_text, summary, origin, group, creator, stats }
            (social-video only — creator: @handle/channel; stats: {views,likes,comments,…} → overlaid on the tile)
```

If a dimension's `layout` is `by-source`, items are rendered grouped by their `group`
field (one card per source) — set `group` on any item you add there, and a source that
yields nothing is simply skipped. Each card shows the source's logo and name in a left
rail; the `logos` map (group label → packaged logo path) is produced by `fetch` from the
config's per-source `logo` slug — **keep it as-is, don't hand-edit it.** For the default
`grid` layout, leave `group` as `""`.

## 5. Fold in the hot trend signal
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
- **Never *generate or fabricate* an image yourself** — every `image` is a real published one: a
  video's thumbnail, or an article/coverage still (including a screenshot of an AI-generated post
  that *is* the story), or `null`. The ban is on *you* creating/AI-generating a picture, not on
  showing a real still of AI content.
- **Never call the Anthropic API** — all writing happens here in this session.
- **Social posts & hotness:** link the real permalink; never fabricate a post, a view count,
  or a virality/hotness figure — the hot signal is an editorial estimate over time, not
  measured analytics.
