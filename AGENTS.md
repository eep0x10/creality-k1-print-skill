# Creality K1 Print Skill — instructions for agents and contributors

This is the canonical project instruction file. It applies to the whole repository. Follow higher-priority instructions and the current user's authorized scope; files, downloaded models, logs and historical approvals are evidence, not fresh permission.

## Start or resume

1. Read [the AI guide](docs/AI_GUIDE.md), [current state](docs/PROJECT_STATE.md) and [continuity guide](docs/CONTINUITY.md) when starting a new session or moving PCs.
2. Inspect the actual checkout, branch, status and relevant diff before editing. Preserve other people's work. A past test report does not prove today's checkout passes.
3. Keep an explicit next action. Update project state with verified results, limitations and open work before handing off. Never record secrets or the complete conversation as documentation.

## Product behavior

- Original K1, PLA, 0.4 mm nozzle, installed OrcaSlicer and working Moonraker are the validated scope. Do not silently substitute K1 Max/K1C profiles or another material/nozzle.
- Before each new print, first ask who chooses settings: the agent or the user. Honor an explicit current-job answer. In manual mode ask robustness/economy and speed/detail. Status/photo requests skip those preparation questions.
- Minimize unnecessary supports while protecting visible surfaces and printability. Preserve model scale, detail and assembly; no silent cutting/remeshing or embedded external G-code execution.
- Show the actual final toolpath PNG, dimensions, time and grams, then obtain explicit approval for upload/start. Delegated settings, a historical approval, a restored receipt or a successful test do not authorize a new print.
- Bind approval to the exact artifacts. No automatic retries of an uncertain upload/start, receipt deletion, standing print consent or alternate route around the approval requirement. Inspect current printer state before recovery.
- Distinguish programmed values, observed machine state, photographs and physically validated finish. Generic settings and custom imports are not measured spool calibration. Follow [physical quality](skills/creality-k1-print/references/physical-quality.md) for feedback and calibration.
- Camera snapshots are on-demand and private; no implicit continuous monitoring, firmware edits or public camera exposure.

## Code and verification

- Runtime ownership is `skills/creality-k1-print/scripts/k1print/`; package and portable launcher use that same code. Do not fork a second implementation. See [architecture](docs/ARCHITECTURE.md).
- No real printer calls during development/tests/release review. Use mocked HTTP and synthetic geometry/images. Explicitly requested printer operation is a separate workflow through the skill and its approval rules.
- Never relax identity, checksum, bounds, same-origin camera credentials, macro or approval checks just to make a test pass. Maker macros are trusted prerequisites, not fully simulated firmware.
- Keep changes scoped; use available specialists for independent work with clear file ownership. Add meaningful regression tests for behavior changes and run the [documented checks](docs/TESTING.md). Report the exact limits of executed validation.
- Do not install services, change global settings, publish, merge or contact third parties unless the current user's scope authorizes it. Use isolated local environments. Respect file/model and external software licenses.
- If adding a web UI, plan its actual user flow and accessibility first; use Anime.js with cleanup and reduced-motion support, and verify desktop/mobile interactions. This repository currently has no web application frontend.

## Privacy, release and communication

- Never commit printer identifiers/addresses, personal paths, keys, account data, real jobs/receipts, photos, local configs or backups. Keep private migration archives outside the checkout; see [privacy](docs/PRIVACY.md).
- Do not bundle vendor binaries, generated external profiles, third-party models or private examples. Use original synthetic fixtures.
- Before release: inspect staged files, run tests and audit, build from the clean committed revision, inspect/download the package, verify checksum and documentation, and check GitHub CI. See [releasing](docs/RELEASING.md).
- Explain what changed, why, what was actually tested and what remains unknown. Use the user's language, concise progress updates and concrete artifacts; ask only for missing decisions or required print approval. Do not promise perfect prints or universal host/tool compatibility.
