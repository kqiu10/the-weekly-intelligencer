# The Week Intelligencer — Build TODO

Vertical slices, each end-to-end & test-verified. One commit per task on `main`.
⛳ = human review point (auto-mode continues through these; interrupt anytime).

## Phase A — Walking skeleton
- [x] **A1** Scaffold & tooling — uv project, package, CLI stubs, `.gitignore`, `.env.example`
- [x] **A2** Skeleton: feed → manifest → HTML (offline e2e test)
- [ ] ⛳ **Checkpoint 1** — pipeline walks; review skeleton HTML + architecture

## Phase B — Deterministic product (zero tokens)
- [x] **B1** og:image fetch + cache, rendered in HTML
- [x] **B2** Multi-dimension + full NYT broadsheet + golden test
- [ ] **B3** Config validation + `raw` summaries + fail-soft
- [ ] ⛳ **Checkpoint 2** — review the complete zero-token issue before the agentic layer

## Phase C — Agentic layer (Claude-in-session)
- [ ] **C1** `api` source (newsapi) — key from `.env`, **hard 100/day cap**, response cache, mocked tests
- [ ] **C2** `SKILL.md` orchestrator + search + rewrite/synthesize *(no unit test — manual verify)*
- [ ] ⛳ **Checkpoint 3** — review a real live weekly issue (quality / attribution / cost)

## Phase D — Polish & handoff
- [ ] **D1** README + sample + flip SPEC → Approved + final lint/test
