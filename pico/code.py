# USB-HID remote — runs on a Raspberry Pi Pico 2 W plugged into your media
# box's USB-A port. The Pico presents itself to the box as an ordinary USB
# keyboard + consumer-control device, and takes commands over Wi-Fi from the
# web page (nginx proxies /ctl/* here). Nothing is installed on the box itself.
#
#   POST/GET  /ctl/key?k=up|down|left|right|ok|back|home|menu|playpause|volup|voldn
#   POST/GET  /ctl/raw?kc=<int>    -> send a raw HID keyboard keycode  (mapping tests)
#   POST/GET  /ctl/cons?u=<hex>    -> send a raw consumer-control usage (mapping tests)
#   POST/GET  /ctl/health          -> "hid ready ip=<ip>"
#
# Requires CircuitPython + the adafruit_hid and adafruit_httpserver libraries
# in /lib (see pico/README.md). Wi-Fi credentials come from settings.toml.
import os, time
import wifi, socketpool
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_httpserver import Server, Request, Response, GET, POST

kbd = Keyboard(usb_hid.devices)
cc = ConsumerControl(usb_hid.devices)

# Named keys. Arrows drive the D-pad; ENTER is "OK/select" on most launchers.
KEY = {
    "up": Keycode.UP_ARROW, "down": Keycode.DOWN_ARROW,
    "left": Keycode.LEFT_ARROW, "right": Keycode.RIGHT_ARROW,
    "ok": Keycode.ENTER, "back": Keycode.ESCAPE,
    "menu": Keycode.APPLICATION,
}
# Consumer-control usages. Android reliably maps these to Back / Home / media
# even when a keyboard's ESC does not register as Back.
CONS = {"home": 0x223, "back": 0x224, "playpause": 0x00CD, "volup": 0x00E9, "voldn": 0x00EA}
PREFER_CONS = {"home", "playpause", "volup", "voldn"}


def press(name):
    try:
        if name in PREFER_CONS and name in CONS:
            cc.send(CONS[name]); return True
        if name in KEY:
            kbd.send(KEY[name]); return True
        if name in CONS:
            cc.send(CONS[name]); return True
    except Exception as e:
        print("press err", name, e)
    return False


ssid = os.getenv("CIRCUITPY_WIFI_SSID")
pw = os.getenv("CIRCUITPY_WIFI_PASSWORD")
while True:
    try:
        print("connecting to", ssid)
        wifi.radio.connect(ssid, pw)
        break
    except Exception as e:
        print("wifi retry:", e); time.sleep(3)
IP = str(wifi.radio.ipv4_address)
print("WIFI OK ip=", IP, "mac=", ":".join("%02x" % b for b in wifi.radio.mac_address))

pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=False)


@server.route("/ctl/key", [GET, POST])
def _key(request: Request):
    ok = press(request.query_params.get("k", ""))
    return Response(request, "ok" if ok else "unknown-key")


@server.route("/ctl/raw", [GET, POST])
def _raw(request: Request):
    try:
        kbd.send(int(request.query_params.get("kc", "0")))
        return Response(request, "ok")
    except Exception as e:
        return Response(request, "err %s" % e)


@server.route("/ctl/cons", [GET, POST])
def _cons(request: Request):
    try:
        cc.send(int(request.query_params.get("u", "0"), 16))
        return Response(request, "ok")
    except Exception as e:
        return Response(request, "err %s" % e)


@server.route("/ctl/health", [GET, POST])
def _health(request: Request):
    return Response(request, "hid ready ip=%s" % IP)


print("serving on", IP, ":5080")
server.serve_forever(IP, 5080)
