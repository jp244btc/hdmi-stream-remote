# hdmi-stream-remote

Watch **and control** any HDMI device — an Android TV / IPTV box, a game console,
a camera feed — from your phone or tablet, at home or over the internet. It's a
self-hosted, DIY placeshifter with a built-in on-screen remote.

The picture comes from an HDMI capture encoder (so it works with *any* source and
needs nothing installed on the device). The remote control comes from a Raspberry
Pi Pico 2 W that plugs into the box's USB port and pretends to be a keyboard — so
the on-screen D-pad drives the box for real, with nothing to install on it either.

Everything runs on your own network. Add the page to your home screen and it
behaves like a native app: live video with sound, a D-pad, OK/Back/Home, a
single-press Pause, and a **Home / Cellular** switch that keeps video smooth on
mobile data.

```
   ┌───────────────┐   HDMI    ┌──────────────────┐   RTSP    ┌────────────────────┐
   │  Your box     │──────────▶│  HDMI encoder    │──────────▶│  Small Linux host  │
   │ (Android TV / │           │ (HDMI → RTSP)    │           │  go2rtc + nginx    │
   │  IPTV / etc.) │           └──────────────────┘           └─────────┬──────────┘
   │               │                                            WebRTC / │ MSE (+ audio)
   │   USB-A  ◀────┼── USB keyboard ── ┌───────────────┐                 ▼
   └───────────────┘   (HID)          │  Pico 2 W     │◀── /ctl/ ── ┌─────────────────┐
                                      │ Wi-Fi ⇄ HTTP  │             │  Phone / tablet │
                                      └───────────────┘   HTTP      │  browser (/tv)  │
                                                                    └─────────────────┘
                                          (remote access: your own VPN, e.g. WireGuard)
```

## Why this design

- **Nothing runs on the box.** No sideloaded app, no root, no ADB, no screen-record
  permission. The encoder sees only HDMI; the Pico is just a USB keyboard. The box
  is untouched and survives its own reboots.
- **Content-agnostic.** Because it captures HDMI, it works with any source. (Note:
  HDCP-protected apps like Netflix/Disney+ encrypt their HDMI output and will show
  a black frame — this captures unprotected output only.)
- **Real key events.** A USB keyboard's arrows/Enter map to the box's D-pad/select,
  so navigation works in every app — not just wherever an accessibility hack reaches.

## Hardware

| Part | What it does | Notes |
|------|--------------|-------|
| **HDMI-to-IP encoder** | HDMI in → H.264 RTSP out | Built with a **LinkPi ENC1-V3** (~$130–150). Any encoder that outputs RTSP with a low-latency 1080p main stream + a lower-res substream works. |
| **A small always-on Linux host** | Runs go2rtc + nginx | A mini-PC, a Raspberry Pi, or an LXC container / VM. ~1 core, 512 MB is plenty. |
| **Raspberry Pi Pico 2 W** | USB keyboard into the box + Wi-Fi control server | ~$7. A Pico W (RP2040) also works. Plus a micro-USB→USB-A **data** cable. |
| **Your box** | The thing you want to watch/control | Any HDMI source. If you want the remote, it must accept a USB keyboard (nearly all Android boxes do). |

Remote (away-from-home) access uses **your own VPN back home** (e.g. WireGuard on
your router). This project doesn't run any cloud service — your video never leaves
your network.

## How it works

1. The **encoder** turns the box's HDMI into two RTSP streams: a sharp main stream
   (e.g. 1080p) and a lighter substream (e.g. 720p).
2. **go2rtc** pulls those and republishes them to browsers as WebRTC (low latency)
   or MSE (buffered), adding an Opus audio track so mobile Safari has sound.
3. **nginx** serves the [`/tv`](web/tv.html) page, proxies control requests to the
   Pico, and gates everything behind a LAN allowlist.
4. The **Pico** plugs into the box as a USB keyboard and runs a tiny HTTP server;
   the page's buttons become real key presses.

---

## Setup

### 1. Encoder

Point the encoder at the box's HDMI and enable **RTSP**. Note its two stream URLs —
typically something like:

- main: `rtsp://<ENCODER_IP>:554/stream0`  (1080p30, ~8 Mbps, CBR)
- sub:  `rtsp://<ENCODER_IP>:554/sub0`     (720p30,  ~3 Mbps, CBR)

Give the encoder a **static/reserved IP**. A GOP (keyframe interval) of ~2× the frame
rate is a good default. Keep the source box output at a plain resolution (1080p) with
PCM/stereo audio for the cleanest capture.

**For weak cellular**, the biggest single win is a lighter stream than 720p/3 Mbps —
congested, indoor, or moving cells often sit at 0.5–1.5 Mbps, where 3 Mbps stalls. This
repo ships a **Saver 480p** tier for exactly that: the `tv_mobile` stream in
[`server/go2rtc.yaml`](server/go2rtc.yaml) is a software **transcode** of the warm `tv`
stream down to 854×480 ~1.2 Mbps. It needs `ffmpeg` built with **libx264**, runs only
on demand (go2rtc spins it up when someone selects Saver and stops it when they leave),
adds no load to the encoder, and works regardless of what your encoder can produce.
A CPU-only host handles one 480p transcode easily (~0.2 of a core here).

If you'd rather offload it, and your encoder supports a *third* concurrent hardware
encode, you can instead point `tv_mobile` at a real 480p encoder substream — but that
means a native encoder feed (and changing encoder profiles briefly restarts capture,
interrupting anyone watching, so do it when nobody's mid-show).

### 2. Linux host — go2rtc + nginx

Install [go2rtc](https://github.com/AlexxIT/go2rtc) and **ffmpeg** (go2rtc uses it
for the Opus audio track), plus **nginx**.

```bash
# go2rtc binary
sudo curl -L -o /usr/local/bin/go2rtc \
  https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_amd64
sudo chmod +x /usr/local/bin/go2rtc
sudo apt install -y ffmpeg nginx
```

Copy the configs from [`server/`](server/) and edit the placeholder IPs
(`SERVER_IP`, `ENCODER_IP`, `PICO_IP`) and the nginx allowlist:

```bash
sudo mkdir -p /etc/go2rtc
sudo cp server/go2rtc.yaml           /etc/go2rtc/go2rtc.yaml
sudo cp server/go2rtc.service        /etc/systemd/system/go2rtc.service
sudo cp server/keepwarm.service      /etc/systemd/system/keepwarm.service
sudo cp server/nginx.conf            /etc/nginx/sites-available/tv
sudo cp web/tv.html                  /var/www/tv.html
sudo ln -sf /etc/nginx/sites-available/tv /etc/nginx/sites-enabled/tv
sudo rm -f /etc/nginx/sites-enabled/default

sudo systemctl daemon-reload
sudo systemctl enable --now go2rtc keepwarm
sudo nginx -t && sudo systemctl reload nginx
```

- **`keepwarm.service`** holds one connection to the encoder open at all times. Cheap
  encoders are flaky to (re)connect but rock-solid once flowing, so this makes the
  browser always join an already-live stream instantly.
- The page and stream name (`tv` / `tv_low`) must match across `go2rtc.yaml`,
  `keepwarm.service`, and the `PROFILES` in `tv.html`.

Open `http://<SERVER_IP>:1984/tv` from an allowlisted device — you should see video.

### 3. Pico 2 W — the remote

Full steps in [`pico/README.md`](pico/README.md). In short:

1. Flash the **CircuitPython `.uf2`** (hold BOOTSEL, drag the file onto the `RPI-RP2`
   drive).
2. Copy the **`adafruit_hid`** and **`adafruit_httpserver`** libraries into `lib/`.
3. Copy [`pico/code.py`](pico/code.py) and a filled-in `settings.toml` (from
   [`settings.toml.example`](pico/settings.toml.example)) onto the drive.
4. Confirm it's up: `curl http://<PICO_IP>:5080/ctl/health` → `hid ready ip=...`,
   reserve its IP, then plug the **same cable into a USB-A port on your box**.

### 4. Remote access (optional)

To use it away from home, put a VPN on your home network (WireGuard is ideal) and
add your VPN's subnet to the nginx `allow` list. Then the same `/tv` page works from
anywhere. No config in this project changes — you're just on the LAN over the tunnel.

---

## Using it

Open `http://<SERVER_IP>:1984/tv` and **Add to Home Screen** — it launches
full-screen like an app.

- **Watch:** tap the video once to enable sound (mobile browsers start muted).
- **D-pad / OK / Back / Home:** the on-screen buttons; `✛` collapses the D-pad.
- **⏯ Pause:** a single-press play/pause for video players (the OK button sends a
  double-select which some players read as pause-then-play).
- **Stream settings** (bottom-left, two independent toggles, both remembered):
  - **🖥 HD 1080p / 📱 Lite 720p / 🐢 Saver 480p** — resolution/bitrate (which stream).
    Saver is an on-demand ~1.2 Mbps transcode for weak cellular; expect a few seconds
    of cold-start when you switch to it (see the encoder note below).
  - **⚡ Live / 🌊 Buffered** — transport:
    - **Live** = WebRTC. Real-time (~0.5 s), adapts bitrate on the fly, degrades by
      dropping frames rather than stalling. Your daily driver.
    - **Buffered** = **native HLS** (the browser's own `.m3u8` player). Hardware-
      decoded and deeply buffered — rock-solid on a genuinely bad link — but runs
      **~6–10 s behind live**. Use it only as a worst-case escape hatch.
  - Note: go2rtc's MSE mode is deliberately *not* used here. On iOS Safari its
    Managed Media Source fights go2rtc's low-latency push feed and stutters even on a
    clean LAN, so Buffered uses native HLS instead — the format iOS plays flawlessly.
  - **Live usually wins** on both Wi-Fi and cellular; reach for Buffered only when a
    weak link makes Live unwatchable, and drop to **Lite/Saver** quality first.
- **Hardware keyboard** (e.g. iPad Magic Keyboard): arrows navigate, **Return** = OK,
  **Delete/Backspace/Esc** = Back, **Space** = Pause.

## Tuning the buttons for your box

Different boxes map keys differently. The Pico exposes raw test endpoints so you can
discover what yours wants, then set them in [`web/tv.html`](web/tv.html)'s `EP` map:

```bash
curl "http://<PICO_IP>:5080/ctl/raw?kc=88"     # send raw HID keycode 88 (keypad Enter)
curl "http://<PICO_IP>:5080/ctl/cons?u=224"    # send consumer-control usage 0x224 (AC Back)
```

Watch the box while sending codes (the live stream is a handy feedback loop) to find
which select/back/home code it honors, then edit the mapping. Common gotchas: some
launchers want plain Enter (`kc=40`) while player apps want keypad Enter (`kc=88`);
many Android boxes ignore keyboard Esc as Back and need the consumer AC-Back
(`cons?u=224`).

## Security

The whole thing is gated by the nginx **LAN allowlist** — only listed device IPs and
your VPN subnet can reach the page or the control endpoint. This matters because
same-subnet traffic bypasses your router's firewall, and an open control endpoint
means anyone on your network could drive your TV. There's no password (mobile Safari
drops HTTP Basic auth on WebSocket upgrades, which the video needs); the allowlist is
the access control. Keep it tight, and only reach it remotely through your VPN.

## Credits

Built on [go2rtc](https://github.com/AlexxIT/go2rtc),
[CircuitPython](https://circuitpython.org/) + Adafruit's HID / HTTP-server libraries,
ffmpeg, and nginx. MIT licensed — see [LICENSE](LICENSE).
