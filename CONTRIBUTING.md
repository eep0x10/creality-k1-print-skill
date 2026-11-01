# Contributing

Use a new branch and a local Python environment. Install with `python -m pip install -e .` and run `python -m unittest discover -s tests -v` before submitting changes. Keep helpers inside the self-contained skill folder so the installed skill and CLI use the same implementation.

Add regression tests for changed behavior. Printer interactions in tests must be mocked. Never start, heat, home, update or stop a real printer to validate a pull request. Synthetic geometry is preferred; do not add downloaded models unless their license explicitly permits redistribution and the provenance is recorded.

Changes to approval, artifact hashes, transmission order, retries, identity checks, arc geometry or maker macros need independent review. An uncertain request may have succeeded; do not add blind retries. Preserve the distinction between instructions, software checks and physical evidence.

Keep README languages, CLI help and setup/workflow references aligned. Run the publication audit and inspect the package before publishing. Do not submit private configurations, account screenshots, logs, actual printer identities or jobs.

See [SECURITY.md](SECURITY.md) for reporting sensitive issues without publishing private evidence.
