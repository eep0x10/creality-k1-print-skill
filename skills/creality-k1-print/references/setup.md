# Local setup

## Prerequisites

- Original Creality K1, PLA and a 0.4 mm nozzle.
- Moonraker 0.10.0 or later with API major 1, reachable from this computer. Confirm `/server/info` and `/printer/info`; root access and a visible Mainsail page alone do not prove connectivity. The bridge rejects older, unknown and prerelease versions rather than assuming server-side checksum support.
- [OrcaSlicer from its official releases](https://github.com/OrcaSlicer/OrcaSlicer/releases). Version 2.4.2 is the initial locally exercised CLI. The helper reads official installed profile resources; no binary or profile catalogue is bundled here.
- Python 3.11+ and an agent capable of local terminal/file operations.

For printer-side installation, use the [Creality Helper Script documentation](https://guilouz.github.io/Creality-Helper-Script-Wiki/) and confirm compatibility with the exact firmware. This skill does not root, upgrade, reboot or automatically repair printers. Never change firmware/services during a print.

## Install the skill

From a cloned or extracted repository:

```sh
python scripts/install_skill.py --with-runtime
```

Default destination: `~/.agents/skills/creality-k1-print`. `--target PATH` selects another directory; existing targets are preserved and cause an error. `--with-runtime` creates `<skill>/.venv` and installs the declared Python dependencies from the normal package registry. It does not download OrcaSlicer or contact a printer.

If copying succeeded but dependency installation failed, rerun the installer from the source repository with `--repair-runtime --target <skill-folder>`. This repairs only the recognized skill's Python runtime and preserves its instructions/scripts. It is not an upgrade command. For a version update, first back up the existing installation privately and install into a new/empty destination, reviewing any local customization before selecting the new skill.

Use that environment's interpreter with `<skill>/scripts/k1.py`. On Windows it is `<skill>/.venv/Scripts/python.exe`; on Linux/macOS it is `<skill>/.venv/bin/python`. This avoids depending on whichever global Python the agent happens to use.

Codex local discovery and other agent locations depend on the host. The current [official Codex skill documentation](https://learn.chatgpt.com/docs/build-skills) describes user and repository skill directories. The folder is an Agent Skills resource; a host without local execution still needs an actual printer bridge.

## Direct CLI for development or manual use

Windows:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e .
.venv/Scripts/k1print.exe --help
```

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/k1print --help
```

The shorter `k1print` commands below assume that environment is activated or on PATH. Otherwise use its executable directly. No execution-policy change is required.

## Configure your own connection

Use the real hostname returned by your printer, not a hostname from someone else's example:

```sh
k1print init --printer-url http://k1.local:7125 --expected-hostname YOUR_K1_HOSTNAME --orca-path /path/to/orca-slicer
k1print status
```

Supply `--orca-resources /path/to/resources` if resource discovery cannot find the official profile directory. Windows paths containing spaces must be quoted. The default local config is `~/.config/k1-print/config.json`; choose another with global `--config PATH`.

If Moonraker requires an API key, configure `--api-key-env MOONRAKER_API_KEY` and set that environment variable through your local secret mechanism. The JSON stores only the variable's name. Never paste credentials into a repository or put them in a printer URL.

If you do not know the address, use `k1print discover --subnet YOUR_PRIVATE_SUBNET/24`. Only scan a network you own or are authorized to inspect. The helper limits scanning to a small RFC1918 IPv4 subnet; it does not traverse VPNs, routers or public addresses automatically. With multiple candidate printers, select the intended identity explicitly.

Next: [workflow](workflow.md). If setup fails, report the actual limitation; do not claim a configured skill creates callable tools in an already running client.

For an existing camera/snapshot service, see [camera setup and capture](camera.md). Camera support is optional and does not change print approval. Use Moonraker webcam discovery or local `camera_url`; `camera_base_url` handles relative URLs behind a proxy. Do not expose a camera publicly or modify printer services during a print.
