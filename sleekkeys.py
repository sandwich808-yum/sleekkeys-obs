#!/usr/bin/env python3
"""
SleekKeys - a clean keyboard + mouse input overlay for OBS (a NohBoard alternative).

How it works
  * Low-level Windows hooks watch the keyboard and mouse.
  * A tiny local web server (127.0.0.1 only) streams those events to the overlay page.
  * In OBS you add the overlay as a Browser Source - it is natively transparent, no green screen.

Standard library only. Windows only.

Run:  python sleekkeys.py [--port 7878] [--open]
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import http.server
import json
import mimetypes
import os
import queue
import socketserver
import sys
import threading
import time
import urllib.parse
import webbrowser

VERSION = "1.0.0"
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def log(*args) -> None:
    """print() that never crashes when there is no console (pythonw)."""
    try:
        print(*args, flush=True)
    except Exception:
        pass


# --------------------------------------------------------------------------------------
# Scan code -> KeyboardEvent.code names. Scan codes are layout independent, so the overlay
# works the same on QWERTY, AZERTY, etc.
# --------------------------------------------------------------------------------------
SC = {
    0x01: "Escape", 0x02: "Digit1", 0x03: "Digit2", 0x04: "Digit3", 0x05: "Digit4",
    0x06: "Digit5", 0x07: "Digit6", 0x08: "Digit7", 0x09: "Digit8", 0x0A: "Digit9",
    0x0B: "Digit0", 0x0C: "Minus", 0x0D: "Equal", 0x0E: "Backspace", 0x0F: "Tab",
    0x10: "KeyQ", 0x11: "KeyW", 0x12: "KeyE", 0x13: "KeyR", 0x14: "KeyT", 0x15: "KeyY",
    0x16: "KeyU", 0x17: "KeyI", 0x18: "KeyO", 0x19: "KeyP", 0x1A: "BracketLeft",
    0x1B: "BracketRight", 0x1C: "Enter", 0x1D: "ControlLeft", 0x1E: "KeyA", 0x1F: "KeyS",
    0x20: "KeyD", 0x21: "KeyF", 0x22: "KeyG", 0x23: "KeyH", 0x24: "KeyJ", 0x25: "KeyK",
    0x26: "KeyL", 0x27: "Semicolon", 0x28: "Quote", 0x29: "Backquote", 0x2A: "ShiftLeft",
    0x2B: "Backslash", 0x2C: "KeyZ", 0x2D: "KeyX", 0x2E: "KeyC", 0x2F: "KeyV",
    0x30: "KeyB", 0x31: "KeyN", 0x32: "KeyM", 0x33: "Comma", 0x34: "Period",
    0x35: "Slash", 0x36: "ShiftRight", 0x37: "NumpadMultiply", 0x38: "AltLeft",
    0x39: "Space", 0x3A: "CapsLock", 0x3B: "F1", 0x3C: "F2", 0x3D: "F3", 0x3E: "F4",
    0x3F: "F5", 0x40: "F6", 0x41: "F7", 0x42: "F8", 0x43: "F9", 0x44: "F10",
    0x45: "NumLock", 0x46: "ScrollLock", 0x47: "Numpad7", 0x48: "Numpad8",
    0x49: "Numpad9", 0x4A: "NumpadSubtract", 0x4B: "Numpad4", 0x4C: "Numpad5",
    0x4D: "Numpad6", 0x4E: "NumpadAdd", 0x4F: "Numpad1", 0x50: "Numpad2",
    0x51: "Numpad3", 0x52: "Numpad0", 0x53: "NumpadDecimal", 0x56: "IntlBackslash",
    0x57: "F11", 0x58: "F12",
}
SC_EXT = {  # extended (E0-prefixed) keys
    0x1C: "NumpadEnter", 0x1D: "ControlRight", 0x35: "NumpadDivide", 0x38: "AltRight",
    0x47: "Home", 0x48: "ArrowUp", 0x49: "PageUp", 0x4B: "ArrowLeft", 0x4D: "ArrowRight",
    0x4F: "End", 0x50: "ArrowDown", 0x51: "PageDown", 0x52: "Insert", 0x53: "Delete",
    0x5B: "MetaLeft", 0x5C: "MetaRight", 0x5D: "ContextMenu", 0x37: "PrintScreen",
}


# --------------------------------------------------------------------------------------
# Event hub: fans events out to every connected overlay (Server-Sent Events).
# --------------------------------------------------------------------------------------
class Client:
    def __init__(self, codes: set[str] | None):
        self.q: queue.Queue[str] = queue.Queue(maxsize=512)
        self.codes = codes  # None = send every key; otherwise only these key codes (privacy)

    def wants(self, ev: dict) -> bool:
        if ev.get("t") == "k" and self.codes is not None:
            return ev["c"] in self.codes
        return True


class Hub:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.clients: list[Client] = []
        self.held_keys: set[str] = set()
        self.held_buttons: set[str] = set()
        self.paused = False

    def add(self, c: Client) -> None:
        with self.lock:
            self.clients.append(c)

    def remove(self, c: Client) -> None:
        with self.lock:
            if c in self.clients:
                self.clients.remove(c)

    def snapshot_for(self, c: Client) -> dict:
        with self.lock:
            keys = [k for k in self.held_keys if c.codes is None or k in c.codes]
            return {"t": "s", "k": keys, "m": sorted(self.held_buttons)}

    def publish(self, ev: dict) -> None:
        if self.paused:
            return
        payload = json.dumps(ev, separators=(",", ":"))
        with self.lock:
            if ev["t"] == "k":
                (self.held_keys.add if ev["d"] else self.held_keys.discard)(ev["c"])
            elif ev["t"] == "m":
                (self.held_buttons.add if ev["d"] else self.held_buttons.discard)(ev["b"])
            targets = [c for c in self.clients if c.wants(ev)]
        for c in targets:
            try:
                c.q.put_nowait(payload)
            except queue.Full:
                pass  # slow client; drop rather than block the input hook


hub = Hub()


# --------------------------------------------------------------------------------------
# Windows low-level hooks
# --------------------------------------------------------------------------------------
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL, WH_MOUSE_LL = 13, 14
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x200, 0x201, 0x202
WM_RBUTTONDOWN, WM_RBUTTONUP, WM_MBUTTONDOWN, WM_MBUTTONUP = 0x204, 0x205, 0x207, 0x208
WM_MOUSEWHEEL, WM_XBUTTONDOWN, WM_XBUTTONUP, WM_MOUSEHWHEEL = 0x20A, 0x20B, 0x20C, 0x20E
LLKHF_EXTENDED = 0x01

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD)
user32.SetWindowsHookExW.restype = wt.HHOOK
user32.CallNextHookEx.argtypes = (wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM)
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = (wt.HHOOK,)
user32.GetMessageW.argtypes = (ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT)
user32.PostThreadMessageW.argtypes = (wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM)
kernel32.GetModuleHandleW.argtypes = (wt.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wt.HMODULE

_held: set[str] = set()
_move = {"dx": 0, "dy": 0, "last": None}
_move_lock = threading.Lock()
_hook_thread_id = 0
_stop = threading.Event()


def _keyboard_proc(n_code, w_param, l_param):
    try:
        if n_code == 0:
            info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            ext = bool(info.flags & LLKHF_EXTENDED)
            code = (SC_EXT if ext else SC).get(info.scanCode) or SC.get(info.scanCode)
            if code is None:
                code = f"VK_{info.vkCode:02X}"
            if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                if code not in _held:  # ignore auto-repeat
                    _held.add(code)
                    hub.publish({"t": "k", "c": code, "d": 1})
            elif w_param in (WM_KEYUP, WM_SYSKEYUP):
                _held.discard(code)
                hub.publish({"t": "k", "c": code, "d": 0})
    except Exception:
        pass
    return user32.CallNextHookEx(None, n_code, w_param, l_param)


_MOUSE_BTN = {
    WM_LBUTTONDOWN: ("l", 1), WM_LBUTTONUP: ("l", 0),
    WM_RBUTTONDOWN: ("r", 1), WM_RBUTTONUP: ("r", 0),
    WM_MBUTTONDOWN: ("m", 1), WM_MBUTTONUP: ("m", 0),
}


def _mouse_proc(n_code, w_param, l_param):
    try:
        if n_code == 0:
            info = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            if w_param == WM_MOUSEMOVE:
                with _move_lock:
                    last = _move["last"]
                    if last is not None:
                        _move["dx"] += info.pt.x - last[0]
                        _move["dy"] += info.pt.y - last[1]
                    _move["last"] = (info.pt.x, info.pt.y)
            elif w_param in _MOUSE_BTN:
                b, d = _MOUSE_BTN[w_param]
                hub.publish({"t": "m", "b": b, "d": d})
            elif w_param in (WM_XBUTTONDOWN, WM_XBUTTONUP):
                which = "x1" if (info.mouseData >> 16) & 0xFFFF == 1 else "x2"
                hub.publish({"t": "m", "b": which, "d": 1 if w_param == WM_XBUTTONDOWN else 0})
            elif w_param in (WM_MOUSEWHEEL, WM_MOUSEHWHEEL):
                delta = ctypes.c_short((info.mouseData >> 16) & 0xFFFF).value
                if delta:
                    hub.publish({"t": "w", "v": 1 if delta > 0 else -1,
                                 "h": 1 if w_param == WM_MOUSEHWHEEL else 0})
    except Exception:
        pass
    return user32.CallNextHookEx(None, n_code, w_param, l_param)


# Keep references so the callbacks are never garbage collected.
_kb_cb = HOOKPROC(_keyboard_proc)
_ms_cb = HOOKPROC(_mouse_proc)


def hook_thread() -> None:
    """Installs both hooks and pumps messages (required for low-level hooks to fire)."""
    global _hook_thread_id
    _hook_thread_id = kernel32.GetCurrentThreadId()
    module = kernel32.GetModuleHandleW(None)
    kb = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _kb_cb, module, 0)
    ms = user32.SetWindowsHookExW(WH_MOUSE_LL, _ms_cb, module, 0)
    if not kb or not ms:
        log("ERROR: could not install input hooks (error %d)." % ctypes.get_last_error())
        _stop.set()
        return
    msg = wt.MSG()
    while not _stop.is_set():
        r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if r in (0, -1):
            break
    user32.UnhookWindowsHookEx(kb)
    user32.UnhookWindowsHookEx(ms)


def motion_thread() -> None:
    """Sends accumulated mouse movement ~60 times a second (the hook itself must stay fast)."""
    while not _stop.is_set():
        time.sleep(1 / 60)
        with _move_lock:
            dx, dy = _move["dx"], _move["dy"]
            _move["dx"] = _move["dy"] = 0
        if dx or dy:
            hub.publish({"t": "mv", "x": dx, "y": dy})


# --------------------------------------------------------------------------------------
# HTTP server
# --------------------------------------------------------------------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "SleekKeys/" + VERSION
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quiet
        pass

    # Only answer requests addressed to localhost: blocks DNS-rebinding attacks. We never send
    # CORS headers either, so other websites cannot read the key stream.
    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        return host in ("localhost", "127.0.0.1", "[::1]", "::1")

    def _send(self, code: int, body: bytes, ctype: str = "text/plain; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, b"forbidden")
        url = urllib.parse.urlparse(self.path)
        path = url.path
        if path == "/events":
            return self._events(urllib.parse.parse_qs(url.query))
        if path == "/api/info":
            body = json.dumps({"name": "SleekKeys", "version": VERSION, "paused": hub.paused})
            return self._send(200, body.encode(), "application/json")
        if path in ("/", "/settings"):
            path = "/settings.html"
        elif path == "/overlay":
            path = "/overlay.html"
        full = os.path.normpath(os.path.join(WEB_DIR, path.lstrip("/")))
        if not full.startswith(WEB_DIR) or not os.path.isfile(full):
            return self._send(404, b"not found")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)

    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-SleekKeys") != "1":
            return self._send(403, b"forbidden")
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/quit":
            self._send(200, b"bye")
            threading.Thread(target=shutdown, daemon=True).start()
        elif path == "/api/pause":
            hub.paused = not hub.paused
            self._send(200, json.dumps({"paused": hub.paused}).encode(), "application/json")
        else:
            self._send(404, b"not found")

    def _events(self, query):
        codes = None
        if "codes" in query and query["codes"][0]:
            codes = set(query["codes"][0].split(","))
        client = Client(codes)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        hub.add(client)
        try:
            self.wfile.write(f"data: {json.dumps(hub.snapshot_for(client))}\n\n".encode())
            self.wfile.flush()
            while not _stop.is_set():
                try:
                    payload = client.q.get(timeout=10)
                    self.wfile.write(f"data: {payload}\n\n".encode())
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            hub.remove(client)
            self.close_connection = True


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # so a second copy fails loudly instead of sharing the port


_httpd: Server | None = None


def shutdown() -> None:
    _stop.set()
    if _hook_thread_id:
        user32.PostThreadMessageW(_hook_thread_id, 0x0012, 0, 0)  # WM_QUIT
    if _httpd:
        _httpd.shutdown()


def main() -> int:
    global _httpd
    ap = argparse.ArgumentParser(description="SleekKeys - keyboard + mouse overlay for OBS")
    ap.add_argument("--port", type=int, default=7878)
    ap.add_argument("--open", action="store_true", help="open the settings page in your browser")
    args = ap.parse_args()

    if os.name != "nt":
        log("SleekKeys only runs on Windows.")
        return 1
    if not os.path.isdir(WEB_DIR):
        log("Missing 'web' folder next to sleekkeys.py")
        return 1

    try:
        _httpd = Server(("127.0.0.1", args.port), Handler)
    except OSError as e:
        log(f"Could not start on port {args.port}: {e}")
        log("Is SleekKeys already running? Try --port 7879.")
        return 1

    threading.Thread(target=hook_thread, daemon=True).start()
    threading.Thread(target=motion_thread, daemon=True).start()

    url = f"http://127.0.0.1:{args.port}"
    log(f"SleekKeys {VERSION} is running.")
    log(f"  Settings + live preview : {url}/")
    log(f"  OBS browser source URL  : {url}/overlay   (copy the exact URL from the settings page)")
    log("  Press Ctrl+C in this window to stop.")
    if args.open:
        webbrowser.open(url + "/")

    try:
        _httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        _stop.set()
        if _hook_thread_id:
            user32.PostThreadMessageW(_hook_thread_id, 0x0012, 0, 0)
        _httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
