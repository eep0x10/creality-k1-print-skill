# Creality K1 Print Skill

This repository distributes a self-contained agent skill and a local Python CLI for original Creality K1 printers using PLA, a 0.4 mm nozzle, OrcaSlicer and a working Moonraker service.

- Never operate a real printer during repository development or tests. Use HTTP mocks and synthetic geometry. Do not modify any printer, firmware, active job or existing personal installation.
- Keep all distributable helpers under `skills/creality-k1-print/scripts/k1print/`. The root Python package installs that same code; the skill can also run through `scripts/k1.py` without installing the package.
- The skill first asks whether the user delegates decisions or wants to choose. In manual mode ask strength versus filament savings and speed versus detail. Always minimize unnecessary support and obtain final approval of the actual G-code preview before upload/start.
- Approval binds the exact G-code hash. No automatic retries of upload/start, no print in setup/prepare/dry-run, no standing print consent.
- No hardcoded personal paths, printer addresses/hostnames, credentials, account identifiers, downloaded third-party models or private logs. Kiln is optional and not a runtime dependency.
- Use original synthetic examples and preserve source/licensing attribution for external tools. Do not bundle OrcaSlicer binaries or third-party profiles.
- Run `python -m unittest discover -s tests -v`, the skill validator and publication audit. Test changed behavior with regression cases. Keep documentation aligned with CLI behavior and distinguish local validation from physical print evidence.
