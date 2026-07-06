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
- **If the user asks for only certain dimensions** ("just the labs and Cross-Border
  Branding", "only do 1 and 2", "skip the social one"), resolve their request against the
  config's **declared order** (1-based: the first dimension is `1`) and pass it to `--only`
  on both `fetch` and `render` — it takes a comma-separated list of indices and/or name
  substrings, e.g. `--only 1,3` or `--only "labs,Cross-Border"`. Default (no such request):
  process **all** dimensions, as normal. Note `fetch --only` now *merges* into any existing
  `out/manifest.json` (it no longer wipes the untouched dimensions), so a partial refresh is
  safe — but a search-only dimension still has its items re-filled by you in step 2.

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

### The Intelligent Factory, Rewriting Cross-Border Branding & Trending Social Video & Images
All three arrive **pre-filled by `fetch`** as ungrouped candidate pools. **Prune** each
pool to its bar below (rebalanced 2026-07-06 — the middle between the original strict bars
and none), set each kept item's `group` (company / brand / platform / publication — one
card per group), drop the rest. If more than `max_items` qualify, keep the **newest
`max_items`** — a mechanical ceiling, no judgment. Zero in a quiet week is fine — an empty
dimension doesn't render; leave `notes` empty.

- **The Intelligent Factory** keeps: a named manufacturer/industrial company with a
  concrete AI adoption, deployment, or partnership — **vendor named or not**; substantive
  industrial-AI trade coverage (cobots, digital twins, robotics in production); and **The
  Batch weekly as a standing recap card** (group `"The Batch"`). Reject: AI vendors' own
  chip/data-center/infrastructure moves (wrong direction), M&A with no AI angle,
  conference calendars, how-tos, promos.
- **Rewriting Cross-Border Branding** keeps: a named Chinese cross-border/going-global
  brand × AI story; a **major milestone of such a brand even without an AI angle** (IPO,
  market entry, flagship launch — e.g. Anker's HKEX listing); and a platform-AI feature
  that materially affects Chinese sellers going global. Reject: market/stock digests and
  morning briefs, ESG/finance notes, trademark/patent warnings, how-to guides,
  domestic-only stories, and a Chinese AI vendor's own overseas expansion (that's
  Frontier AI Research Labs' beat).
- **Trending Social Video & Images** keeps: a curator tweet **showcasing a specific
  AI-generated work** (media attached or a link to one) — virality **not** required; the
  curator's pick is the signal. Link the underlying post when the tweet points at one
  (`group` = the platform it lives on), else the tweet itself (`group: "X"`). `creator`
  always; `image`/`stats` only when actually visible. Reject: personal/admin posts,
  milestones, promos, link-less chatter.

Safety floor everywhere (non-negotiable): no misinformation, violence, gore, or harmful
deepfakes — and never fabricate a title, link, stat, or image. For kept items: WebFetch to
confirm/fill `image` (real og:image, else null) and `raw_text`; dedup against the other
dimensions this issue; set `dim.logos[group]` when a packaged slug exists (or add a real
Simple Icons SVG — never invent path data — extending the logo test), else the label-only
rail is fine.

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
