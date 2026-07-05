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

### The "Intelligent Factory" dimension
A named manufacturer adopting a **named** AI vendor's tech for its own operations — not
the AI industry's own hardware/infrastructure news. Find up to `max_items` qualifying
stories this week, never pad to reach it — zero in a quiet week is correct, not a failure.

**This dimension is feed-sourced now — `fetch` already handed you a candidate pool.** Its
two `feed` sources (Manufacturing Dive's RSS + a recency-scoped `when:7d` Google News
proxy) land in this dimension's `items` as an ungrouped, deterministically gathered batch
(`group: ""`). **Your job is to *filter*, not to search from scratch:** read that pool and
keep only the entries that pass the qualify bar below, dropping the rest. (This replaced
the old search-only design: a keyword feed alone can't judge direction/recency, but a feed
*plus your judgment as the filter* can — the same split that already works for YouTube.)

**Step 0 — also scan the labs' own already-fetched feeds (free).** Frontier AI Research
Labs' `feed`/`site` sources are capped at `max_per_source: 2` for *that* dimension; re-pull
each (`fetch_feed(url)`) and scan the *uncapped* list for a customer/partnership headline
the cap dropped. This is how a 2026-07-03 run missed HP × OpenAI (item #6 in OpenAI's RSS).

**The `search` supplement is the long tail.** After filtering the feed pool, if it's thin,
run the dimension's `search` source — a generic query plus combined watchlist×vendor
queries (`(HP OR Foxconn OR …) (OpenAI OR Microsoft OR NVIDIA) AI partnership this week`)
and vendor customer-story hubs (`openai.com/stories`, Microsoft/NVIDIA newsrooms). If the
feed pool already yields enough qualifying stories, you can skip it.

**Known AI-active manufacturers — a search aid, not a qualify restriction.** Any named
manufacturer still qualifies (per the rule above); this list exists to make queries sharper
and cheaper. Cross a few of these with the vendor list in a *single* combined query per
sector rather than one query per company — e.g. `(HP OR Foxconn OR Dell OR Lenovo OR
Samsung) (OpenAI OR Anthropic OR Microsoft OR NVIDIA) AI partnership this week` — a
named-pair match like this is sharper than either side alone, and is what should have
caught HP × OpenAI directly.
- **Electronics/hardware:** HP, Foxconn, Dell, Lenovo, Samsung
- **Industrial/automation:** Siemens, ABB, Schneider Electric, Honeywell, Rockwell
  Automation, Bosch
- **Automotive:** Toyota, Volkswagen, Hyundai, Ford, BMW
- **Heavy industry/aerospace:** Caterpillar, John Deere, Boeing, Airbus
- **Consumer goods:** Unilever, Mattel, Procter & Gamble

Grow this list over time — add a company here once a real, verified story about it is
found (mirroring how `data/trends.json` accumulates topics), so future searches start
sharper than this week's did.

**Qualify — needs a named AI vendor AND a named manufacturer applying it:**
- ✅ HP × OpenAI — "Frontier" partnership for customer experience and internal operations
  (hp.com press release + openai.com confirmation + independent trade press — the reference
  example; verified real, not hypothetical)
- ❌ "Siemens deploys a generative-AI copilot" — no vendor named
- ❌ "Toyota uses AI-powered computer vision for quality control" — no vendor named
- ❌ "Anthropic in talks with Samsung to manufacture a custom AI chip" — wrong direction,
  the AI vendor is the customer, not the industry adopting its AI
- ❌ NVIDIA "AI Factory" data-center campus — marketing term for a GPU data center
- ❌ opinion pieces, market forecasts, conference PR, unconfirmed "sources say" reports

AI vendor = OpenAI, Anthropic, Google DeepMind, xAI, Meta, DeepSeek, Qwen, Microsoft,
NVIDIA, or another major AI vendor — broader than the Frontier AI Research Labs roster
above; this beat is frontier AI landing in the wider economy, not that dimension's list.

**Freshness — re-check every kept item's real date.** The `when:7d` proxy and
`within_days: 7` already drop stale items, but confirm each kept story's *actual* published
date is inside this issue's week before adding it — don't trust the feed's recency setting
alone (a `when:7d` query is the belt, the parsed-date check is the suspenders).

- **Verify with WebFetch** before adding: confirm the named companies, that the date is
  inside the issue window, and that the link resolves to the real article, not a
  redirect/paywall stub. (Feed-pool items arrive with a title but often no image/lede —
  fetch the ones you keep to fill `image`/`raw_text`; Google News proxy links resolve to
  the real publisher on fetch.)
- **Dedup** against this issue's Frontier AI Research Labs dimension — if the same
  announcement already appears there (e.g. the lab's own newsroom post), don't add it
  again here; this dimension is for the industry-adoption angle, usually reported by
  business/trade press or the customer company, not the lab's own blog.
- **Silently** skip when nothing verifiable qualifies — leave `notes` empty, same as the
  social platforms below.
- **Set `group`** to the manufacturer's name (e.g. `"HP"`) on every kept item — the feed
  left it `""`; you reassign it so `by-source` renders one card per company (like the labs).
- **Logo, if you can add one:** run `ls src/intelligencer/assets/logos/` — if a
  `<slug>.svg` already matches the company (lowercased name, e.g. `hp.svg`), set
  `dim.logos[group] = "assets/logos/<slug>.svg"`. If none exists yet, either add one
  (matching the existing style exactly: Simple Icons format — `<svg fill="#<official brand
  hex>" role="img" viewBox="0 0 24 24" ...><title>Name</title><path d="..."/></svg>` —
  fetch the real path data, e.g. from
  `raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/<slug>.svg`, and the
  brand hex from their `data/simple-icons.json`; never invent path data) or leave the card
  logo-less — a missing `logo` entry always renders a safe label-only rail, never a broken
  `<img>`. This library only grows on confirmed, real companies (mirrors `data/trends.json`
  — small, accumulates over time); extend `tests/test_render.py`'s
  `test_intelligent_factory_company_logos_are_packaged` with the new slug when you add one.

### The "Rewriting Cross-Border Branding" dimension
Any real news tying a **named Chinese cross-border / going-global brand** to **AI** — how AI
is reshaping the way these brands market, localize, sell, and build themselves overseas.
Search-only; find up to `max_items` (7) qualifying stories this week, never pad — zero in a
quiet week is correct. **The qualify bar is deliberately broad** (any real brand × AI story,
not only a signed tool-adoption deal — unlike The Intelligent Factory's stricter
named-vendor-named-adopter bar); the discipline here is the **reject** list, which keeps it
from collapsing into "any China-AI news."

**Feed-sourced, same as The Intelligent Factory — `fetch` gave you a candidate pool.** Its
two `feed` sources — a 中文 `when:7d` Google News proxy (which aggregates 白鲸出海, 雨果跨境,
36氪出海, AMZ123 and the rest) plus 白鲸出海's own RSS — land here ungrouped (`group: ""`).
**Filter the pool** to the entries passing the qualify bar; this China-first beat breaks
first in Chinese-media coverage, which English/US search misses. AI vendor can be **any**
major AI company, Chinese or Western — Alibaba/Qwen, ByteDance/Doubao, Baidu/ERNIE, DeepSeek,
Zhipu/GLM, Moonshot/Kimi, Tencent, OpenAI, Anthropic, Microsoft, NVIDIA — broader than the
Frontier AI Research Labs roster (don't re-narrow it to the 7 labs).

**Step 0** — also scan the labs' own already-fetched uncapped feeds for a cross-border-brand
angle. **The `search` supplement** catches the long tail if the feed pool is thin (skip it
if the pool already yields enough). **Re-check each kept item's real published date** is
inside this week — don't trust the `when:7d` setting alone. **Set `group`** to the brand's
name on every kept item (the feed left it `""`), so `by-source` renders one card per brand.

**Watchlist — a search aid, not a qualify restriction (grows over time from verified finds):**
- **E-commerce/platforms:** SHEIN, Temu (PDD), AliExpress/Alibaba.com, TikTok Shop, DHgate
- **Consumer electronics/smart home:** Anker (Eufy, Soundcore), Ecovacs, Roborock, DJI, Insta360, UBTECH, Xiaomi
- **Home appliances:** TCL, Hisense, Midea
- **EV/auto:** BYD, NIO, XPeng
- **Gaming/entertainment:** miHoYo/HoYoverse, Tencent (global titles)

**Qualify — a named cross-border/going-global brand whose story materially involves AI:**
- ✅ A brand adopting an AI tool/platform capability to go global — marketing, localization,
  customer service, demand forecasting, logistics. *Real, verifiable examples of this
  tooling: Alibaba International's **Aidge** multilingual localization/marketing AI suite and
  its **Marco** merchant AI agents (openly announced, cross-border-seller-facing) — a named
  brand using these to expand overseas qualifies.*
- ✅ A named brand shipping an AI-powered product built for overseas markets (e.g. Anker's
  AI-driven smart-home line sold internationally).
- ✅ A cross-border platform's AI capability explicitly enabling a **named** brand's
  international push ("[platform]'s AI helped [named brand] reach $X in [overseas market]").

**Reject — the guardrails that keep this dimension distinct:**
- ❌ A Chinese **AI vendor's own** product/model gaining overseas *users*, with no other
  named brand involved (DeepSeek/Qwen/Kimi/Kling expanding abroad) — that's the vendor's own
  market expansion, already Frontier AI Research Labs' beat, not a *brand* using AI to go
  global. **This is the most common false positive — watch for it.**
- ❌ Domestic-only stories with no cross-border/international angle.
- ❌ A pure factory-floor / production AI deployment with no brand-facing or go-to-market
  angle — that's The Intelligent Factory (§10.4); dedup against it.
- ❌ Opinion pieces, market forecasts, conference PR, unconfirmed "sources say" reports.

**Verify / Dedup / Silently skip / Set `group` / Logo — identical mechanics to The
Intelligent Factory above:** WebFetch to confirm the named brand, the AI angle, the date is
inside the window, and the link resolves; dedup against the other dimensions this issue;
leave `notes` empty when nothing qualifies; set `group` to the brand's name (`by-source`
layout, one card per brand); add a real Simple-Icons logo for a newly-confirmed brand only if
one doesn't exist yet (never invent path data), else a safe label-only rail — and extend
`tests/test_render.py`'s logo test with any slug you add.

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
