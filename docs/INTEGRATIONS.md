# Integrations and evidence

## OrcaSlicer

The package invokes the user's installed [official OrcaSlicer CLI](https://github.com/OrcaSlicer/OrcaSlicer/wiki/cli_mode). Machine/process/filament profiles are resolved from its local resources and flattened into a private job directory. The source resources are not edited. Version 2.4.2 is the initial real slicer exercised with a synthetic model. Later versions can change their profiles or flags; report failures rather than quietly substituting a generic printer.

## Moonraker and Klipper

The bridge uses the [official file upload API](https://moonraker.readthedocs.io/en/latest/external_api/file_manager/) and printer endpoints. It requires Moonraker 0.10.0+ with API major 1; the [v0.10.0 upload handler](https://github.com/Arksine/moonraker/blob/v0.10.0/moonraker/components/application.py) parses the checksum field and rejects a mismatch. Upload includes that SHA256 checksum and `print=false`. A successful upload must identify the expected file and confirm that no print was started or queued. Readiness is checked again before requesting start. Maker macro checks are basic presence/token checks, not Jinja execution verification; unmodified trusted K1 firmware/configuration remains a prerequisite. No firmware or service modification is automated.

Root and a Mainsail page alone are insufficient. Moonraker must answer correctly, and the reported identity must match the user's configured K1. A server that requires authentication needs a local API-key environment variable.

## Model sources

The CLI prepares local STL or 3MF geometry. An agent may download a source through the source's normal browser/connector workflow when the user authorizes it. Authentication, model licenses and paid access still apply. This package does not scrape credentials, bypass download restrictions or bundle a model catalogue.

## Optional Kiln

[Kiln](https://github.com/codeofaxel/Kiln) can be installed separately for additional assistant tools. The originating setup evaluated version 1.5.0. In that version, the upload scanner rejected normal named K1 macros and its homing check did not recognize the maker's homing inside START_PRINT. Specific profile limits also required a separate catalogue/account lookup.

The public skill therefore uses native Moonraker transport and independent local validation. It does not patch or disable Kiln's filters, import its source, require an account or imply compatibility with every future Kiln version.

## Agents

The skill folder follows the Agent Skills layout. [Codex local skill discovery](https://learn.chatgpt.com/docs/build-skills) supports user/repository installations. Other hosts need compatible skill loading, local file/terminal access and permission to reach the printer. Loading instructions into a remote chat alone does not establish a hardware connection.
