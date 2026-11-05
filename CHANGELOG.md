# Changelog

## 0.3.0 — 2026-11-05

- Added complete local custom profile reuse through `prepare --profiles-dir`, preserving supplied values and original bytes with provenance. Imports remain physically unverified and keep the existing final G-code/approval checks.
- Added runtime repair for recognized skill installations without replacing custom instructions/scripts, and excluded generated package metadata from installation copies.
- Bound release ZIPs to clean committed source with `RELEASE-MANIFEST.json`; added Git-independent verification for ZIP/extracted downloads.
- Published physical-quality review/calibration guidance previously available only in the originating local installation.
- Expanded canonical agent instructions and added AI, project-state, cross-PC continuity and release guides. Public source and private owner records remain separate.

## 0.2.0 — 2026-11-01

- Added GET-only camera snapshots, local camera configuration, bounded image validation and private output handling.

## 0.1.0 — 2026-11-01

- Initial reusable skill, original K1/PLA preparation, real toolpath previews and approval-bound native Moonraker transport.
