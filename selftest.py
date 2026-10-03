"""
SleekKeys self-test. Start `python sleekkeys.py` first, then run `python selftest.py`.

It injects HARMLESS input (Shift, F24, a one-notch scroll, a 4px mouse nudge that is undone) and checks
that the events arrive on the live stream. It never clicks anything.
"""
import ctypes
import http.client
import json
import sys
import threading
import time

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 7878
user32 = ctypes.WinDLL("user32")

KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x2, 0x8
MOUSEEVENTF_MOVE, MOUSEEVENTF_WHEEL = 0x1, 0x800

events: list[dict] = []
ready = threading.Event()


def listen():
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=30)
    conn.request("GET", "/events")
    resp = conn.getresponse()
    ready.set()
    buf = b""
    while True:
        chunk = resp.read1(4096)
        if not chunk:
            break
        buf += chunk
        while b"\n\n" in buf:
            block, buf = buf.split(b"\n\n", 1)
            if block.startswith(b"data: "):
                events.append(json.loads(block[6:]))


threading.Thread(target=listen, daemon=True).start()
ready.wait(5)
time.sleep(0.3)

results = []


def check(name, ok):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)


# 1) host-header protection
c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=5)
c.request("GET", "/api/info", headers={"Host": "evil.example.com"})
check("rejects non-localhost Host header (DNS rebinding)", c.getresponse().status == 403)
c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=5)
c.request("POST", "/api/pause")
check("rejects POST without the X-SleekKeys header (CSRF)", c.getresponse().status == 403)
c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=5)
c.request("GET", "/api/info")
r = c.getresponse()
check("/api/info works for localhost", r.status == 200 and b"SleekKeys" in r.read())
c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=5)
c.request("GET", "/..%5csleekkeys.py")
check("path traversal blocked", c.getresponse().status == 404)

# 2) real keyboard hook: left shift by scancode, then F24 by virtual key
user32.keybd_event(0, 0x2A, KEYEVENTF_SCANCODE, 0)
time.sleep(0.05)
user32.keybd_event(0, 0x2A, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
user32.keybd_event(0x87, 0, 0, 0)
time.sleep(0.05)
user32.keybd_event(0x87, 0, KEYEVENTF_KEYUP, 0)
time.sleep(0.4)
keys = [(e["c"], e["d"]) for e in events if e.get("t") == "k"]
check("LShift down/up seen as ShiftLeft  %s" % [k for k in keys if k[0] == "ShiftLeft"],
      ("ShiftLeft", 1) in keys and ("ShiftLeft", 0) in keys)
check("unknown key falls back to VK_87 (F24)", ("VK_87", 1) in keys and ("VK_87", 0) in keys)

# 3) real mouse hook: wheel + movement
user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, 120, 0)
user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, ctypes.c_ulong(-120 & 0xFFFFFFFF).value, 0)
user32.mouse_event(MOUSEEVENTF_MOVE, 4, 0, 0, 0)
time.sleep(0.05)
user32.mouse_event(MOUSEEVENTF_MOVE, ctypes.c_ulong(-4 & 0xFFFFFFFF).value, 0, 0, 0)
time.sleep(0.4)
wheel = [e["v"] for e in events if e.get("t") == "w"]
check("wheel up/down seen %s" % wheel, 1 in wheel and -1 in wheel)
mv = [e for e in events if e.get("t") == "mv"]
check("mouse movement seen (%d msgs)" % len(mv), len(mv) > 0)

# 4) mouse buttons: drive the hook procedure directly (no real clicks!)
sys.path.insert(0, ".")
import importlib.util
spec = importlib.util.spec_from_file_location("sk", "sleekkeys.py")
sk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sk)
cl = sk.Client(None)
sk.hub.add(cl)
info = sk.MSLLHOOKSTRUCT()
for wp, mouse_data in ((sk.WM_LBUTTONDOWN, 0), (sk.WM_LBUTTONUP, 0), (sk.WM_RBUTTONDOWN, 0),
                       (sk.WM_MBUTTONDOWN, 0), (sk.WM_XBUTTONDOWN, 1 << 16), (sk.WM_XBUTTONUP, 2 << 16)):
    info.mouseData = mouse_data
    sk._mouse_proc(0, wp, ctypes.addressof(info))
got = []
while not cl.q.empty():
    got.append(json.loads(cl.q.get()))
buttons = [(e["b"], e["d"]) for e in got]
check("mouse buttons mapped %s" % buttons,
      buttons == [("l", 1), ("l", 0), ("r", 1), ("m", 1), ("x1", 1), ("x2", 0)])

# 5) privacy filter: a client that only asked for KeyQ must not receive ShiftLeft
f = sk.Client({"KeyQ"})
check("code filter drops unrequested keys", not f.wants({"t": "k", "c": "ShiftLeft", "d": 1})
      and f.wants({"t": "k", "c": "KeyQ", "d": 1}) and f.wants({"t": "m", "b": "l", "d": 1}))

print("\n%d/%d passed" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
