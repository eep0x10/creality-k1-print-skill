# Working on this project with an AI

Read [AGENTS.md](../AGENTS.md) first. Other hosts may not discover that file automatically: explicitly give the agent the startup prompt in [continuity](CONTINUITY.md). A text file cannot grant terminal/network access, change a model's capabilities or guarantee compliance.

## Understand the boundaries

| Surface | Owner and purpose |
| :--- | :--- |
| `skills/creality-k1-print/SKILL.md` | User-facing decision, preparation, preview and printing workflow |
| `skills/creality-k1-print/references/` | Setup, physical quality, camera and per-job details; installed with the skill |
| `skills/creality-k1-print/scripts/k1print/` | Single Python runtime for installed CLI and portable launcher |
| `tests/` | Offline regression tests with synthetic geometry and mocked HTTP |
| `scripts/` | Skill installer, publication audit and release builder |
| `docs/` | Architecture, current state, migration and contributor operation |
| Private workspace outside the checkout | Real models, photos, derived profiles, local connection config, jobs and receipts |

There is no backend service to deploy and no cloud account required. OrcaSlicer and Moonraker are external dependencies. Kiln is optional; do not patch its checks or claim it is installed/available on another host.

## Work from evidence

Read the smallest owning modules before changing a behavior. Trace inputs, state and output artifacts; do not guess command flags or configuration schema. Use `--help` and tests. For bugs, reproduce the narrow failure offline, identify a discriminating check and keep observation separate from hypothesis. Preserve concurrent edits and keep ownership explicit if using multiple agents.

New configuration/profile options must not silently fall back to stock values or run an external post-processing command. Preserve source profiles and capture provenance. Never treat import success, calibration flags or a manufacturer maximum as proof that a particular spool was physically calibrated.

## Keep physical operation separate

Developing a camera/printing feature is not permission to exercise real hardware. Unit tests, CI, installation and release review must remain offline with respect to printers. A user-requested print must use the skill: preferences, real preview, approval, identity/readiness checks, immutable validated bytes and one upload/start attempt. Keep the receipt on the same job directory.

For a restored job, begin by reading the receipt and current machine state when operation is authorized. If it was sent before, do not erase the receipt or replay its old approval. Prepare a fresh job and ask for a new preview approval for a deliberate repeat. Migration never starts a print.

## Finish a change so another agent can resume

Run checks appropriate to the delta. Preserve a clean, reviewable diff and cite actual tests, environment and limitations. Update [PROJECT_STATE.md](PROJECT_STATE.md) with the handoff date, verified behavior, limitations and next actions; keep volatile private job status in the private workspace. Keep CLI help, skill, examples and docs aligned. Use [RELEASING.md](RELEASING.md) only when publication is authorized.

Do not copy a chat transcript or host-specific global rules into the repository. Stable project constraints live in AGENTS; operational workflows live in the skill; versioned facts and remaining work live in project state. Preserve uncertain findings as uncertain.
