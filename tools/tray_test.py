"""
Tray integration test. Start the app first with its own data folder, e.g.
    python sleekkeys.py --data-dir %TEMP%\\sk_testdata --background
then:  python tools/tray_test.py
It checks the tray icon exists, drives the menu commands (open editor / pause / quit) via WM_COMMAND.
"""
import ctypes
import ctypes.wintypes as wt
import json
import subprocess
import sys
import time
import urllib.request

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 7878
user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
user32.FindWindowW.argtypes = (wt.LPCWSTR, wt.LPCWSTR)
user32.FindWindowW.restype = wt.HWND
user32.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

WM_COMMAND = 0x0111
results = []


def check(name, ok):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)


def info():
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/info", timeout=3))


class NOTIFYICONIDENTIFIER(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT),
                ("guid", ctypes.c_ubyte * 16)]


hwnd = user32.FindWindowW("SleekKeysTrayWindow", None)
check("tray window exists", bool(hwnd))

nii = NOTIFYICONIDENTIFIER()
nii.cbSize = ctypes.sizeof(nii)
nii.hWnd = hwnd
nii.uID = 1
rect = wt.RECT()
hr = shell32.Shell_NotifyIconGetRect(ctypes.byref(nii), ctypes.byref(rect))
check("tray icon is registered with Windows (hr=%d, rect=%d,%d)" % (hr, rect.left, rect.top), hr == 0)

# pause via menu command
before = info()["paused"]
user32.PostMessageW(hwnd, WM_COMMAND, 2, 0)
time.sleep(0.4)
after = info()["paused"]
check("menu 'Pause overlay' toggles pause (%s -> %s)" % (before, after), before != after)
user32.PostMessageW(hwnd, WM_COMMAND, 2, 0)
time.sleep(0.4)
check("pause toggles back", info()["paused"] == before)


def edge_app_windows():
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
                          "Where-Object { $_.CommandLine -like '*--app=http://127.0.0.1:%d*' } | Measure-Object | "
                          "Select-Object -ExpandProperty Count" % PORT], capture_output=True, text=True).stdout.strip()
    return int(out or 0)


n0 = edge_app_windows()
user32.PostMessageW(hwnd, WM_COMMAND, 1, 0)   # Open editor
time.sleep(3)
n1 = edge_app_windows()
check("menu 'Open editor' launches the app window (--app mode) (%d -> %d processes)" % (n0, n1), n1 > n0)

user32.PostMessageW(hwnd, WM_COMMAND, 9, 0)   # Quit
time.sleep(1.5)
try:
    info()
    check("menu 'Quit' stops the app", False)
except Exception:
    check("menu 'Quit' stops the app", True)
print("\n%d/%d passed" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
