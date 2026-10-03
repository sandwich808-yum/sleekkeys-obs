#!/usr/bin/env python3
"""
SleekKeys - a clean keyboard + mouse input overlay for OBS (a NohBoard alternative).

A tray app:
  * Low-level Windows hooks watch the keyboard and mouse.
  * A local web server (127.0.0.1 only) streams those events to the overlay and hosts the editor.
  * The editor opens in its own app window (no browser tabs / URL bar); your settings are saved in
    %APPDATA%\\SleekKeys and applied live - the OBS browser source URL never changes.

Standard library only. Windows only.

    SleekKeys.exe                 start (tray icon + editor on first run)
    SleekKeys.exe --background    start silently in the tray (what "start with Windows" uses)
    SleekKeys.exe --editor        open the editor window
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
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser

try:
    import winreg
except ImportError:  # not Windows
    winreg = None  # type: ignore

VERSION = "2.0.0"
APP_NAME = "SleekKeys"
EDITOR_TITLE = "SleekKeys Editor"
FROZEN = bool(getattr(sys, "frozen", False))
RES_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(RES_DIR, "web")
ICON_PATH = os.path.join(RES_DIR, "icon.ico")
DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
LOG_PATH = os.path.join(DATA_DIR, "sleekkeys.log")
MAX_CONFIG_BYTES = 512 * 1024
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

PORT = 7878


def log(*args) -> None:
    """Console + log file (the packaged app has no console)."""
    line = " ".join(str(a) for a in args)
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 200_000:
            os.replace(LOG_PATH, LOG_PATH + ".old")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + line + "\n")
    except Exception:
        pass


# --------------------------------------------------------------------------------------
# Scan code -> KeyboardEvent.code names (layout independent: QWERTY, AZERTY, ...).
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
# Event hub: fans events out to every connected page (Server-Sent Events).
# --------------------------------------------------------------------------------------
class Client:
    def __init__(self, codes: set[str] | None):
        self.q: queue.Queue[str] = queue.Queue(maxsize=512)
        self.codes = codes  # None = every key; otherwise only these codes (privacy)

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
        self.config_version = 0

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
            return {"t": "s", "k": keys, "m": sorted(self.held_buttons), "v": self.config_version}

    def publish(self, ev: dict) -> None:
        if self.paused and ev["t"] != "cfg":
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
                pass  # slow client: drop rather than block the input hook

    def set_paused(self, value: bool) -> None:
        self.paused = value
        if value:
            with self.lock:
                self.held_keys.clear()
                self.held_buttons.clear()
        self.publish({"t": "cfg", "v": self.config_version, "paused": value})


hub = Hub()


# --------------------------------------------------------------------------------------
# Config file (profiles + layouts), autostart, editor window
# --------------------------------------------------------------------------------------
_config_lock = threading.Lock()


def read_config() -> str | None:
    with _config_lock:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None


def write_config(raw: bytes) -> tuple[bool, str]:
    if len(raw) > MAX_CONFIG_BYTES:
        return False, "config too large"
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return False, "invalid JSON"
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), dict) or not data["profiles"]:
        return False, "config needs a non-empty 'profiles' object"
    if not isinstance(data.get("active"), str):
        return False, "config needs an 'active' profile name"
    with _config_lock:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CONFIG_PATH)
    hub.config_version += 1
    hub.publish({"t": "cfg", "v": hub.config_version, "paused": hub.paused})
    return True, "ok"


def suggested_size() -> list[int]:
    """Browser-source size that fits the default profile (same maths as core.js `bounds`). Used by the OBS script."""
    try:
        cfg = json.loads(read_config() or "")
        prof = cfg["profiles"][cfg["active"]]
        opts, lay = prof.get("opts", {}), prof.get("layout", {})
        scale = min(3.0, max(0.3, float(opts.get("scale", 1))))
        gap = min(24.0, max(0.0, float(opts.get("gap", 6)))) * scale
        step = 56 * scale + gap
        bw = bh = 0.0
        for k in lay.get("keys", [])[:300]:
            bw = max(bw, float(k.get("x", 0)) + float(k.get("w", 1)))
            bh = max(bh, float(k.get("y", 0)) + float(k.get("h", 1)))
        m = lay.get("mouse") or {}
        if m.get("show", True):
            ms = float(m.get("scale", 1))
            bw = max(bw, float(m.get("x", 0)) + 2.1 * ms)
            bh = max(bh, float(m.get("y", 0)) + 2.1 * 214 / 128 * ms + (0.5 if opts.get("cps") else 0))
        import math
        return [int(math.ceil(bw * step - gap)) + 28, int(math.ceil(bh * step - gap)) + 28]
    except Exception:
        return [640, 340]


def create_start_menu_shortcut() -> None:
    """Adds 'SleekKeys' to the Start menu so it can be found and launched like any app."""
    try:
        programs = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs")
        lnk = os.path.join(programs, "SleekKeys.lnk")
        if FROZEN:
            target, args, icon = sys.executable, "", sys.executable + ",0"
        else:
            pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            target, args, icon = (pyw if os.path.exists(pyw) else sys.executable), f'"{os.path.abspath(__file__)}"', ICON_PATH
        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');$s.TargetPath='%s';$s.Arguments='%s';"
              "$s.IconLocation='%s';$s.Description='SleekKeys - keyboard and mouse overlay editor';$s.Save()"
              % (lnk, target, args.replace("'", "''"), icon))
        subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                       creationflags=0x08000000, timeout=20)
    except Exception as e:
        log("start menu shortcut failed:", e)


def _autostart_command() -> str:
    if FROZEN:
        return f'"{sys.executable}" --background'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.exists(pyw) else sys.executable
    return f'"{exe}" "{os.path.abspath(__file__)}" --background'


def autostart_enabled() -> bool:
    if not winreg:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(enabled: bool) -> bool:
    if not winreg:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _autostart_command())
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError as e:
        log("autostart failed:", e)
        return False


def _find_browser() -> str | None:
    pf = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")]
    rels = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
            r"BraveSoftware\Brave-Browser\Application\brave.exe"]
    for rel in rels:
        for base in pf:
            if base and os.path.exists(os.path.join(base, rel)):
                return os.path.join(base, rel)
    return None


def _focus_existing_editor() -> bool:
    """If the editor window is already open, bring it to the front instead of opening another."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def enum_proc(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value.startswith(EDITOR_TITLE):
                    found.append(hwnd)
        return True

    user32.EnumWindows(enum_proc, 0)
    if found:
        user32.ShowWindow(found[0], 9)  # SW_RESTORE
        user32.SetForegroundWindow(found[0])
        return True
    return False


def open_editor() -> None:
    """Opens the editor as a standalone app window (Edge/Chrome --app mode: no tabs, no URL bar)."""
    try:
        if _focus_existing_editor():
            return
    except Exception:
        pass
    url = f"http://127.0.0.1:{PORT}/"
    browser = _find_browser()
    if not browser:
        webbrowser.open(url)
        return
    profile = os.path.join(DATA_DIR, "app-window")
    try:
        subprocess.Popen(
            [browser, f"--app={url}", "--window-size=1400,900", f"--user-data-dir={profile}",
             "--no-first-run", "--no-default-browser-check", "--disable-features=Translate,msEdgeSidebarV2"],
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
    except OSError as e:
        log("could not launch app window:", e)
        webbrowser.open(url)


# --------------------------------------------------------------------------------------
# Windows low-level hooks + tray icon (all on one thread with a message loop)
# --------------------------------------------------------------------------------------
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

WH_KEYBOARD_LL, WH_MOUSE_LL = 13, 14
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x200, 0x201, 0x202
WM_RBUTTONDOWN, WM_RBUTTONUP, WM_MBUTTONDOWN, WM_MBUTTONUP = 0x204, 0x205, 0x207, 0x208
WM_MOUSEWHEEL, WM_XBUTTONDOWN, WM_XBUTTONUP, WM_MOUSEHWHEEL = 0x20A, 0x20B, 0x20C, 0x20E
LLKHF_EXTENDED = 0x01

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT), ("uFlags", wt.UINT),
                ("uCallbackMessage", wt.UINT), ("hIcon", wt.HICON), ("szTip", wt.WCHAR * 128),
                ("dwState", wt.DWORD), ("dwStateMask", wt.DWORD), ("szInfo", wt.WCHAR * 256),
                ("uVersion", wt.UINT), ("szInfoTitle", wt.WCHAR * 64), ("dwInfoFlags", wt.DWORD),
                ("guidItem", GUID), ("hBalloonIcon", wt.HICON)]


user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD)
user32.SetWindowsHookExW.restype = wt.HHOOK
user32.CallNextHookEx.argtypes = (wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM)
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = (wt.HHOOK,)
user32.GetMessageW.argtypes = (ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT)
user32.DispatchMessageW.argtypes = (ctypes.POINTER(wt.MSG),)
user32.TranslateMessage.argtypes = (ctypes.POINTER(wt.MSG),)
user32.PostThreadMessageW.argtypes = (wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.DefWindowProcW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassW.argtypes = (ctypes.POINTER(WNDCLASSW),)
user32.RegisterClassW.restype = wt.ATOM
user32.CreateWindowExW.argtypes = (wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID)
user32.CreateWindowExW.restype = wt.HWND
user32.DestroyWindow.argtypes = (wt.HWND,)
user32.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.LoadImageW.argtypes = (wt.HINSTANCE, wt.LPCWSTR, wt.UINT, ctypes.c_int, ctypes.c_int, wt.UINT)
user32.LoadImageW.restype = wt.HANDLE
user32.LoadIconW.argtypes = (wt.HINSTANCE, wt.LPCWSTR)
user32.LoadIconW.restype = wt.HICON
user32.CreatePopupMenu.restype = wt.HMENU
user32.AppendMenuW.argtypes = (wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR)
user32.TrackPopupMenu.argtypes = (wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.LPVOID)
user32.DestroyMenu.argtypes = (wt.HMENU,)
user32.SetForegroundWindow.argtypes = (wt.HWND,)
user32.RegisterWindowMessageW.argtypes = (wt.LPCWSTR,)
user32.MessageBoxW.argtypes = (wt.HWND, wt.LPCWSTR, wt.LPCWSTR, wt.UINT)
shell32.Shell_NotifyIconW.argtypes = (wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW))
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


# ---------- tray icon
WM_APP_TRAY = 0x8001
WM_COMMAND, WM_DESTROY = 0x0111, 0x0002
NIM_ADD, NIM_DELETE, NIM_MODIFY = 0, 2, 1
NIF_MESSAGE, NIF_ICON, NIF_TIP = 1, 2, 4
MF_STRING, MF_CHECKED, MF_SEPARATOR = 0, 8, 0x800
TPM_RIGHTBUTTON, TPM_RETURNCMD = 2, 0x100
CMD_OPEN, CMD_PAUSE, CMD_AUTOSTART, CMD_QUIT = 1, 2, 3, 9

_tray = {"hwnd": None, "nid": None, "taskbar_msg": 0, "enabled": True}


def tray_command(cmd: int) -> None:
    if cmd == CMD_OPEN:
        threading.Thread(target=open_editor, daemon=True).start()
    elif cmd == CMD_PAUSE:
        hub.set_paused(not hub.paused)
    elif cmd == CMD_AUTOSTART:
        set_autostart(not autostart_enabled())
    elif cmd == CMD_QUIT:
        threading.Thread(target=shutdown, daemon=True).start()


def _show_menu(hwnd) -> None:
    menu = user32.CreatePopupMenu()
    user32.AppendMenuW(menu, MF_STRING, CMD_OPEN, "Open SleekKeys editor")
    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
    user32.AppendMenuW(menu, MF_STRING | (MF_CHECKED if hub.paused else 0), CMD_PAUSE, "Pause overlay")
    user32.AppendMenuW(menu, MF_STRING | (MF_CHECKED if autostart_enabled() else 0), CMD_AUTOSTART,
                       "Start with Windows")
    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
    user32.AppendMenuW(menu, MF_STRING, CMD_QUIT, "Quit SleekKeys")
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    user32.SetForegroundWindow(hwnd)
    cmd = user32.TrackPopupMenu(menu, TPM_RETURNCMD | TPM_RIGHTBUTTON, pt.x, pt.y, 0, hwnd, None)
    user32.PostMessageW(hwnd, 0, 0, 0)  # WM_NULL: lets the menu close properly
    user32.DestroyMenu(menu)
    if cmd:
        tray_command(cmd)


def _add_tray_icon() -> None:
    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = _tray["hwnd"]
    nid.uID = 1
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    nid.uCallbackMessage = WM_APP_TRAY
    icon = None
    if os.path.exists(ICON_PATH):
        icon = user32.LoadImageW(None, ICON_PATH, 1, 0, 0, 0x10 | 0x40)  # IMAGE_ICON, LR_LOADFROMFILE|DEFAULTSIZE
    nid.hIcon = icon or user32.LoadIconW(None, ctypes.cast(32512, wt.LPCWSTR))
    nid.szTip = "SleekKeys - click to open the editor"
    _tray["nid"] = nid
    shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))


def _wnd_proc(hwnd, msg, w_param, l_param):
    try:
        if msg == WM_APP_TRAY:
            ev = l_param & 0xFFFF
            if ev == WM_LBUTTONUP:
                tray_command(CMD_OPEN)
            elif ev in (WM_RBUTTONUP, 0x7B):  # WM_CONTEXTMENU
                _show_menu(hwnd)
            return 0
        if msg == WM_COMMAND:
            tray_command(w_param & 0xFFFF)  # also lets tests drive the menu
            return 0
        if _tray["taskbar_msg"] and msg == _tray["taskbar_msg"]:
            _add_tray_icon()  # Explorer restarted
            return 0
    except Exception:
        pass
    return user32.DefWindowProcW(hwnd, msg, w_param, l_param)


_wnd_cb = WNDPROC(_wnd_proc)


def _create_tray(module) -> None:
    cls = WNDCLASSW()
    cls.lpfnWndProc = _wnd_cb
    cls.hInstance = module
    cls.lpszClassName = "SleekKeysTrayWindow"
    user32.RegisterClassW(ctypes.byref(cls))
    hwnd = user32.CreateWindowExW(0, cls.lpszClassName, "SleekKeys", 0, 0, 0, 0, 0, None, None, module, None)
    if not hwnd:
        log("tray window failed:", ctypes.get_last_error())
        return
    _tray["hwnd"] = hwnd
    _tray["taskbar_msg"] = user32.RegisterWindowMessageW("TaskbarCreated")
    _add_tray_icon()


def hook_thread(with_tray: bool) -> None:
    """Installs both hooks (+ tray icon) and pumps messages (required for hooks and windows to work)."""
    global _hook_thread_id
    _hook_thread_id = kernel32.GetCurrentThreadId()
    module = kernel32.GetModuleHandleW(None)
    kb = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _kb_cb, module, 0)
    ms = user32.SetWindowsHookExW(WH_MOUSE_LL, _ms_cb, module, 0)
    if not kb or not ms:
        log("ERROR: could not install input hooks (error %d)." % ctypes.get_last_error())
        _stop.set()
        return
    if with_tray:
        try:
            _create_tray(module)
        except Exception as e:  # the overlay must keep working even if the tray fails
            log("tray icon unavailable:", e)
    msg = wt.MSG()
    while not _stop.is_set():
        r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if r in (0, -1):
            break
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    if _tray["nid"] is not None:
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(_tray["nid"]))
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
    # CORS headers either, so other websites cannot read the key stream or the settings.
    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        return host in ("localhost", "127.0.0.1", "[::1]", "::1")

    def _send(self, code: int, body: bytes, ctype: str = "text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, b"forbidden")
        url = urllib.parse.urlparse(self.path)
        path = url.path
        if path == "/events":
            return self._events(urllib.parse.parse_qs(url.query))
        if path == "/api/info":
            return self._json({"name": APP_NAME, "version": VERSION, "paused": hub.paused,
                               "autostart": autostart_enabled(), "frozen": FROZEN,
                               "dataDir": DATA_DIR, "configVersion": hub.config_version,
                               "size": suggested_size()})
        if path == "/api/config":
            raw = read_config()
            if raw is None:
                return self._json(None)
            return self._send(200, raw.encode("utf-8"), "application/json; charset=utf-8")
        if path in ("/", "/settings", "/editor"):
            path = "/index.html"
        elif path == "/overlay":
            path = "/overlay.html"
        elif path == "/icon.png":
            path = "/icon.png"
        full = os.path.normpath(os.path.join(WEB_DIR, path.lstrip("/")))
        if not full.startswith(WEB_DIR) or not os.path.isfile(full):
            return self._send(404, b"not found")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)

    def do_POST(self):
        # state-changing requests need a custom header: a website cannot add it without our consent (CORS)
        if not self._host_ok() or self.headers.get("X-SleekKeys") != "1":
            return self._send(403, b"forbidden")
        path = urllib.parse.urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if 0 < length <= MAX_CONFIG_BYTES + 1 else b""
        if path == "/api/config":
            ok, msg = write_config(body)
            return self._json({"ok": ok, "message": msg, "version": hub.config_version}, 200 if ok else 400)
        if path == "/api/quit":
            self._send(200, b"bye")
            threading.Thread(target=shutdown, daemon=True).start()
        elif path == "/api/pause":
            hub.set_paused(not hub.paused)
            self._json({"paused": hub.paused})
        elif path == "/api/autostart":
            try:
                want = bool(json.loads(body or b"{}").get("enabled"))
            except Exception:
                want = not autostart_enabled()
            set_autostart(want)
            self._json({"autostart": autostart_enabled()})
        elif path == "/api/open-editor":
            threading.Thread(target=open_editor, daemon=True).start()
            self._json({"ok": True})
        else:
            self._send(404, b"not found")

    def _events(self, query):
        codes = None
        if "codes" in query:
            codes = set(c for c in query["codes"][0].split(",") if c)
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
    allow_reuse_address = False  # a second copy must fail loudly instead of sharing the port


_httpd: Server | None = None
_mutex = None


def shutdown() -> None:
    _stop.set()
    if _hook_thread_id:
        user32.PostThreadMessageW(_hook_thread_id, 0x0012, 0, 0)  # WM_QUIT
    if _httpd:
        _httpd.shutdown()


def _already_running() -> bool:
    """Single-instance guard (a named mutex)."""
    global _mutex
    kernel32.CreateMutexW.argtypes = (wt.LPVOID, wt.BOOL, wt.LPCWSTR)
    kernel32.CreateMutexW.restype = wt.HANDLE
    _mutex = kernel32.CreateMutexW(None, False, "Local\\SleekKeys_SingleInstance")
    return ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS


def main() -> int:
    global _httpd, PORT, DATA_DIR, CONFIG_PATH, LOG_PATH
    ap = argparse.ArgumentParser(description="SleekKeys - keyboard + mouse overlay for OBS")
    ap.add_argument("--port", type=int, default=7878)
    ap.add_argument("--background", action="store_true", help="start silently in the tray (no editor window)")
    ap.add_argument("--editor", action="store_true", help="open the editor window")
    ap.add_argument("--no-tray", action="store_true", help="no tray icon (testing)")
    ap.add_argument("--data-dir", help="store settings here (testing)")
    ap.add_argument("--open", action="store_true", help=argparse.SUPPRESS)  # old flag
    args = ap.parse_args()
    PORT = args.port
    if args.data_dir:
        DATA_DIR = os.path.abspath(args.data_dir)
        CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
        LOG_PATH = os.path.join(DATA_DIR, "sleekkeys.log")

    if os.name != "nt":
        log("SleekKeys only runs on Windows.")
        return 1
    if not os.path.isdir(WEB_DIR):
        log("Missing 'web' folder:", WEB_DIR)
        return 1

    if not args.data_dir and _already_running():
        # SleekKeys is already in the tray: just bring up the editor (unless we were started silently)
        if not args.background:
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/open-editor", method="POST",
                                             headers={"X-SleekKeys": "1"})
                urllib.request.urlopen(req, timeout=3).read()
            except Exception:
                open_editor()
        return 0

    try:
        _httpd = Server(("127.0.0.1", PORT), Handler)
    except OSError as e:
        log(f"Could not start on port {PORT}: {e}")
        user32.MessageBoxW(None, f"SleekKeys could not start: port {PORT} is already in use.\n\n"
                           f"Close the other program using it, or run SleekKeys with --port <number>.",
                           "SleekKeys", 0x10)
        return 1

    setup_marker = os.path.join(DATA_DIR, "setup-done")
    first_run = not os.path.exists(setup_marker) and not os.path.exists(CONFIG_PATH)
    threading.Thread(target=hook_thread, args=(not args.no_tray,), daemon=True).start()
    threading.Thread(target=motion_thread, daemon=True).start()
    log(f"SleekKeys {VERSION} running on http://127.0.0.1:{PORT}  (settings: {DATA_DIR})")

    if first_run and not args.background and not args.no_tray and not args.data_dir:
        # one-time setup: Start-menu entry + a question, so the overlay is simply always there from now on
        threading.Thread(target=create_start_menu_shortcut, daemon=True).start()
        answer = user32.MessageBoxW(
            None, "Start SleekKeys automatically when you sign in to Windows?\n\n"
                  "(Recommended - your OBS overlay will always just work. You can change this any time in the "
                  "tray menu.)", "Welcome to SleekKeys", 0x24 | 0x40000)  # YESNO | ICONQUESTION | TOPMOST
        if answer == 6:  # IDYES
            set_autostart(True)
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            open(setup_marker, "w").close()  # never ask again
        except OSError:
            pass

    if (first_run or args.editor or args.open) and not args.background:
        threading.Thread(target=open_editor, daemon=True).start()

    try:
        _httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        _stop.set()
        if _hook_thread_id:
            user32.PostThreadMessageW(_hook_thread_id, 0x0012, 0, 0)
        time.sleep(0.2)
        _httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
