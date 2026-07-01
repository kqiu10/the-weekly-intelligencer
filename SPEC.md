# The Weekly Intelligencer — Specification

> A Claude Code **skill** that generates a weekly, *New York Times*–style AI-industry
> digest and renders it as a **self-contained HTML issue** that opens in any browser.
> The Anthropic API is never used — all LLM/web work runs inside the Claude Code
> session under the existing subscription; deterministic work runs in Python scripts.

- **Status:** v1 implemented & in use; v2 features (§10) specified, not yet built.
- **Created:** 2026-06-26 · **Refreshed:** 2026-07-01
- **Owner:** ck
- **Location:** `/Users/ck/workspace/the-weekly-intelligencer/`
- **Supersedes:** `tasks/SPEC.md` (the original v1 spec — kept as historical record).
  This file is the canonical spec; it reflects the code as it stands after the move to
  first-party sources (the NewsAPI subsystem was removed) plus the v2 roadmap.

---

## 1. Objective

### Problem
Keeping up with worldwide AI developments — frontier labs *and* what's going viral in
AI-generated media — means scanning dozens of sources every week. There is no single,
well-designed weekly digest that the user controls.

### What we're building
A generator that, on demand, produces one **weekly issue**: a curated, multi-section
AI-industry briefing rendered in a NYT broadsheet style (serif masthead, company/source
cards, preview images, hyperlinks). Sections ("dimensions") and their sources are fully
configurable. The issue is a **self-contained HTML file** that opens directly in a
browser — no site or build tooling required to read it.

### Target user
The user (ck), generating a weekly issue to read now and publish later. Single-operator
tool; not a multi-tenant product.

### Success criteria
1. **One invocation → one issue.** Running the skill produces a valid
   `dist/YYYY-MM-DD.html` (self-contained, NYT-styled) plus its cached images.
2. **Cost-thrifty by construction.** `feed` and `site` sources cost **zero gather
   tokens** (fetched by script). An all-`feed`/`site` + all-`raw` issue runs end-to-end
   with **no Claude tokens at all**. Tokens are spent only on `search` sources and
   `rewrite`/`synthesize`/TL;DR writing.
3. **First-party by preference.** Sources are the labs' and platforms' own newsrooms,
   feeds, and (where open) official APIs — not third-party news aggregators or paid
   scrapers.
4. **Configurable dimensions.** Adding/removing a section or source is a config edit — no
   code change.
5. **Every item is attributed.** Each item links to its original source; nothing is
   fabricated.
6. **Self-contained output.** The HTML opens with no build step; styling is inlined and
   the `dist/` bundle is portable and hostable anywhere.
7. **NYT presentation.** The issue reads as a broadsheet — masthead with issue number and
   week range, per-source cards, preview images, hyperlinks.

### Non-goals (v1)
- Third-party news aggregators / paid social scrapers (deliberately removed).
- Eleventy/site integration, scheduling, PDF/email output (parked — §11).
- AI-generated imagery (article/post preview images only).
- Direct access to locked social APIs (TikTok/IG/FB); the one exception considered is the
  **open, first-party YouTube Data API** (§10.1).

---

## 2. Architecture

Two halves with a clean contract between them:

```
┌─────────────────────────┐   manifest.json   ┌──────────────────────────┐
│  Python helper scripts  │ ───────────────►  │   Claude Code (session)  │
│  (deterministic)        │ ◄───────────────  │   search + write         │
│  • fetch feeds/sites     │   manifest.json   │  • WebSearch/WebFetch     │
│  • resolve GNews, og:img │                   │  • editorial summaries    │
│  • extract article lede  │                   │  • TL;DR + trend curation │
│  • render issue HTML     │                   │  • headline/order curation│
└─────────────────────────┘                   └──────────────────────────┘
             │                                            ▲
             │  reads/writes                              │ orchestrated by
             ▼                                            │
   config/dimensions.yaml                          .claude/skills/.../SKILL.md
             │
             ▼  render writes
   dist/2026-06-26.html  (+ dist/assets/…)   ← self-contained, opens anywhere
```

The generator renders a complete, styled HTML issue on its own — no server, no build step.

### The pipeline (what the skill orchestrates)
1. **`validate`** (script): check `config/dimensions.yaml`; stop on errors.
2. **`fetch`** (script): for every `feed`/`site` source, gather items, resolve Google
   News redirects, extract `og:image` + the article's own lede, and cache images if
   configured. Write `out/manifest.json`. `search` sources are left as empty placeholders.
3. **search** (Claude, in-session): for each `search` source, use WebSearch/WebFetch to
   fill items (title, url, image, snippet). Skipped if there are none.
4. **write** (Claude, in-session): per each dimension's `summary` mode, produce item
   summaries; write the issue **TL;DR** (§10.3); curate the **trend** signal (§10.2).
   Skipped for `raw` dimensions with no trend/TL;DR needs.
5. **`render`** (script): render a self-contained NYT-styled HTML file into `output.dir`
   (Jinja2 + CSS inlined into `<head>`); copy cached images and packaged logos into
   `dist/`. Optionally open it.

### The manifest contract
`out/manifest.json` is the **single source of truth** passed between stages (gitignored).
Current shape (v2 additions marked ⬥):

```json
{
  "issue": {
    "date": "2026-06-26", "title": "The Weekly Intelligencer",
    "subtitle": "…", "week": 1,
    "tldr": "⬥ issue-level executive summary (~100 words, written at the write stage)"
  },
  "dimensions": [
    {
      "name": "Frontier AI Research Labs",
      "blurb": "…", "summary_mode": "rewrite", "layout": "by-source",
      "logos": { "Anthropic": "assets/logos/anthropic.svg" },
      "notes": [],
      "items": [
        {
          "title": "Introducing Claude Sonnet 5",
          "url": "https://www.anthropic.com/news/…",
          "source": "anthropic.com", "published": "2026-06-30",
          "image": "assets/2026-06-26/anthropic-1.jpg",
          "raw_text": "the article's own opening words (the lede)…",
          "summary": "Claude-written prose (empty for raw)",
          "origin": "site", "group": "Anthropic"
        }
      ],
      "trends": [
        "⬥ { descriptor, tags, magnitude, recurring, direction, heat_tier } — §10.2"
      ]
    }
  ]
}
```

`render` reads this same manifest for every output, so new targets (an Eleventy file in
v2) can be added without touching fetch/search/write.

---

## 3. Source types & summary modes

### Source types
| `type`   | Determinism       | Who fetches       | Gather token cost |
|----------|-------------------|-------------------|-------------------|
| `feed`   | deterministic     | Python script     | none              |
| `site`   | deterministic     | Python script     | none              |
| `search` | non-deterministic | Claude WebSearch  | yes (session)     |

- **`feed`** — RSS/Atom. Includes **Google News search feeds**: the script resolves the
  opaque `news.google.com` redirect to the real publisher article (via the `batchexecute`
  endpoint), names the real outlet, strips the trailing " - Publisher" from the title, and
  drops the generic thumbnail Google returns on every item.
- **`site`** — scrape a company's **own newsroom index** for `(url, date)` pairs, then read
  each article's title, `og:image`, and lede from the article page. No aggregator involved.
  (e.g. `anthropic.com/news`, `x.ai/news`, `ai.meta.com/blog`.)
- **`search`** — filled by Claude in-session with WebSearch/WebFetch. The mechanism for
  non-feed, non-official content (e.g. trending social media — §10.1).

> **Removed:** the `type: api` / NewsAPI subsystem. NewsAPI is a paid third-party
> *aggregator* (news articles *about* things), which is the wrong layer and against the
> first-party principle. Precision for social content comes from first-party platform APIs
> (only YouTube offers one openly) + Claude search — never a news aggregator.

### Item enrichment (deterministic, applied to `feed`/`site` items)
- **Lede/blurb** — the article's **own first `defaults.blurb_words` words** (default **50**,
  NYT-brief; ~40–60), verbatim, ending on a whole sentence — the way a newspaper reprints a
  wire lede rather than paraphrasing. Reads leading `<p>` paragraphs; for JS-rendered pages
  (no readable body) falls back to the page's `NewsArticle` JSON-LD (`articleBody`, else the
  publisher `description`). A blurb that merely repeats the headline is hidden.
- **Preview image** — `og:image` (rejects unfilled template placeholders); any image
  repeated across items (feed boilerplate) is dropped so each story shows its own picture or
  none.
- **Drop-contentless** — an item with no title, or with neither image nor blurb (usually a
  hard scraper block, e.g. Cloudflare 403), is dropped rather than shown as a bare headline.
  A source may therefore show fewer items (0–`max_per_source`), which is fine.

### Summary modes (per-dimension token lever)
| mode         | Behaviour                                          | Token cost |
|--------------|----------------------------------------------------|------------|
| `raw`        | use the lede/feed text verbatim                    | ~none      |
| `rewrite`    | Claude rewrites each item into NYT prose           | medium     |
| `synthesize` | Claude reads several items → one combined section  | highest    |

---

## 4. Configuration

Single file: `config/dimensions.yaml`. Editing it is the primary way to change output.

```yaml
publication:
  title: "The Weekly Intelligencer"
  subtitle: "A weekly briefing on AI and the work it's reshaping"
  first_issue_date: "2026-06-26"   # anchors issue numbering (§7 numbering)

output:
  dir: "./dist"                    # where <date>.html and its assets are written
  images: cache                    # cache (download alongside) | hotlink (source URL)
  open_after_render: false

defaults:
  summary: rewrite                 # raw | rewrite | synthesize (per-dimension override)
  max_items: 5
  blurb_words: 50                  # words of the article's own lede per item (~40–60)
  tldr_words: 100                  # ⬥ v2: issue-level TL;DR target length (§10.3)

dimensions:
  - name: "Frontier AI Research Labs"
    blurb: "The week's models, money, and announcements from the leading AI labs"
    summary: rewrite
    layout: by-source              # one labeled card per lab; empty labs are skipped
    max_per_source: 2              # at most 2 events per lab
    within_days: 7                 # only items from the past 7 days
    sources:                       # label = card heading; logo = slug in assets/logos/
      - { type: site, label: "Anthropic",       logo: "anthropic", url: "https://www.anthropic.com/news" }
      - { type: feed, label: "Google DeepMind", logo: "deepmind",  url: "https://deepmind.google/blog/rss.xml" }
      - { type: feed, label: "OpenAI",          logo: "openai",    url: "https://openai.com/news/rss.xml" }
      - { type: site, label: "xAI",             logo: "xai",       url: "https://x.ai/news" }
      - { type: feed, label: "DeepSeek",        logo: "deepseek",  url: "https://news.google.com/rss/search?q=DeepSeek&hl=en-US&gl=US&ceid=US:en" }
      - { type: site, label: "Meta",            logo: "meta",      url: "https://ai.meta.com/blog/" }
      - { type: feed, label: "Alibaba Qwen",    logo: "qwen",      url: "https://news.google.com/rss/search?q=Qwen%20Alibaba%20AI&hl=en-US&gl=US&ceid=US:en" }

  # ⬥ v2 — see §10.1
  - name: "Trending AI Generative Context & Social Video"
    blurb: "The week's most-shared AI-generated photos and videos across social platforms"
    summary: rewrite
    layout: by-source
    max_per_source: 2
    within_days: 7
    trends: true                   # ⬥ enable hotness tracking for this dimension (§10.2)
    sources:                       # one card per platform, filled by Claude web search
      - { type: search, label: "YouTube Shorts", logo: "youtube",   query: "trending AI-generated video YouTube Shorts this week" }
      - { type: search, label: "TikTok",         logo: "tiktok",    query: "viral AI-generated video TikTok this week" }
      - { type: search, label: "Instagram",      logo: "instagram", query: "viral AI-generated reel Instagram this week" }
      - { type: search, label: "Facebook",       logo: "facebook",  query: "viral AI-generated video Facebook this week" }
```

### Layouts
- **`by-source`** — one bordered **card per source** (in config order): a left rail with the
  source's `label` over its brand logo, and its recent items alongside (preview thumbnail +
  headline + lede + `source · date`). Empty sources are skipped. `max_per_source` (default
  **2**) caps items per card; `within_days` keeps only recent items.
- **`grid`** — a lead story + item list (used for non-`by-source` dimensions).

### Validation rules
- Every dimension needs ≥1 source and a unique `name`.
- `type` ∈ {`feed`, `site`, `search`}; a `feed`/`site` source needs a `url`.
- Unknown `type`/`summary`/`layout` fail validation loudly.
- A `by-source` `feed` source without a `label` warns (its card would be unlabeled).
- `output.dir` is created if missing.

---

## 5. Project structure

```
the-weekly-intelligencer/
├── SPEC.md                         # this file (canonical)
├── README.md                       # quickstart
├── pyproject.toml                  # uv-managed; runtime + dev deps; ruff/black line-length 100
├── .gitignore                      # out/, dist/, __pycache__, caches
│
├── .claude/skills/the-weekly-intelligencer/
│   └── SKILL.md                    # orchestrator: runs validate → fetch → search → write → render
│
├── config/
│   └── dimensions.yaml             # publication meta, output, defaults, dimensions
│
├── src/intelligencer/
│   ├── __init__.py
│   ├── cli.py                      # `intelligencer fetch|render|validate` (loads .env via dotenv)
│   ├── config.py                   # load + validate dimensions.yaml
│   ├── feeds.py                    # RSS/Atom parse; Google News publisher/title/date handling
│   ├── images.py                   # og:image, article lede, title, Google News redirect decode, cache
│   ├── sites.py                    # official-newsroom index crawl → (url, date)
│   ├── text.py                     # normkey, item_blurb (shared by gather + render)
│   ├── manifest.py                 # manifest schema + (de)serialize
│   ├── gather.py                   # config → manifest; issue numbering; window/dedup/drop rules
│   ├── net.py                      # HTTP constants (USER_AGENT, DEFAULT_TIMEOUT, BROWSER_HEADERS)
│   ├── render.py                   # manifest → self-contained HTML (Jinja2); copies logos
│   ├── templates/
│   │   ├── issue.html.j2           # NYT broadsheet template
│   │   └── intelligencer.css       # NYT styling (inlined at render)
│   └── assets/logos/               # brand-colored SVGs: openai, anthropic, deepmind, qwen,
│                                    #   xai, deepseek, meta  (v2 adds: youtube, tiktok,
│                                    #   instagram, facebook, and the 🔥 flame — §10)
│
├── data/                           # ⬥ v2: committed trend history (trends.json — §10.2)
├── samples/2026-06-26.html         # golden issue (render byte-compare test)
├── tests/                          # offline, deterministic (fixtures/, no live network)
├── tasks/                          # SPEC (v1 historical), plan.md, todo.md
├── out/                            # working dir (gitignored): manifest.json, image cache
└── dist/                           # rendered issues + assets (gitignored)
```

**Skill discovery:** project-local under `.claude/skills/`, discovered when Claude Code runs
from this directory. Optionally symlink into `~/.claude/skills/` for global invocation.

---

## 6. Commands

Python env via **uv**. The skill calls these; the user can run them directly too.

| Command | Purpose |
|---|---|
| `uv sync` | install deps |
| `uv run intelligencer validate` | validate `config/dimensions.yaml` |
| `uv run intelligencer fetch` | deterministic gather (feeds + sites) → `out/manifest.json` |
| `uv run intelligencer render` | manifest → self-contained HTML in `./dist` |
| `uv run intelligencer render --open` | render, then open the issue in a browser |
| `uv run pytest` | run the test suite (offline) |
| `uv run ruff check . && uv run black --check .` | lint + format check |

**Skill invocation:** from the project directory, ask Claude Code to *"generate this week's
Intelligencer issue."* The skill runs `validate → fetch → [search] → [write] → render` and
reports the output HTML path.

---

## 7. Code style

- **Python 3.12+**, full type hints, `ruff` + `black` at **line-length 100**, small
  single-purpose modules.
- **Stdlib-first**; minimal runtime deps: `feedparser`, `httpx`, `pyyaml`, `beautifulsoup4`,
  `jinja2`, `python-dotenv`. **No LLM SDK** — the LLM is the session.
- **Fail-soft:** one dead feed, missing image, or blocked page never aborts the issue; it
  logs and continues. The issue is best-effort but always builds.
- **Network discipline:** every HTTP call has a timeout and a descriptive User-Agent; some
  newsrooms need browser-shaped headers (`BROWSER_HEADERS`). Fetches are single-shot and
  fail-soft (no retry/backoff today — add per-host backoff only if a source needs it).
- **Deterministic output:** given the same manifest, `render` produces byte-identical HTML
  (stable ordering, inlined CSS) — the golden test depends on this.
- **Config is data, code is logic:** no source URLs, queries, or paths hardcoded in Python —
  all live in `dimensions.yaml`. **YAML keys** are `snake_case`.

### Issue numbering
`issue_week_number` counts **Mon–Sun calendar weeks** since the first issue's week (1-based):
Issue 1 is the calendar week *containing* `first_issue_date`, so it ends on that first Sunday
and each following Monday starts the next issue. `issue_week_range` gives the Mon–Sun span the
issue covers. The masthead/colophon read **"Issue N · Jun 29 – Jul 5, 2026"**. (For the window
and the label to line up cleanly, publish on/near the week's Sunday.)

---

## 8. Testing strategy

Lean by design — cover the **crucial, fiddly, non-obvious** logic, not every function.
Consolidate near-identical cases (parametrize), extract shared setup, and don't duplicate what
another test or the golden sample already pins.

- **No live network in the suite.** `tests/fixtures/` holds canned RSS/Atom + HTML; parsing is
  tested against them.
- **Deterministic units worth testing:** config validation; feed/publisher/date parsing;
  og:image + lede extraction (truncation, sentence-boundary, JSON-LD fallbacks); Google News
  `batchexecute` decode; newsroom listing crawl; the gather window/dedup/drop rules; **issue
  calendar-week numbering + range**; the golden render (fixture manifest → byte-compare against
  `samples/2026-06-26.html`).
- **End-to-end offline:** a fixture config with only `file://` feed sources runs `fetch →
  render` with zero network and zero tokens, proving the deterministic path top-to-bottom.
- **Not unit-tested:** Claude's search/summaries/TL;DR/trend curation (non-deterministic) — they
  are constrained by the manifest schema and the §9 boundaries.
- **v2 additions to test deterministically:** the trend **store round-trip**, the **magnitude
  delta / heat-tier** computation, and **flame-tier → render** mapping (§10.2). The semantic
  *matching* itself (Claude/embeddings) is not unit-tested; the arithmetic on top of it is.
- Regenerate `samples/2026-06-26.html` whenever the template changes intentionally.

---

## 9. Boundaries

### Always
- **Attribute everything.** Every item carries a working hyperlink to its original source
  (a real permalink for social posts); preserve the source name.
- **Prefer the first-party, cheap path.** Route `feed`/`site` through the script (zero gather
  tokens); spend Claude only on `search` and `rewrite`/`synthesize`/TL;DR/trend work. Prefer a
  platform's own newsroom/feed/official API over any aggregator.
- **Fail soft and disclose.** A dead source is skipped with a visible note, never silently
  dropped or invented around.
- **Respect sources.** Honor `robots.txt`, ToS, and rate limits; identify with a real
  User-Agent; never bypass paywalls.

### Ask first
- Before adding **any keyed API** source — *even a free one* (e.g. the YouTube fast-follow,
  §10.1). It reintroduces key/quota handling.
- Before adding a **non-trivial dependency** — in particular a **vector DB or a local
  embedding/CLIP model** (§10.2); these are heavy and must be justified by scale.
- Before any step that **writes outside** the project's `output.dir` (the `data/` trend store
  is the one sanctioned exception, and it is committed and diff-able).

### Never
- **Never fabricate** news, quotes, numbers, dates, links, or **virality/hotness figures**;
  state no more than the source supports. Hotness is an editorial proxy (§10.2), never
  presented as measured analytics unless it comes from a first-party metric (e.g. YouTube
  view counts).
- **Never generate or insert AI imagery** — real article/post preview images only.
- **Never hotlink** images when `images: cache` is set.
- **Never call the Anthropic API** — all LLM work is the Claude Code session.
- **Never reintroduce third-party news aggregators or paid social scrapers** (NewsAPI, Apify,
  TikHub, …) — they are the layer this project deliberately left.

---

## 10. v2 roadmap — new features (specified, not yet built)

### 10.1 Dimension: "Trending AI Generative Context & Social Video"
A second dimension listing the week's most-shared **AI-generated photos/videos** across
YouTube Shorts, TikTok, Instagram, and Facebook — rendered with the **exact `by-source` card**
used by Frontier Labs (one card per platform: platform logo + trending posts with preview
image, title, short lede, permalink · date).

- **Sourcing = pure `type: search`** (Claude in-session). Rationale (researched 2026-07):
  among the four platforms, only **YouTube** exposes an open, first-party trending API; TikTok/
  Instagram/Facebook offer **no** open trending API (research-only or paid third-party scrapers,
  both excluded). So Claude web search — which finds the actual primary posts, judges "is this
  AI-generated / trending," and grabs preview images — is the best philosophy-compatible route.
- **Precision fast-follow (ask-first, §9):** add the **official YouTube Data API** (free key,
  `videos.list?chart=mostPopular` = 1 quota unit; `search.list` for AI queries) for the YouTube
  card only — it yields exact thumbnails, publish dates, and **real view counts** that also feed
  the hotness metric (§10.2). This is first-party, so it fits; it is the *only* keyed source
  worth reviving, and only when trend precision matters.
- **New logos:** `youtube`, `tiktok`, `instagram`, `facebook` (brand SVGs), packaged like the
  lab logos.
- **Known limits (accepted):** TikTok/IG preview images sit behind CDNs that may expire or
  block hotlinking, so some cards fall back to no-image and are dropped by drop-contentless →
  thinner cards on those platforms; "is it AI-generated?" is Claude's curation judgment.

### 10.2 Trend intelligence — the 🔥 hotness signal
For the social-video dimension, show whether a **context** (a topic / recurring visual meme /
key fact) is **getting hotter**. Displayed as a **graduated flame** — 🔥 / 🔥🔥 / 🔥🔥🔥 — shown
when a context **recurs** (seen in a prior week) **and is rising**. A layered design, because
the problem is really two problems — *identity* (which needs semantic, not string, matching) and
*trend* (which is time-series counting):

**A. Understanding content (now, zero new infra).** During the write stage Claude uses its own
**vision** on each item's thumbnail/preview + caption + any web description to write a
**canonical descriptor + tags** of *what the media depicts* (not just its title). This is how we
"understand what shows up inside the image/video." Limit: it sees the thumbnail, not full video
motion — sufficient for topic identity, especially with YouTube titles/descriptions.

**B. Semantic matching across weeks (语义级相似度).** A normalized string key is *too weak* to
tell that "Sora fighter-jet cat" ≈ "AI cat flying a jet". So:
- **v1:** Claude matches this week's descriptors against recent stored descriptors **in-session**
  — it *is* the semantic engine; no vector DB while history is small.
- **v2 (when history outgrows context):** add a **text-embedding index** over the descriptors
  (pgvector / sqlite-vss / Chroma) for nearest-neighbor retrieval of prior matches, which Claude
  then confirms. *This* is where an embedding DB earns its place — as a **retrieval index**, not
  as the trend computer.
- **v3 (only if needed):** **multimodal/CLIP embeddings** on the actual images for true
  visual-dedup (same meme, different captions). Heaviest option (local CLIP dep or a paid
  multimodal key) — gate behind evidence that caption+thumbnail matching is insufficient.

**C. Trend math + storage (always deterministic).** A committed **`data/trends.json`**
time-series (stdlib SQLite is the scale-up path; both zero new deps) — never a vector store:

```json
{
  "topics": [
    {
      "id": "sora-photoreal-animals",
      "descriptor": "Photorealistic AI videos of animals in absurd human scenarios (Sora-style)",
      "tags": ["sora", "photorealistic", "animals", "video"],
      "history": [
        { "week": 2, "issue_date": "2026-06-29", "magnitude": 3, "samples": ["https://…"] },
        { "week": 3, "issue_date": "2026-07-06", "magnitude": 7, "samples": ["https://…"] }
      ]
    }
  ]
}
```

- **magnitude** = a hotness proxy: count of distinct items/sources Claude found for the context
  this week + Claude's qualitative volume estimate (+ **real YouTube view counts** when the
  §10.1 fast-follow is present). It is an *editorial* signal, disclosed as such — not analytics.
- **heat_tier** (0–3 flames) = f(recurring?, magnitude delta over recent weeks): unseen → new
  (no flame); recurring & rising a little → 🔥; strongly rising → 🔥🔥; sustained multi-week
  climb → 🔥🔥🔥. A falling recurring context reads as cooling (muted, no flame).
- **Cold start:** trends need history — the first ~3–4 issues have little to compare against, so
  the signal warms up over a few weeks.
- **Display:** a "Heating up" strip within the dimension listing the hot contexts with their
  flames (keyword/context level, distinct from the media cards). Flame is a **packaged SVG**
  asset (traced from the user's flame PNG) so the HTML stays self-contained; no JS.

### 10.3 Issue-level TL;DR
A **TL;DR** block at the very top of the issue (above the first dimension), summarizing the whole
issue across all dimensions.

- **Length: ~100 words**, one tight paragraph (bounded 80–120) — the NYT briefing register;
  enough to land 3–5 threads without ceasing to be a *TL;DR*. Configurable via
  `defaults.tldr_words`. Optional variant: 1 framing sentence + one bullet per dimension.
- **Written by Claude at the write stage**, *after* all dimensions are gathered (it summarizes
  them), stored as `issue.tldr`. Zero Anthropic-API cost. It may open with the §10.2 trend
  highlights ("heating up this week: …").
- **Render:** a new block above `<main>`; the by-source first dimension already suppresses the
  grid hero, so that slot is free.

---

## 11. Further future (parked)
- **Eleventy publish target** — a second render target off the same manifest (11ty content file
  + assets + a thin Nunjucks layout) for archive, RSS, and nav. Additive; v1 stages unchanged.
- Scheduled runs (launchd/cron wrapping the manual command).
- "Print to PDF" / EPUB export; email edition (inline-CSS render of the same manifest).
- Cross-dimension de-duplication; trend charts/sparklines as an alternative to the flame.
