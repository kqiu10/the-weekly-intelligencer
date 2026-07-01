# The Weekly Intelligencer

A weekly, *New York Times*–style digest of AI-industry news, rendered as a
self-contained HTML issue you can open in any browser. Sections and sources are fully
configurable.

It runs as a **Claude Code skill**: deterministic gathering (RSS feeds, NewsAPI) is done
by Python scripts with **zero tokens**; web `search` sources and the editorial summaries
are written by Claude Code in-session — no Anthropic API key, no per-token cost.

## How it works

```
config/dimensions.yaml ─▶ fetch (feeds + NewsAPI, scripts) ─▶ out/manifest.json
                                  │  Claude: fill `search` + write summaries
                                  ▼
                          render (Jinja2 + NYT CSS) ─▶ dist/<date>.html
```

The `manifest` is the single source of truth; every stage reads and writes it.

## Setup

```bash
uv sync                    # install dependencies
cp .env.example .env       # then add your NEWSAPI_KEY (only needed for `api` sources)
```

## Usage

### As a Claude Code skill (full issue)
From the project directory, ask Claude Code to **"generate this week's Intelligencer
issue."** The skill validates config, gathers deterministic sources, fills `search`
sources via web search, writes summaries, and renders the issue. The orchestration lives
in `.claude/skills/the-weekly-intelligencer/SKILL.md`.

### By hand (deterministic only)
```bash
uv run intelligencer validate        # check config/dimensions.yaml
uv run intelligencer fetch           # feeds + NewsAPI → out/manifest.json
uv run intelligencer render --open   # manifest → dist/<date>.html
```
With an all-`feed` + all-`raw` config this produces a complete issue with **zero** Claude
tokens.

## Configuring dimensions

Each section ("dimension") in `config/dimensions.yaml` has a name, blurb, summary mode,
`max_items`, and a list of sources.

With `layout: by-source`, each source becomes its own card — a left rail with the
company's name over its logo, and its recent items alongside. Give the source a `label`
(the displayed name) and a `logo` slug matching a brand-colored SVG in
`src/intelligencer/assets/logos/<slug>.svg` (bundled: `openai`, `anthropic`, `deepmind`,
`qwen`, `xai`, `deepseek`, `meta`); the render copies referenced logos into the issue so
`dist/` stays self-contained.

Google News search feeds hand back opaque `news.google.com` redirect links and a generic
thumbnail on every item. Fetch resolves those redirects to the real publisher article (so
the link and its `og:image` work) and drops any preview image repeated across items, so
each story shows its own picture — or none, rather than boilerplate.

From that same article page, fetch also pulls the story's own **lede** — its first
`defaults.blurb_words` words (default 50, NYT-brief length; ~40–60), verbatim, the way a
newspaper reprints a wire story's opening rather than paraphrasing it, ending on a whole
sentence. It reads the leading paragraphs, and for JavaScript-rendered pages (no readable
`<p>` body) falls back to the page's `NewsArticle` JSON-LD (article body, else the
publisher's description). A blurb that merely repeats the headline (as Google News'
"Headline — Publisher" does) is hidden, never printed twice.

If an article can't be read at all (a hard scraper block, e.g. a Cloudflare 403 that a
browser User-Agent can't get past), the item has neither image nor blurb, so it's dropped
rather than shown as a bare headline — a company simply shows fewer stories (0–2).

| Source `type`   | Gathered by        | Token cost |
|-----------------|--------------------|------------|
| `feed`          | script (RSS/Atom)  | none       |
| `api` (NewsAPI) | script (NewsAPI)   | none       |
| `search`        | Claude web search  | yes        |

| `summary` mode | Behaviour                          | Token cost |
|----------------|------------------------------------|------------|
| `raw`          | feed/snippet text verbatim         | ~none      |
| `rewrite`      | Claude rewrites each item          | medium     |
| `synthesize`   | Claude writes one combined section | highest    |

### NewsAPI
`api` sources are configured under `providers.newsapi`: the key is read from
`NEWSAPI_KEY` in `.env`, and `daily_request_limit` (default **100**) is a **hard cap**
enforced across runs via a persistent daily counter, with a response cache so repeat
runs don't spend quota.

## Output

A self-contained `dist/<date>.html` with the NYT broadsheet styling inlined. The `dist/`
bundle is portable — open it locally or host it anywhere. (Publishing into an Eleventy
site is a planned v2; see `SPEC.md` §9.)

## Development

```bash
uv run pytest                            # tests (offline, deterministic)
uv run ruff check . && uv run black .    # lint + format
```

See `tasks/SPEC.md` for the full specification and `tasks/plan.md` for the build plan.
