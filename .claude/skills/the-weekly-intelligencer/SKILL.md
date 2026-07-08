---
name: the-weekly-intelligencer
description: Generate this week's issue of The Weekly Intelligencer — a New York Times–style AI-industry digest rendered as a self-contained HTML page. Use when the user asks to build, generate, or refresh the weekly AI issue. Python scripts gather all sources deterministically; you prune the candidate pools, write the editorial summaries, and translate.
---

# The Weekly Intelligencer — issue orchestrator

You are producing **one weekly issue**. The deterministic work (RSS `feed` and `site`
sources) is done by Python scripts and costs no tokens — you only spend effort on
pruning, summaries, and translation. Work from the project root and follow these
steps in order.

## 0. Preconditions
- Run `uv run intelligencer validate`. If it reports errors, stop and show them.
- Read `config/dimensions.yaml`. Note, per dimension: its `summary` mode
  (`raw` / `rewrite` / `synthesize`) and its `max_items`.
- **If the user asks for only certain dimensions** ("just the labs and Cross-Border
  Branding", "only do 1 and 2", "skip the social one"), resolve their request against the
  config's **declared order** (1-based: the first dimension is `1`) and pass it to `--only`
  on both `fetch` and `render` — it takes a comma-separated list of indices and/or name
  substrings, e.g. `--only 1,3` or `--only "labs,Cross-Border"`. Default (no such request):
  process **all** dimensions, as normal. Note `fetch --only` now *merges* into any existing
  `out/manifest.json` (it no longer wipes the untouched dimensions), so a partial refresh is
  safe — a refetched pool dimension arrives raw again, so you re-prune it in step 2.

## 1. Gather deterministic sources (no tokens)
Run `uv run intelligencer fetch`. This writes `out/manifest.json` with the issue metadata
and the items already gathered from `feed`, `site` (scraped official newsrooms), and
`youtube` (the YouTube Data API — the YouTube Shorts card, when `YOUTUBE_API_KEY` is set)
sources. (A `search`-type source would be filled by you via WebSearch on its `query` —
none is configured today; see git history for the full drill if one returns.)

## 2. Prune the candidate pools
**The Intelligent Factory, Rewriting Cross-Border Branding & Trending Social Video &
Images** arrive **pre-filled by `fetch`** as ungrouped candidate pools. **Prune** each
pool to its bar below, set each kept item's `group` (company / brand / platform / publication — one
card per group), drop the rest. If more than `max_items` qualify, keep the **newest
`max_items`** — a mechanical ceiling, no judgment. Zero in a quiet week is fine — an empty
dimension doesn't render; leave `notes` empty.

- **The Intelligent Factory** keeps: a named manufacturer/industrial company with a
  concrete AI adoption, deployment, or partnership — **vendor named or not**; substantive
  industrial-AI trade coverage (cobots, digital twins, robotics in production); and **The
  Batch weekly as a standing recap card** (group `"DeepLearning.AI"`). Reject: AI vendors' own
  chip/data-center/infrastructure moves (wrong direction), M&A with no AI angle,
  conference calendars, how-tos, promos.
- **Rewriting Cross-Border Branding** keeps: a named Chinese cross-border/going-global
  brand × AI story; a **major milestone of such a brand even without an AI angle** (IPO,
  market entry, flagship launch — e.g. Anker's HKEX listing); and a platform-AI feature
  that materially affects Chinese sellers going global. Reject: market/stock digests and
  morning briefs, ESG/finance notes, trademark/patent warnings, how-to guides,
  domestic-only stories, and a Chinese AI vendor's own overseas expansion (that's
  Frontier AI Research Labs' beat).
- **Trending Social Video & Images** keeps: items **showcasing a specific AI-generated
  work**. The **r/aivideo weekly-top pool** is the beat by construction — keep the
  strongest posts (group `"Reddit"`), drop memes/discussion/promo threads; thumbnails
  arrive from the feed itself. `creator`/`image`/`stats` only when actually present —
  never invented.

Safety floor everywhere (non-negotiable): no misinformation, violence, gore, or harmful
deepfakes — and never fabricate a title, link, stat, or image. For kept items: WebFetch to
confirm/fill `image` (real og:image, else null) and `raw_text`; dedup against the other
dimensions this issue; set `dim.logos[group]` when a packaged slug exists (or add a real
Simple Icons SVG — never invent path data — extending the logo test), else the label-only
rail is fine.

## 3. Write summaries per the dimension's `summary` mode
**Write each summary in the item's source language — never translate**: a Chinese-language
source (白鲸, 雨果, 36氪, 钛媒体…) gets a 中文 summary; an English source gets English. The
issue-level TL;DR stays in English (masthead register).
- **`raw`** — leave `summary` empty (the feed/snippet text is shown as-is).
- **`rewrite`** — write a faithful 1–2 sentence NYT-style summary for each item.
- **`synthesize`** — write one combined 2–4 sentence editorial paragraph for the
  dimension and place it as the `summary` of that dimension's first item.

Apply the same mode to the deterministic (`feed`/`site`) items already in the manifest.

## 4. Patch the manifest
Rewrite `out/manifest.json` with the **Write** tool. Keep `issue` and every item that
survived the prune; fill in summaries. Also:

- **Issue TL;DR** — write `issue.tldr`: a one-paragraph, ~`defaults.tldr_words` (≈100-word)
  executive summary of the whole issue across all dimensions (NYT briefing register). It may
  open with what's heating up this week.
- **Bilingual i18n (SPEC §10.9)** — for **every item** write
  `i18n: {"zh": {title, summary, raw_text}, "en": {...}}`: the **source-language entry is
  the original values verbatim**; the other entry is your faithful translation — ledes
  (`raw_text`) translate too; company/brand/product names stay untranslated inside
  sentences. For each dimension write `name_i18n`/`blurb_i18n` `{"zh","en"}` pairs, and
  for the issue write `tldr_i18n`. The rendered page defaults to 中文; the masthead
  translate icon flips languages (pure CSS, no JS).
Preserve the schema exactly:

```
issue:      { date, title, subtitle, week, tldr, tldr_i18n }
dimensions: [ { name, name_i18n, blurb, blurb_i18n, summary_mode, layout, items: [ ... ],
                notes: [ ... ], logos: { ... } } ]
item:       { title, url, source, published, image, raw_text, summary, origin, group,
              creator, stats, i18n }
            (social-video only — creator: @handle/channel; stats: {views,likes,comments,…} → overlaid on the tile)
```

If a dimension's `layout` is `by-source`, items are rendered grouped by their `group`
field (one card per source) — set `group` on any item you add there, and a source that
yields nothing is simply skipped. Each card shows the source's logo and name in a left
rail; the `logos` map (group label → packaged logo path) is produced by `fetch` from the
config's per-source `logo` slug — **keep it as-is, don't hand-edit it.** For the default
`grid` layout, leave `group` as `""`.

## 5. Render
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
- **Social posts:** link the real permalink; never fabricate a post, a view count, or an
  engagement figure — `stats` only carry numbers a platform actually exposes.
