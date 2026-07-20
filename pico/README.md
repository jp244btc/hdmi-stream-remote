# Pico 2 W — USB-HID remote

The Pico plugs into your media box's USB-A port and acts as a **USB keyboard**.
Your box already knows how to take input from a USB keyboard (arrows = D-pad,
Enter = select), so nothing has to be installed or enabled on the box. The Pico
also joins your Wi-Fi and runs a tiny HTTP server, so the web page can turn a
button tap into a real key press on the box.

## What you need

- A **Raspberry Pi Pico 2 W** (the RP2350 board with Wi-Fi; a Pico W / RP2040 also works).
- A **micro-USB → USB-A cable** (data, not charge-only) to connect the Pico to the box.
- A computer to flash it (any OS).

## 1. Flash CircuitPython (the `.uf2`)

1. Download the CircuitPython **UF2** for your board from
   <https://circuitpython.org/board/raspberry_pi_pico2_w/> (pick the Pico W page if
   you have the RP2040 board). This project was built on CircuitPython 10.x.
2. Hold the **BOOTSEL** button on the Pico while plugging it into your computer.
   It mounts as a USB drive named **`RPI-RP2`**.
3. Drag the `.uf2` file onto that drive. The Pico reboots and re-mounts as
   **`CIRCUITPY`**.

## 2. Add the libraries

`code.py` needs two Adafruit libraries. Download the **CircuitPython Library
Bundle** matching your CircuitPython major version from
<https://circuitpython.org/libraries>, then copy these into a `lib/` folder on
the `CIRCUITPY` drive:

```
CIRCUITPY/lib/adafruit_hid/            (whole folder)
CIRCUITPY/lib/adafruit_httpserver/     (whole folder)
```

## 3. Add the code and your Wi-Fi

Copy onto the root of the `CIRCUITPY` drive:

- **`code.py`** (from this folder) — runs automatically on boot.
- **`settings.toml`** — copy `settings.toml.example`, rename it, and fill in your
  Wi-Fi name and password. The SSID is case-sensitive.

The drive should now look like:

```
CIRCUITPY/
├── code.py
├── settings.toml
└── lib/
    ├── adafruit_hid/
    └── adafruit_httpserver/
```

## 4. Find its IP and plug it into the box

- Unplug/replug the Pico from your computer once so it runs `code.py` fresh. It
  joins Wi-Fi and starts the control server on port **5080**.
- Find its IP (check your router's DHCP leases, or open the CircuitPython serial
  console — it prints `WIFI OK ip=...`). **Reserve that IP** in your router so it
  never changes.
- Confirm it answers: `curl http://<PICO_IP>:5080/ctl/health` → `hid ready ip=...`
- Now move the **same cable** to a **USB-A port on your media box**. The box powers
  the Pico, the Pico rejoins Wi-Fi on its own, and the box sees a USB keyboard.

That's it — the Pico needs no further attention. It has no screen and nothing to
babysit; it just answers control requests forever.

## Notes

- **Powered by the box.** No separate power supply — it draws from the box's USB port.
- **Discovering key codes for your box:** if a button does the wrong thing, use the
  `/ctl/raw?kc=<int>` (keyboard) and `/ctl/cons?u=<hex>` (consumer-control) endpoints
  to probe which code your box responds to, then adjust the mapping in
  [`../web/tv.html`](../web/tv.html). See the main README's "Tuning the buttons".
