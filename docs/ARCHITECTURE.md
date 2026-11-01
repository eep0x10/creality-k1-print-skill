# Architecture

The same runtime lives inside the skill and the Python package: `skills/creality-k1-print/scripts/k1print/`. There is no separate web service or cloud relay.

| Component | Responsibility |
| :--- | :--- |
| `config.py`, `discovery.py` | Local configuration and bounded RFC1918 discovery |
| `model.py` | Read STL/3MF geometry, preserve transforms/units and scale uniformly |
| `profiles.py` | Resolve installed official Orca K1 profile inheritance and derive job priorities |
| `slicing.py` | Invoke the configured Orca executable with an argument list, never a shell |
| `preview.py` | Read deposited paths, render a bounded real-toolpath image and retain full bounds/estimates |
| `validation.py` | Verify artifacts, supported commands, temperatures, motion and arc bounds |
| `transport.py` | Identity/readiness checks, checksum upload and a single approved start |
| `camera.py` | GET-only camera discovery, bounded JPEG/PNG capture and local output |
| `cli.py`, `scripts/k1.py` | Installed command and portable skill launcher |

## Job state

Preparation writes a new local job directory containing geometry, derived profiles, slicer logs, G-code, `preview.png`, `preview-report.json` and `job.json`. The manifest stores relative artifact paths and SHA256 hashes of the G-code, preview and report. It starts in `awaiting_preview_approval`.

The agent's conversation supplies the human approval. An approval reference records where it came from; it does not authenticate a person. All artifacts must be kept in a trusted local directory. Local validation completes before printer requests. The bridge copies the bytes it validated, uploads with automatic print disabled, rechecks identity/state and starts once. A persistent receipt prevents accidental resubmission. An uncertain response remains uncertain until status is observed; no POST is automatically repeated.

These checks reduce common mistakes; they do not simulate firmware, guarantee physical print quality or replace user supervision.

## Camera observations

Camera capture is independent of the print job/approval state. It checks the configured printer identity and reads its state, then gets one snapshot from a configured URL or Moonraker's enabled webcam list. Relative webcam paths default to the printer host at HTTP port 80, following Moonraker's documented semantics; an explicit camera base supports other proxy ports. Only the printer's configured hostname is accepted, with no redirects. The Moonraker API key is never forwarded to another origin, including a different port.

Image bytes are bounded and validated before an exclusive local write. The result includes a retrieval timestamp (`captured_at_utc`), dimensions, SHA256 and the separately read printer state, never the camera URL or response body. These observations are not simultaneous, a server may return a cached frame, and they do not establish physical success. No camera frame is a test fixture or release asset.
