# The Week Intelligencer — Specification

> A Claude Code **skill** that generates a weekly, New York Times–style AI-industry
> digest and renders it as a **self-contained HTML issue** that opens in any browser.
> The Anthropic API is never used — all LLM/web work runs inside the Claude Code
> session under the existing subscription; deterministic work runs in Python scripts.

- **Status:** Draft for sign-off
- **Created:** 2026-06-26
- **Owner:** ck
- **Location:** `/Users/ck/workspace/the-week-intelligencer/`
- **Scope note:** v1 ships the **HTML** output only. Publishing into the user's
  Eleventy (11ty) site is a deliberate **v2** add-on (see §9) — the manifest is the
  source of truth, so that path is additive and does not touch v1.

---

## 1. Objective

### Problem
Keeping up with worldwide AI developments (US + China, frontier labs, spending,
social-platform trends) means scanning dozens of sources every week. There is no
single, well-designed weekly digest that the user controls.

### What we're building
A generator that, on demand, produces one **weekly issue**: a curated, multi-section
AI-industry briefing rendered in a NYT broadsheet style (serif masthead, columns,
preview images, hyperlinks). Sections ("dimensions") and their data sources are fully
configurable. The issue is rendered as a **self-contained HTML file** that opens
directly in a browser — no site or build tooling required to read it.

### Target user
The user (ck), generating a weekly issue to read now and publish later. Single-operator
tool; not a multi-tenant product.

### Success criteria
1. **One invocation → one issue.** Running the skill produces a valid
   `dist/YYYY-MM-DD.html` (self-contained, NYT-styled) plus its cached images.
2. **Cost-thrifty by construction.** `type: feed`/`type: api` sources cost **zero
   gather tokens** (fetched by script). A dimension set that is all-`feed` + all-`raw`
   runs end-to-end with **no Claude tokens at all**. Tokens are spent only on
   `type: search` sources and `rewrite`/`synthesize` summaries.
3. **Configurable dimensions.** Adding/removing a section or a data source is a config
   edit — no code change.
4. **Every item is attributed.** Each news item links to its original source; nothing
   is fabricated.
5. **Self-contained output.** The HTML opens in a browser with no build step; styling is
   inlined and the `dist/` bundle is portable and hostable anywhere.
6. **NYT presentation.** The rendered issue visually reads as a broadsheet (masthead,
   multi-column, lead story, preview images, hyperlinks).

### Non-goals (v1)
- **Eleventy/site integration** (archive, RSS, nav) — deferred to v2.
- Automated scheduling (manual invocation only; cron/launchd is a thin v2 wrapper).
- PDF or email output (a later target off the same manifest).
- AI-generated imagery (article preview images only).
- Direct social-platform API access (FB/IG/TikTok trends come via web search).

---

## 2. Architecture

Three parts with a clean contract between them:

```
┌─────────────────────────┐   manifest.json   ┌──────────────────────────┐
│  Python helper scripts  │ ───────────────►  │   Claude Code (session)  │
│  (deterministic)        │ ◄───────────────  │   search + write         │
│  • fetch feeds/apis     │   manifest.json   │  • WebSearch/WebFetch     │
│  • extract og:image     │                   │  • editorial summaries    │
│  • render issue HTML    │                   │  • headline/order curation│
└─────────────────────────┘                   └──────────────────────────┘
             │                                            ▲
             │  reads/writes                              │ orchestrated by
             ▼                                            │
   config/dimensions.yaml                          .claude/skills/.../SKILL.md
             │
             ▼  render writes
   dist/2026-06-26.html  (+ dist/assets/2026-06-26/…)   ← self-contained, opens anywhere
```

**The generator renders a complete, styled HTML issue on its own** — nothing else is
required to view it. (No 11ty, no server, no build step.)

### The pipeline (what the skill orchestrates)
1. **`fetch`** (script): load config; for every `type: feed`/`type: api` source,
   fetch + parse items, extract `og:image` (and cache locally if configured). Write
   `out/manifest.json` with these deterministic items. `type: search` sources are left
   as empty placeholders flagged for Claude.
2. **search** (Claude, in-session): for each `type: search` source, use
   WebSearch/WebFetch to gather items (title, url, image, snippet) and fill the
   manifest placeholders. Skipped entirely if there are no `search` sources.
3. **write** (Claude, in-session): per each dimension's `summary` mode, produce the
   final item summaries and an optional editor's note; select/curate the lead story and
   ordering. Skipped for `raw` dimensions (their text comes straight from the feed).
4. **`render`** (script): render the issue to a **self-contained NYT-styled HTML file**
   in `output.dir` (Jinja2 template + the shared CSS inlined into `<head>`); copy cached
   images into `dist/assets/<date>/`. Optionally open it in a browser.

### The manifest contract
`out/manifest.json` is the **single source of truth** passed between stages. Shape:

```json
{
  "issue": { "date": "2026-06-26", "title": "...", "volume": 1, "number": 3 },
  "dimensions": [
    {
      "name": "Frontier Labs",
      "blurb": "What the leading labs shipped",
      "summary_mode": "rewrite",
      "items": [
        {
          "title": "OpenAI releases …",
          "url": "https://…",
          "source": "openai.com",
          "published": "2026-06-24",
          "image": "assets/2026-06-26/openai-1.jpg",
          "raw_text": "feed description text…",
          "summary": "Claude-written prose (empty until 'write' stage)",
          "origin": "feed"
        }
      ]
    }
  ]
}
```

`render` validates this against a schema before producing HTML. Because every render
target consumes this same manifest, **additional targets (e.g. an Eleventy content file
in v2) can be added without changing the fetch/search/write stages.**

---

## 3. Project structure

```
the-week-intelligencer/
├── SPEC.md                         # this file
├── README.md                       # quickstart (written during build)
├── pyproject.toml                  # uv-managed; runtime + dev deps
├── .gitignore                      # out/, dist/, .env, __pycache__, caches
├── .env.example                    # any optional API keys (NEWSAPI_KEY, …)
│
├── .claude/
│   └── skills/
│       └── the-week-intelligencer/
│           └── SKILL.md            # orchestrator: runs the pipeline above
│
├── config/
│   └── dimensions.yaml             # publication meta, output settings, dimensions
│
├── src/intelligencer/              # the Python package (the "generator")
│   ├── __init__.py
│   ├── cli.py                      # `intelligencer fetch|render|validate`
│   ├── config.py                   # load + validate dimensions.yaml
│   ├── feeds.py                    # RSS/Atom + api fetch/parse
│   ├── images.py                   # og:image extraction + optional caching
│   ├── manifest.py                 # manifest schema + (de)serialize
│   └── render.py                   # manifest → self-contained HTML (Jinja2)
│
├── templates/
│   ├── issue.html.j2               # NYT broadsheet template (Jinja2)
│   └── intelligencer.css           # NYT styling (inlined into <head> at render)
│
├── samples/
│   └── 2026-06-26.html             # golden example issue (for tests + preview)
│
├── tests/
│   ├── fixtures/                   # canned RSS/Atom + HTML (no live network)
│   ├── test_config.py
│   ├── test_feeds.py
│   ├── test_images.py
│   ├── test_manifest.py
│   └── test_render.py
│
├── out/                            # working dir (gitignored): manifest.json, image cache
└── dist/                           # rendered issues + assets (gitignored)
```

**Skill discovery:** the skill is project-local under `.claude/skills/`, discovered when
Claude Code runs from this directory. Optionally symlink it into `~/.claude/skills/`
for global invocation.

---

## 4. Configuration

Single file: `config/dimensions.yaml`. Editing it is the primary way to change output.

```yaml
publication:
  title: "The Week Intelligencer"
  subtitle: "A weekly briefing on AI and the work it's reshaping"
  first_issue_date: 2026-06-26     # used to compute Vol./No.
  timezone: "Asia/Singapore"

output:
  dir: "./dist"                    # where <date>.html and its assets are written
  images: cache                    # cache (download alongside) | hotlink (source URL)
  open_after_render: false         # open the file in a browser when done

defaults:
  summary: rewrite                 # raw | rewrite | synthesize   (per-dimension override)
  max_items: 5

dimensions:
  - name: "Frontier Labs"
    blurb: "What the leading labs shipped this week"
    summary: rewrite
    max_items: 6
    sources:
      - { type: feed,   url: "https://openai.com/blog/rss.xml" }      # deterministic
      - { type: feed,   url: "https://www.anthropic.com/rss.xml" }    # deterministic
      - { type: api,    provider: newsapi, query: "AI model release", key_env: NEWSAPI_KEY }
      - { type: search, query: "frontier AI lab news this week" }     # Claude web search

  - name: "AI Spending & Capex"
    summary: synthesize
    sources:
      - { type: feed,   url: "https://www.datacenterdynamics.com/rss/" }
      - { type: search, query: "AI datacenter capex spending this week" }

  - name: "China AI"
    summary: rewrite
    sources:
      - { type: search, query: "China AI model release news this week" }

  - name: "TikTok / Reels AI Trends"
    summary: raw                    # cheapest: snippet ~verbatim, ~no write tokens
    sources:
      - { type: search, query: "TikTok AI viral trend this week" }
```

### Source types
| `type`   | Determinism      | Who fetches      | Token cost to gather |
|----------|------------------|------------------|----------------------|
| `feed`   | deterministic    | Python script    | none                 |
| `api`    | deterministic    | Python script    | none                 |
| `search` | non-deterministic| Claude WebSearch | yes                  |

### Summary modes (per-dimension token lever)
| mode         | Behaviour                                            | Token cost |
|--------------|------------------------------------------------------|------------|
| `raw`        | use feed/snippet text ~verbatim                      | ~none      |
| `rewrite`    | Claude rewrites each item into NYT prose             | medium     |
| `synthesize` | Claude reads several items → one combined section    | highest    |

### Validation rules
- Every dimension needs ≥1 source and a unique `name`.
- `api` sources naming a `key_env` must find that env var, or the source is skipped with
  a warning (the issue still builds).
- `output.dir` is created if missing.
- Unknown `type`/`summary` values fail validation loudly.

---

## 5. Commands

Python env via **uv**. The skill calls these; the user can run them directly too.

| Command | Purpose |
|---|---|
| `uv sync` | install deps |
| `uv run intelligencer validate` | validate `config/dimensions.yaml` |
| `uv run intelligencer fetch` | deterministic gather → `out/manifest.json` |
| `uv run intelligencer render` | manifest → self-contained HTML in `./dist` |
| `uv run intelligencer render --open` | render, then open the issue in a browser |
| `uv run intelligencer fetch --dry-run` | fetch without writing the cache |
| `uv run pytest` | run the test suite |
| `uv run ruff check . && uv run black --check .` | lint + format check |

**Skill invocation:** from the project directory, ask Claude Code to *"generate this
week's Intelligencer issue"* (or invoke the skill by name). The skill runs
`validate → fetch → [search] → [write] → render` and reports the output HTML path.

---

## 6. Code style

- **Python 3.12+**, full type hints, `ruff` + `black`, small single-purpose modules.
- **Stdlib-first**; minimal runtime deps: `feedparser`, `httpx`, `pyyaml`,
  `selectolax` (or `beautifulsoup4`) for `og:image`, `jinja2` for HTML render. No LLM
  SDK — the LLM is the session.
- **Fail-soft:** one dead feed, missing image, or absent API key never aborts the issue;
  it logs a warning and continues. The issue is best-effort but always builds.
- **Network discipline:** every HTTP call has a timeout, a retry-with-backoff, and a
  descriptive User-Agent; respect `robots.txt` and per-host rate limits.
- **Deterministic output:** given the same manifest, `render` produces byte-identical
  HTML (stable ordering, CSS inlined from the checked-in stylesheet) — so golden tests work.
- **Config is data, code is logic:** no source URLs, queries, or paths hardcoded in
  Python — all live in `dimensions.yaml`.
- **YAML keys** are `snake_case`.

---

## 7. Testing strategy

- **No live network in the suite.** `tests/fixtures/` holds canned RSS/Atom feeds and
  HTML pages; `feeds`/`images` are tested against them.
- **Unit:**
  - `test_config` — valid configs load; bad `type`/`summary`/missing sources fail clearly.
  - `test_feeds` — RSS + Atom fixtures parse to the expected item fields; malformed feed
    degrades gracefully.
  - `test_images` — `og:image` extracted from fixture HTML; missing tag → `None`, no crash.
  - `test_manifest` — schema round-trips; invalid manifest rejected by `render`.
  - `test_render` — golden test: fixture manifest → byte-compare against
    `samples/2026-06-26.html`.
- **End-to-end dry run:** a `tests/fixtures/config.sample.yaml` with only `feed` sources
  (pointing at fixture files via `file://`) runs `fetch → render` with zero network and
  zero tokens, producing a complete HTML issue — proving the deterministic path
  top-to-bottom.
- **Optional `--live` smoke test** (not in CI): hits a couple of real feeds to catch
  upstream format drift.
- **Not unit-tested:** Claude's search/summaries (non-deterministic). They are constrained
  instead by the manifest schema and by the boundaries in §8.

---

## 8. Boundaries

### Always
- **Attribute everything.** Every item carries a working hyperlink to its original source;
  preserve the source name.
- **Prefer the cheap path.** Route `feed`/`api` through the script (zero gather tokens);
  only spend Claude on `search` sources and `rewrite`/`synthesize` summaries.
- **Fail soft and disclose.** A dead source is skipped with a visible note, never silently
  dropped or invented around.
- **Respect sources.** Honor `robots.txt`, ToS, and rate limits; identify with a real
  User-Agent; never bypass paywalls.
- **Keep secrets out of git.** API keys live in `.env` / env vars (referenced via
  `key_env`), never in `dimensions.yaml` or committed files.

### Ask first
- Before adding any **paid or keyed API** source.
- Before adding a non-trivial dependency.
- Before any step that **writes outside** the project's `output.dir`.

### Never
- **Never fabricate** news, quotes, numbers, dates, or links; never state more than the
  source supports.
- **Never generate or insert AI imagery** — article preview images only.
- **Never hotlink** images when `images: cache` is set.
- **Never call the Anthropic API** — all LLM work is the Claude Code session.

---

## 9. Future (v2, parked)
- **Eleventy publish target** — a second render target that consumes the same manifest to
  emit an 11ty content file + assets + a thin Nunjucks wrapper layout, giving the site
  archive, RSS, and nav. Additive; v1's fetch/search/write/render stays unchanged.
- Scheduled runs (launchd/cron wrapping the manual command).
- "Print to PDF" / EPUB export from the rendered HTML.
- Email edition (inline-CSS render of the same manifest).
- De-duplication across dimensions; per-source recency windows; trend charts.
```
