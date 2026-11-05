# Project state and next-agent handoff

Reviewed on **2026-11-05**. This is a repository continuity record, not a live printer report. The change described here is the v0.3.0 continuity release; use Git history, the release tag and CI to confirm the exact revision you have.

## Implemented

- Original K1 / PLA / 0.4 mm preparation through the locally installed OrcaSlicer, geometry-only STL/3MF handling and a PNG of deposited G-code paths.
- Decision-mode question before a new print, manual priority questions only when applicable, minimal unnecessary supports and final approval bound to artifact hashes.
- Native Moonraker transport: identity/readiness and maker macro checks, checksum upload with automatic start disabled, one start request and an exclusive receipt. No automatic POST retry.
- GET-only status and optional bounded JPEG/PNG snapshot, same-host URL validation, exact-origin key forwarding and no redirects. Relative webcam paths use the documented HTTP port 80 default, with an explicit proxy base option.
- Self-contained skill installation plus a Python package using the same runtime. Generic profile derivation remains available; `prepare --profiles-dir` preserves a complete local custom profile set in a new job.
- Physical-quality review instructions, migration/release guides and canonical agent instructions are included in the repository and release downloads.

## Historical evidence and its limits

The original setup exercised OrcaSlicer 2.4.2 on Windows with a synthetic overhang. Unit/CI checks use mocks and synthetic inputs. Windows/Linux CI does not prove that the Orca executable or camera on every OS/firmware works. macOS has not been physically exercised.

Separate private field records from 2026-11-01 confirmed upload/start on an original K1. Photos of a completed decorative print showed rough undersides, visible seams and layer texture, leading to the physical-quality procedure. These observations did not prove moisture, wrong temperature, PA zero or a mechanical fault.

A later Benchy finish candidate preserved original size, used no supports and reduced external motion demands. Its exact approved upload/start was recorded. **No subsequent Benchy completion/finish feedback was supplied before this handoff.** Do not infer successful completion, a currently active job or a calibrated material profile from those historical records.

The camera implementation passed offline tests, but the actual snapshot attempt on that setup reported no configured Moonraker webcams. A status field claiming camera readability did not establish a working snapshot. Hardware camera availability is still installation-specific.

Public source intentionally excludes all those private models, photos, generated G-code, connection settings and receipts. Preserving them for the owner requires the separate local migration archive described in [CONTINUITY.md](CONTINUITY.md).

## Open work

1. Obtain/inspect physical Benchy feedback when the user supplies it; choose focused calibration tests and record measured passing values. The current material profile remains a candidate.
2. Configure/verify the owner's camera only if requested and compatible with the actual firmware. Do not change printer services during a print.
3. Validate custom profile imports on additional real installed Orca releases and operating systems without overstating offline CI evidence.
4. Improve installer upgrade handling if needed; preserve local customization and runtime recovery. See the current supported procedures in [continuity](CONTINUITY.md).
5. Preserve checksum, receipt and preview/approval guarantees during any new feature. Do not add background monitoring or internet exposure implicitly.

## Refresh this record

After a meaningful change, update implemented behavior, executed validation and remaining work. Put the exact build revision and environment in the validation/release evidence. Keep private machine identifiers, account data and raw logs out of this file.
