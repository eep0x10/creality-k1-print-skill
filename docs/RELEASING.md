# Release checklist

Publishing requires authorization from the current user. No real printer requests are part of a release. Preserve local data and inspect the diff before any push.

1. Update the version in `pyproject.toml` and `skills/creality-k1-print/scripts/k1print/__init__.py` together. Update CLI help, skill references, README and project state for the final behavior.
2. Run the commands in [TESTING.md](TESTING.md), inspect the complete staged manifest/diff and verify local links/assets. Run the skill schema validator if available; otherwise state that limitation. Never copy private examples into tests or docs.
3. Commit the reviewed change. `scripts/package_release.py` requires a clean committed tree and records the source commit and file hashes in the ZIP. Ignored local environments and validation output are not source files.
4. Push the authorized branch and inspect the GitHub CI results for **that exact commit**, not an earlier green run. Verify the rendered README, banner, diagrams and linked guides.
5. Build the release ZIP using `python scripts/package_release.py --output dist`. Preserve old archives; a conflicting archive name is refused. Confirm its contents include AGENTS, AI/continuity/state/release docs, skill, runtime, tests, license and original synthetic assets. `SHA256SUMS` hashes the complete archive.
6. Create the versioned GitHub release on that commit and upload the ZIP/checksum. Download the published artifacts into a new local folder, verify checksum, source manifest (`python scripts/verify_release.py PATH_TO_ZIP`) and expected files, and test a fresh clone/extracted installation offline. A hash manifest alone is not an independent signature: compare its commit with the authorized GitHub tag.
7. Verify the tag/commit, release assets, visibility and CI. Record actual evidence and limitations. Do not call compilation, unit tests or a recorded print start proof of physical finish.

Never attach the owner's migration archive, private job files, camera frames, local paths, credentials, databases or application sessions to a public release. See [PRIVACY.md](PRIVACY.md).
