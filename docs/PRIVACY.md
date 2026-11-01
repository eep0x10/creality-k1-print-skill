# Privacy and local data

The core needs no cloud account, OpenAI API key or Kiln account. Models, profiles, previews and receipts remain in the selected local job directory. Requests go to the printer URL the user configures. An agent hosting the conversation has its own data policy; this package does not change that policy.

## Keep private

- Printer URL, actual hostname, local filesystem locations and optional Moonraker API keys.
- Model files and their licenses, sliced G-code, job manifests, receipts and slicer logs.
- Browser sessions and downloaded source files.

The repository excludes jobs, outputs, local config, environment files, logs, databases, model/G-code files and binary installers. Configuration stores only the optional API-key environment variable's name. The key is read locally and attached only to requests to the configured printer. Avoid putting credentials in a URL. TLS verification is not disabled.

The installer does not overwrite existing skills or copy hidden files, bytecode or virtual environments. The release builder uses tracked repository files and runs a publication audit before producing a package. The audit is a best-effort check, not a secret-detection guarantee; inspect the Git diff and package manifest before publishing.

Discovery is explicit, read-only and limited to a small private IPv4 subnet. It does not scan public networks or automatically choose a VPN interface. No tunnel, public port, telemetry service or permanent monitoring daemon is installed.

The distributed previews use an original synthetic example. Private printer screenshots, downloaded models and real user jobs are not published as demo evidence.
