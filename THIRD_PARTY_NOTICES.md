# External tools and attribution

The original skill instructions, Python helpers, synthetic examples and project identity in this repository are MIT licensed. This project is independent of Creality, OrcaSlicer, Moonraker, Klipper and Kiln; their names identify compatibility, not endorsement.

- [OrcaSlicer](https://github.com/OrcaSlicer/OrcaSlicer) is an external slicer. Its binary and profile files are not distributed here. Install it from its official releases and retain its [license and notices](https://github.com/OrcaSlicer/OrcaSlicer/blob/main/LICENSE). The profile helper reads the user's installed resources and writes local derived profiles; those files are excluded from publication.
- [Moonraker](https://github.com/Arksine/moonraker) and [Klipper](https://github.com/Klipper3d/klipper) run on the user's printer. This package calls the Moonraker API and does not distribute or modify their firmware or server code.
- [Kiln](https://github.com/codeofaxel/Kiln) was evaluated as an optional integration. It is not installed or imported by this package, and its source code, catalogue and accounts are not bundled. Its own license and terms govern any separate installation.
- Python dependencies retain their own licenses and notices as installed by pip. See `pyproject.toml` for direct dependencies and the distribution metadata of installed packages for their licenses.

The documentation previews use an original synthetic overhang, not a downloaded third-party model. No Creality Cloud model, user account screenshot, private G-code or printer configuration is part of this distribution.
