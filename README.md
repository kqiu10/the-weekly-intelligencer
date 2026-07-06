# The Weekly Intelligencer

**A weekly digest of AI industry news, featuring updates on frontier labs, AI's rollout across industry, and the latest trending AI-generated images and video.**

[![Languages: English · 中文](https://img.shields.io/badge/languages-English%20%C2%B7%20%E4%B8%AD%E6%96%87-8b0000?style=flat-square)](https://kqiu10.github.io/the-weekly-intelligencer/issues/2026-07-05.html)
[![License: MIT](https://img.shields.io/badge/license-MIT-555?style=flat-square)](LICENSE)

*Every issue ships bilingual — 中文 by default, with an in-page language toggle in the masthead.*

## Preview
![Scrolling through a sample issue](samples/sample-scroll.gif)


## Dimensions
Four sections per issue: frontier AI labs, industrial AI adoption, Chinese cross-border brands × AI, and trending AI-generated media. All sources are **direct feeds and first-party scrapes** — no web search, no news aggregators; the deterministic scripts gather candidate pools and Claude only prunes them against each section's editorial bar.

**Frontier AI Research Labs**

The week's models, money, and announcements from the leading AI labs.

| AI Lab | Type | Source |
|---|---|---|
| Anthropic | `site` | Official newsroom |
| Google DeepMind | `feed` | Official RSS |
| OpenAI | `feed` | Official RSS |
| xAI | `site` | Official newsroom |
| DeepSeek | `feed` | Google News |
| Meta | `site` | Official AI blog |
| Alibaba Qwen | `feed` | Google News |

**The Intelligent Factory**

Frontier AI landing in industry — named manufacturers adopting AI for their own operations, plus substantive industrial-AI trade coverage (cobots, digital twins, robotics in production).

| Source | Type | Description |
|---|---|---|
| Manufacturing Dive | `feed` | Technology-topic RSS of the manufacturing trade press |
| DeepLearning.AI | `feed` | Andrew Ng's *The Batch* weekly, via a self-hosted RSSHub instance |

**Rewriting Cross-Border Branding** · 重塑跨境品牌

How AI is reshaping the way Chinese cross-border brands market and build themselves overseas — brand × AI stories, major brand milestones, and platform-AI features affecting Chinese sellers. Chinese-language sources, summarized in 中文.

| Source | Type | Description |
|---|---|---|
| 白鲸出海 | `feed` | Cross-border tech vertical, via self-hosted RSSHub |
| 36氪快讯 | `feed` | 7×24 tech newsflashes, via self-hosted RSSHub |
| 钛媒体 | `feed` | TMTPost latest, via self-hosted RSSHub |
| 雨果跨境 | `site` | First-party scrape of the cross-border e-commerce vertical |

**Trending Social Video & Images**

The week's most-shared AI-generated videos and images.

| Source | Type | Description |
|---|---|---|
| r/aivideo | `feed` | Reddit's weekly-top AI videos, native first-party RSS |


## Quick Start

```bash
git clone https://github.com/kqiu10/the-weekly-intelligencer.git
cd the-weekly-intelligencer
uv sync
```

<details open>
<summary><b>As a Claude Code skill (full issue)</b></summary>
Run that prompt in Claude Code from the project directory. 

```
generate this week's Intelligencer issue
```
</details>

<details>
<summary><b>By hand (deterministic only, zero tokens)</b></summary>

```bash
uv run intelligencer validate                 # check config/dimensions.yaml
uv run intelligencer fetch                    # feeds + sites → out/manifest.json
uv run intelligencer fetch --date 2026-06-28  # …or pin a specific past week
uv run intelligencer render --open            # manifest → dist/<date>.html
```

`--only <name>` narrows fetch/render to one dimension. With an all-`feed` + all-`raw` config this produces a complete issue with **zero** Claude tokens.
</details>

---

## Output

A self-contained `dist/<date>.html` with the styling inlined and its images/logos alongside in `dist/assets/`. The bundle is portable — open it locally or host the folder anywhere. The masthead range is week-to-date and fully deterministic (derived from the issue date, no wall-clock).


## Why Agent Skills

Most AI news tools force a choice: paraphrase everything through an LLM (expensive, hallucination-prone) or just dump raw feeds (no editorial judgment). Building this as a Claude Code **Agent Skill** splits the difference — **deterministic scripts do the fetching for free**, and the skill hands Claude Code only the part that needs judgment: pruning the candidate pools and writing summaries, done **in-session, with no API key**. The output is a **single portable HTML file**, not a service to host, and the whole run is reproducible from the manifest.

## Issues

| Issue | Date | Link |
|---|---|---|
| Issue 1 | 6/22-6/28 | [`Issue 1`](https://kqiu10.github.io/the-weekly-intelligencer/issues/2026-06-28.html) |
| Issue 2 | 6/29-7/5 | [`Issue 2`](https://kqiu10.github.io/the-weekly-intelligencer/issues/2026-07-05.html) |

## License

MIT — see [LICENSE](LICENSE).
