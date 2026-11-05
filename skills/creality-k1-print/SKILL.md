---
name: creality-k1-print
description: Prepare PLA models for an original Creality K1, preview OrcaSlicer toolpaths, send approved G-code through Moonraker, and show an on-demand local camera snapshot. Use for K1 printing, STL/3MF preparation, connection setup and camera/status requests.
---

# Creality K1: prepare, preview, approve, print

Use the user's language. This skill supports an original K1 with a 0.4 mm nozzle, PLA, a local computer with OrcaSlicer, and a working Moonraker service. Root access alone does not establish that Moonraker works. Do not modify firmware or an existing print as part of setup.

## Read status or show a camera photo

For a status/photo request about an existing print, skip the new-project preference questions. Read [camera setup and capture](references/camera.md). Use `snapshot --output <local-private-folder>/status.jpg` to retrieve one real frame and the observed printer state. If cameras are ambiguous, select the intended configured camera by name. Do not guess a universal K1 camera endpoint.

Show the returned local image inline using an absolute filesystem path. Label the retrieval time and the separately observed printer state; they are not an atomic observation, and a server may return a cached frame. Distinguish a camera photo from a sliced preview. Describe only what is visible; a photo alone does not prove adhesion, successful completion or absence of defects. Report an unavailable camera honestly and retain status-only consultation as a fallback.

Capture on demand; no recurring monitoring or webcam reconfiguration is included. Do not publish photos, camera URLs or local metadata. Displaying a photo in chat makes it available to the chat host under its own data policy. Snapshot requests never authorize pause, cancel, resume or a new print.

## Start each new print with the decision mode

Before preparing each new project, ask **first and by itself** whether the user wants the GPT to evaluate the model and decide the settings or prefers to make those choices. Example: “Quer que eu avalie o projeto e decida as configurações, ou prefere escolher?”

- If the current request already clearly chooses the decision mode (for example, “quero que o GPT escolha as configurações” or “prefiro eu escolher”), honor it without asking again. Generic phrases such as “print it”, “just a test”, “resolve the rest” or a request to minimize supports do not answer this first question. An existing selected mode for this same job persists through follow-ups.
- In delegated mode, inspect geometry and purpose, then choose settings. Do not ask the two preference questions merely to follow a checklist.
- In manual mode, ask about **robustness versus filament savings** and **speed versus appearance/detail** before preparing. Explain tradeoffs briefly and accept a balanced preference.
- Always minimize unnecessary supports while preserving the requested strength, detail and printability. “GPT decides everything” delegates preparation, not permission to start printing.

## Set up only what is needed

For installation or a missing connection, read [setup](references/setup.md). Use the packaged launcher, `python <skill-folder>/scripts/k1.py`, or the installed `k1print` command. Use `--help` to confirm options. Configuration and job outputs are local and must not be published.

If the source is a URL, obtain the model through the source's normal authorized download flow using available browser or connector tools. Respect authentication, licenses and paid access; do not infer permission to buy a model. The CLI accepts local files. If access is unavailable, ask for the file or the necessary login, rather than substituting another model.

## Prepare and compare

Read [the workflow](references/workflow.md) for commands and [operating limits](references/operating-limits.md) when a model or printer falls outside the supported shape.

For a first spool/material combination, an appearance-sensitive print, or feedback on a physical result, read [physical quality and calibration](references/physical-quality.md). A generic profile and a valid toolpath are not proof of physical finish. Preserve the actual spool identity and measured calibration locally; do not substitute generic derived values for a validated spool profile silently.

1. Inspect the model, units, components, dimensions, base contact and overhangs. Use geometry only from an external 3MF; never execute its embedded G-code or reuse its machine start commands.
2. Apply requested size uniformly. Preserve shape and assembly transforms. Do not silently cut, split, simplify or repair a model in a way that changes its appearance or fit.
3. Derive settings from the installed official K1 profiles or explicitly reuse a reviewed complete private profile set with `--profiles-dir`. Do not mix custom profiles with priority flags or silently replace known spool settings. Choose walls/infill for strength or economy and layers/speeds for speed or detail. A stock or imported profile is a starting point until its physical calibration is verified.
4. Compare orientations when there is a meaningful alternative. Evaluate support contact on visible surfaces, stability, strength, material and time; auto-orient is a candidate, not an optimum guarantee.
5. Slice locally and inspect the actual deposited G-code preview. Keep work in a new job directory. Label any display sampling; preserve full bounds and estimates in the report.

`prepare` never uploads, heats, moves or starts the printer. Do not start through another tool, raw G-code, a macro, a queue or a file-upload flag while approval is pending.

## Present exactly what will print

Show the local preview PNG inline, with finished dimensions, estimated duration and grams, the chosen orientation, and support color/placement. A render of the STL is not a sliced preview. Mention material uncertainties that change the decision; do not bury the user in implementation details.

Then ask **one final question** authorizing upload and start of this result, with the plate clear and PLA loaded. Keep the G-code hash and artifact paths in the local manifest so the approval binds this exact file. A generic “print it” before seeing the preview is not final approval of a later result.

## Send only after approval

- After explicit approval, use the native `send` command with the job manifest, approved G-code SHA256 and a reference to the user's approval. Never invent approval or treat the reference string as proof by itself.
- Revalidate the local files, printer identity, idle state and maker start/end macros. Upload with automatic start disabled and server checksum verification, recheck idle state, then request start once.
- Do not retry an uncertain upload/start automatically. Inspect the saved receipt and printer state. The request may already have succeeded; do not create a duplicate print.
- Confirm the matching filename and printing state. Distinguish “accepted/preparing/heating” from actual layer deposition and from completion. Do not promise ongoing monitoring without an active monitoring mechanism.
- A changed G-code or preview requires a new preview and approval. The choice to delegate settings never creates standing printing consent.

Development, examples and validation must use mocks or synthetic jobs. Never use a reader's real printer to test an installation or publish private configuration, receipts, account sessions or third-party models.
