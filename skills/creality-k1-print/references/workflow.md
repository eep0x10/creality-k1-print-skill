# Per-job workflow

## Decision mode and priorities

Ask who should decide first. “Print it”, “just a test” and “resolve the rest” are not a decision-mode choice. If the user explicitly delegates configuration, inspect the model and choose. If the user chooses manual decisions, ask robustness versus filament savings and speed versus appearance/detail. Accept balanced values and preserve answers throughout this job.

The `strength` choices are `economy`, `balanced`, `robust`; `finish` choices are `fast`, `balanced`, `detailed`. They derive local profiles from the official installed resources. They do not guarantee mechanical performance or calibrated filament behavior. Select support/orientation based on geometry, visible faces, adhesion and strength rather than material cost alone.

## Prepare locally

```sh
k1print prepare model.stl --job-dir jobs/example --height-mm 80 --strength economy --finish detailed
```

Omit `--height-mm` to preserve source size. Scaling is uniform. Use a fresh job directory, not a prior approved job. STL and geometry-only 3MF are supported. External 3MF profiles, macros and pre-sliced commands are not executed. Other formats need an explicit conversion through an appropriate tool.

`--orient` asks Orca to propose automatic orientation. Compare it with the original when there is a plausible benefit. Preserve the model's appearance and assembly; do not silently split it or pretend the orientation heuristic is globally optimal. Deriving profiles alone is available through `k1print profiles --output-dir PATH`.

Review `job.json`, `preview.png` and `preview-report.json` in the resulting directory. The manifest binds the G-code, preview and report with SHA256. Artifacts are local and not intended for publication. A bounded sample may be used for the 3D image; full bounds and estimates must still be retained. Model and support paths use different colors.

## Approval and transmission

Show the real toolpath PNG inline, dimensions, estimated time and grams, orientation and support contact. Ask one final question approving this result with a clear plate and PLA loaded. The agent records which user message gave approval; a manually supplied text reference is not an authentication system.

A read-only check can run before approval:

```sh
k1print send jobs/example/job.json --dry-run
```

After explicit approval of the current artifacts:

```sh
k1print send jobs/example/job.json --approved-sha256 GCODE_SHA256_FROM_MANIFEST --approval-ref USER_APPROVAL_REFERENCE
```

Do not guess a hash or invent a reference. The bridge checks file integrity, supported commands, printer identity, idle state and the manufacturer's start/end macros. It sends immutable bytes with server checksum verification and automatic start disabled, rechecks readiness, then requests start once. A prior actual receipt prevents accidental resubmission.

If a POST times out or the response is uncertain, read the receipt and query `status` before deciding what happened. The request may already have started the job. Do not automatically rerun `send`, delete its receipt or upload again. A changed file requires another preview and approval.

Report the observed stage accurately: uploaded, preparation/heating, printing or completed. Permanent monitoring is not installed. A failed or interrupted print must be evaluated before another attempt.
