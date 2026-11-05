# Testing and the limits of the evidence

## Reproduce software checks

Windows:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e .
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe scripts/audit_publication.py
```

On Linux/macOS use `python3 -m venv .venv` and replace `.venv/Scripts/python.exe` with `.venv/bin/python`. Tests do not contact a printer. HTTP behavior is mocked; geometry and fake slicer fixtures are created in temporary directories.

Coverage includes approval absence, modified artifacts, wrong/busy printer, start/upload uncertainty, receipt reuse, exact arc bounds, 3MF transforms/units and hostile archive/XML forms, profile inheritance, real-toolpath reports, CLI quoting and installer non-overwrite behavior. CI runs the tests on Windows and Linux. The workflow status, rather than a hardcoded test-count badge, is the current CI evidence.

Camera checks use synthetic JPEG/PNG bytes and mocked HTTP responses, never photos from a real camera. They cover discovery/selection, relative URL resolution, explicit configuration, GET-only behavior during an existing print, origin-specific credentials, invalid images, response limits and exclusive local output. A software pass does not verify that a particular K1 has a reachable camera service.

Custom-profile tests verify that complete local settings are copied byte-for-byte and actually passed to the slicer instead of being replaced by generic values. Rejected inputs include wrong machine/nozzle/material, inheritance, invalid/non-finite/duplicate JSON values and host post-processing. Installer checks cover non-overwrite and recovery of a recognized local runtime. Release tests cover clean-commit provenance, dirty-tree rejection and per-file archive hashes.

## Real slicer check

The public preparation pipeline was exercised offline with OrcaSlicer 2.4.2 on Windows and an original synthetic overhang. It produced G-code, estimates and a preview; the full generated job passed local validation without any printer HTTP requests. The README image comes from this synthetic job.

The underlying workflow also previously confirmed a start on one original K1. That separate physical run does not prove completion or finish quality, and its private model/configuration are not distributed. Development and CI never use it as a fixture.

For the v0.3.0 continuity review, a separate offline replay on Windows/OrcaSlicer 2.4.2 imported the owner's preserved private profile set. It retained the supplied 215 C / flow 0.98 / layer 0.12 mm and produced a validated real-toolpath job with the same displayed slicer estimate (1h53m05s /12.03g) as the historical finish candidate. No printer calls, upload or start occurred. This demonstrates profile reuse on that software setup, not physical calibration or byte-identical output across machines. The private source/profile/job data is not a public test fixture.

## Skill behavior checks

A text-only baseline without the new skill proceeded directly to preparation. A forward test caught an ambiguity in “resolve the rest”; the instruction was tightened so generic print requests do not silently choose a mode. Rechecks covered first-question ordering, explicit delegated mode, answered manual preferences, and invalidation of approval when the file changes. These are scenario checks of instructions, not a guarantee that every model/host always follows them.

The normal skill schema validator checks naming/frontmatter. The publication audit checks assets, local Markdown links, allowed files and common private-data patterns. Neither proves physical printer safety. Read [operating limits](../skills/creality-k1-print/references/operating-limits.md) before hardware use.
