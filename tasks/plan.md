# The Weekly Intelligencer — Build Plan

- **Spec:** `SPEC.md` (v1, HTML output only)
- **Generated:** 2026-06-26
- **Execution:** `/build auto` — autonomous TDD. One failing test → minimal code → full
  suite → build → **one commit per task**, committed directly to `main` (solo dev — no
  feature branch). Runs through all
  tasks after a single approval; stops only on a blocker, spec ambiguity, or a
  high-risk/irreversible step.

## Approach
Work is sliced **vertically**: every task carries one *complete* path (config → fetch →
manifest → render → HTML), then later tasks thicken it. Task **A2 is a walking
skeleton** — the whole spine connected with one feed — so the architecture is proven
end-to-end before any enrichment. The deterministic, zero-token product is fully done by
the end of Phase B; Claude-in-the-loop is added last (Phase C).

## Dependency graph
```
A1 ─► A2 ─► B1 ─► B2 ─► B3 ─► C2 ─► D1
(scaffold) (skeleton)(images)(NYT  (validate (skill) (docs)
                            layout) +raw+
                                   failsoft)
                              └─► C1  (newsapi · keyed · hard 100/day · INCLUDED)
```
`C1` (newsapi) needs the fetch path (post-A2); run it after B3.
`C2` needs the complete deterministic pipeline (post-B3). `D1` needs everything shipped.

---

## Phase A — Walking skeleton

### A1 · Scaffold & tooling
- **Goal:** a runnable, testable Python project skeleton.
- **Touches:** `pyproject.toml` (uv; runtime: `feedparser`, `httpx`, `pyyaml`,
  `beautifulsoup4`, `jinja2`, `python-dotenv`; dev: `pytest`, `ruff`, `black`), `src/intelligencer/__init__.py`,
  `src/intelligencer/cli.py` (subcommands `fetch`/`render`/`validate`, stubbed),
  `tests/`, `.env.example`, `.gitignore` (+ `out/`, `dist/`).
- **RED:** `tests/test_cli.py::test_help` expects `--help` to list the three subcommands.
- **Acceptance:** `uv sync` installs; `uv run intelligencer --help` lists subcommands;
  `uv run pytest` runs; `ruff`/`black` configured.
- **Verify:** run those four commands; all exit 0.

### A2 · Skeleton: feed → manifest → HTML (thinnest end-to-end)
- **Goal:** prove the full spine with one feed, fully offline.
- **Touches (thin slice of each):** `config.py` (load minimal YAML), `feeds.py`
  (fetch/parse one RSS via httpx+feedparser, `file://` supported), `manifest.py`
  (minimal schema + JSON I/O), `render.py` (minimal Jinja2 template → `dist/<date>.html`),
  `cli.py` (wire `fetch`→`out/manifest.json`, `render`→html). Fixtures:
  `tests/fixtures/sample_feed.xml`, `tests/fixtures/config.skeleton.yaml`.
- **RED:** `tests/test_e2e_skeleton.py` — run `fetch` then `render` on the skeleton
  config; assert `dist/<date>.html` exists and contains each feed item's title + link.
- **Acceptance:** `intelligencer fetch && intelligencer render` yields an HTML file with
  the feed's items as working links; e2e test green; **zero network** (`file://`),
  **zero tokens**.
- **Verify:** run both commands; open the HTML; `pytest -k skeleton`.
- **⛳ Checkpoint 1:** pipeline walks. (Auto-mode continues; flagged for your review.)

---

## Phase B — Deterministic product (zero tokens)

### B1 · Preview images (og:image) end-to-end
- **Goal:** each item shows its source preview image.
- **Touches:** `images.py` (fetch article page, extract `og:image` via BeautifulSoup;
  `cache` downloads to `dist/assets/<date>/`, `hotlink` keeps the URL; missing → `None`,
  fail-soft), wired into `fetch`; `manifest` gains `image`; template renders `<img>` + CSS.
  Fixtures: `article_with_og.html`, `article_without_og.html`.
- **RED:** `tests/test_images.py` — extract from fixture HTML; missing tag → `None`.
- **Acceptance:** `cache` mode downloads images and the manifest references relative
  paths; render shows them; a missing image degrades cleanly (no broken layout).
- **Verify:** `pytest test_images` + e2e; open HTML, images visible.

### B2 · Full NYT broadsheet + multiple dimensions + golden
- **Goal:** the real styled, multi-section issue.
- **Touches:** `config` (N dimensions + `defaults`), `manifest` (multi-dimension + issue
  `volume`/`number` from `first_issue_date`), `templates/issue.html.j2` (serif masthead
  w/ title+subtitle+date+vol/no, lead-story treatment, per-dimension sections w/ blurb,
  item cards w/ image+headline+summary+source link, multi-column responsive),
  `templates/intelligencer.css` (inlined at render). Golden: `samples/2026-06-26.html`.
- **RED:** `tests/test_render.py::test_golden` — multi-dimension fixture manifest →
  byte-identical to `samples/2026-06-26.html`.
- **Acceptance:** deterministic byte-identical render; visually reads as an NYT broadsheet.
- **Verify:** `pytest test_render`; open the sample; eyeball masthead/columns/lead.

### B3 · Validation, `raw` summaries, fail-soft
- **Goal:** complete + harden the deterministic product.
- **Touches:** `config.py` full validation + `validate` command (unique names, ≥1 source,
  known `type`/`summary`, `key_env` presence → warn, create `output.dir`); `raw` summary
  mode end-to-end (use `raw_text` ~verbatim → an all-feed+all-raw config renders with
  **no Claude at all**); fail-soft surfacing (dead source skipped with a visible note).
- **RED:** `tests/test_config.py` (good passes, bad fails loudly) + `tests/test_failsoft.py`
  (dead feed skipped with note, issue still builds).
- **Acceptance:** `validate` behaves; an all-feed+all-raw config runs `fetch → render`
  with zero network/zero tokens producing a complete issue; dead source → visible note.
- **Verify:** run `validate` on good+bad configs; run the offline e2e dry-run; `pytest`.
- **⛳ Checkpoint 2:** complete deterministic, zero-token issue. (Auto-mode continues;
  strongly recommended you eyeball the rendered issue here.)

---

## Phase C — Agentic layer (Claude-in-session)

### C1 · `api` source type (newsapi) — **INCLUDED**
- **Goal:** deterministic, keyword-searchable `api` sources via NewsAPI, under a hard daily
  quota.
- **Touches:** `providers/newsapi.py` (call the `everything` endpoint with the source's
  `query`; map results → manifest items), wired into `fetch`. Driven by `providers.newsapi`:
  `key_env` (key from `.env`, never committed), `daily_request_limit` (**hard cap, default
  100**), `cache_ttl_hours`.
- **Hard limit:** a persistent daily counter (`out/newsapi_usage.json`, keyed by date) is
  checked *before* every request; at the cap, remaining `api` requests are skipped fail-soft
  with a warning. A response cache (`out/cache/newsapi/`, TTL `cache_ttl_hours`) serves
  repeats so re-runs during a day don't spend quota.
- **RED:** `tests/test_api_newsapi.py` (all mocked, no live key): mocked response → items;
  **limit enforced** (limit=2, attempt 3 → 3rd skipped + warned, counter persists); a cache
  hit does **not** increment the counter; missing/empty key → skip + warn, issue still builds.
- **Acceptance:** never exceeds `daily_request_limit` across runs; missing key degrades
  cleanly; live use reads `NEWSAPI_KEY` from `.env`.
- **Verify:** `pytest test_api_newsapi`; optionally one real call with the key.

### C2 · `SKILL.md` orchestrator + search / rewrite / synthesize
- **Goal:** the full product, incl. agentic gathering + editorial writing.
- **Touches:** `.claude/skills/the-weekly-intelligencer/SKILL.md` (frontmatter `name` +
  `description`; body: run `validate → fetch`; for each `search` source use
  WebSearch/WebFetch to fill manifest placeholders; write summaries per `summary_mode`
  (`raw` skip / `rewrite` each / `synthesize` combine) + optional editor's note; curate
  lead + order; `render`; report path; enforce §8 boundaries — attribute, no fabrication,
  no AI imagery, no API). Optional `intelligencer compose` helper to merge Claude-written
  summaries into the manifest deterministically.
- **No automated test** (your call — the behavior isn't unit-testable, so we skip the
  structural test too). The one task outside the TDD loop: author + commit `SKILL.md`,
  then verify by hand.
- **Acceptance (behavioral, MANUAL):** invoking the skill in Claude Code produces a real
  issue — deterministic feeds (zero tokens), `search` sources filled with real items,
  summaries per mode, every item attributed, no fabrication. *Not unit-testable
  (non-deterministic); verified by you.*
- **Verify:** run the skill on a config that includes a `search` dimension; inspect links,
  images, summaries, attribution.
- **⛳ Checkpoint 3:** a real, live weekly issue — review quality / attribution / cost.

---

## Phase D — Polish & handoff

### D1 · Docs, sample, finalize
- **Goal:** shippable.
- **Touches:** `README.md` (quickstart: `uv sync` → edit `config/dimensions.yaml` → run
  the skill or `fetch`/`render`; explain source types, summary modes, the token model);
  ensure `samples/` issue is current; flip `SPEC.md` `Status` → Approved; final
  `ruff`/`black`/`pytest` pass; confirm `.gitignore`.
- **RED:** `tests/test_smoke_readme.py` (optional) — the documented offline quickstart
  command sequence produces an HTML file.
- **Acceptance:** a new reader can go from README to a rendered issue; all tests + lint green.
- **Verify:** follow the README from scratch; `pytest`; `ruff check . && black --check .`.

---

## Git & stop conditions
- **Commit directly to `main`** (solo developer — no feature branch). The plan is a single
  prep commit, then one commit per task (`git add` only that task's files + its status
  update). No `push` unless you ask.
- **Stop and ask** on: a test that won't pass / build break without an obvious fix; spec
  ambiguity; or any high-risk/irreversible step (secrets, deletions, deploy, anything not
  undoable via `git revert`). C1 (keyed API) and C2 (live web/tokens) are flagged above.
