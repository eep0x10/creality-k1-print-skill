# Camera photo and printer state

Use this path for an existing print: no new-project preference questions. A camera/snapshot service must already work; the CLI does not install or restart it. Availability depends on hardware, firmware and local configuration.

## Capture one photo

```sh
k1print snapshot --output snapshots/status.jpg
k1print snapshot --output snapshots/status-next.jpg --camera-name chamber
```

Select a name when Moonraker lists multiple enabled cameras with nonempty snapshot URLs. The output contains an absolute local image path, retrieval time in UTC, format, dimensions, SHA256 and separately observed printer state. Show the real local image inline. Existing destinations are refused; choose a new filename each time. Use `.jpg`/`.jpeg` for JPEG and `.png` for PNG, matching the received format.

An unavailable camera does not prove the printer stopped. Use `k1print status` independently. HTML/JSON, continuous MJPEG streams, corrupt images and oversized responses are rejected. This command does not retry, heat, move, start, pause, resume or cancel anything.

The destination folder is created after image validation. Atomic non-overwriting output requires a filesystem supporting hardlinks, such as NTFS or a typical Linux local filesystem; unsupported destinations fail without a partial image. Use a local directory if a removable drive or network share rejects that operation.

## Choose the connection

By default, read `GET /server/webcams/list` and select an enabled camera with `snapshot_url`. A `stream_url` is not a finite photo. No universal snapshot endpoint is guaranteed for every K1 firmware.

An explicit local `camera_url` overrides discovery. When creating a fresh config:

```sh
k1print init --printer-url http://k1.local:7125 --expected-hostname YOUR_K1_HOSTNAME --orca-path /path/to/orca-slicer --camera-url 'http://k1.local:8080/?action=snapshot'
```

That URL illustrates **mjpg-streamer**, not a verified address for your printer. Confirm your existing camera configuration. For an existing local config, add the optional `camera_url` field without replacing printer/Orca settings. Keep personal settings outside the repository.

Moonraker defines relative snapshot URLs on the same host at **HTTP port 80**, not API port `7125`. If a proxy uses another port, set local `camera_base_url`, for example `http://k1.local:4408`, or use `--camera-base-url` when creating a fresh config. No alternative ports are probed. Absolute discovered URLs retain their origin, subject to the hostname restriction.

Only HTTP(S) URLs on the printer's exact configured hostname are accepted; ports may differ. User/password URLs, fragments, secret-bearing query parameters and redirects are unsupported. The Moonraker API key is never forwarded to a different origin, including another port. Cameras needing separate authentication require an independently configured local proxy and are outside direct support. TLS verification stays enabled.

## Privacy and interpretation

Keep images in an ignored local `snapshots/` directory. Never publish photos, camera URLs or local metadata as demos/tests. The CLI keeps the frame local; showing it in chat makes it available to that host under its own data policy.

Label the retrieval time and separately read printer state: they are not an atomic observation. A server may supply a cached image; the timestamp does not prove sensor exposure time. Do not infer completion, adhesion or defect-free printing from one frame. The original frame is shown; Moonraker rotation/flip metadata is not applied in this version.

This is on-demand capture. Periodic monitoring needs a separate explicit request and a real active monitoring mechanism.

## Primary references

- [Moonraker webcam API](https://moonraker.readthedocs.io/en/latest/external_api/webcams/): list and snapshot/stream fields.
- [Moonraker webcam configuration](https://github.com/Arksine/moonraker/blob/master/docs/configuration.md#webcam): relative URLs and camera services.
- [Moonraker webcam implementation](https://github.com/Arksine/moonraker/blob/master/moonraker/components/webcam.py): URL resolution.
- [mjpg-streamer HTTP plugin](https://github.com/jacksonliam/mjpg-streamer/blob/master/mjpg-streamer-experimental/plugins/output_http/README.md): finite snapshot versus continuous stream.
