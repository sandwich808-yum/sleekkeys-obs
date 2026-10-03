# SleekKeys

A clean, sleek **keyboard + mouse overlay for OBS and streaming** - a modern alternative to NohBoard.
Keys glow and pulse as you press them, the mouse tilts as you move it, the scroll wheel animates, and the
background is **truly transparent** (no green screen / chroma key).

It is a normal **desktop app**: it lives in your system tray, starts with Windows, and has its own **drag-and-drop
layout maker**. No URLs to paste, no `.bat` files to run, nothing to restart when you close OBS.

## Install (30 seconds)

1. Download **`SleekKeys.exe`** and put it somewhere permanent (for example `Documents\SleekKeys`).
2. Double-click it. A welcome box asks if it should start with Windows - say **Yes** (recommended).
3. The editor opens in its own window. SleekKeys now sits in the tray (bottom-right, by the clock):
   **click the icon** to open the editor, **right-click** for pause / start-with-Windows / quit.

No Python needed - it is a single file with everything inside.

## Use it in OBS (once, ever)

In OBS: **Tools -> Scripts -> +** and pick `obs/sleekkeys_obs.lua` (from this repo). Done.

Every time OBS starts, the script makes sure SleekKeys is running and adds a **SleekKeys** browser source to your
scene, already sized to fit your layout. You never touch it again - design everything in the SleekKeys editor and the
overlay in OBS updates **live**.

Prefer to do it by hand? Add a *Browser* source with the address `http://127.0.0.1:7878/overlay` (it never changes).

## The editor

| Tab | What it does |
|---|---|
| **Appearance** | Theme (Glass / Neon / Light / Mono), accent colour, font, scale, spacing, corner radius, opacity, glow, mouse tilt, clicks-per-second, background. Live preview reacts to your real keyboard and mouse. |
| **Layout maker** | Build your own layout. **Drag** keys, **drag the corner to resize**, snap to a grid, **add a key by just pressing it**, assign any key, move/scale/remove the mouse, undo/redo, **import/export** layouts to share with friends. Starts from presets: Gamer (left hand), WASD, Full keyboard + arrows, Arrows, Mouse only. |
| **Profiles** | Save several complete looks (layout + style). One is your OBS default; give other scenes their own look with `http://127.0.0.1:7878/overlay?profile=Name`. |
| **General & OBS** | Start with Windows, pause, the OBS address, the recommended source size. |

Everything saves automatically to `%APPDATA%\SleekKeys\config.json`.

## Privacy

An input overlay has to see your keystrokes, so here is exactly what happens:

- The app only listens on **127.0.0.1** (your own PC) and rejects requests not addressed to localhost
  (protects against DNS-rebinding). It sends no CORS headers, so **other websites cannot read your keys or settings**,
  and changing settings requires a custom header a web page cannot add.
- The overlay asks for **only the keys that are in its layout**. Everything else you type (passwords, chat, ...) is never
  sent anywhere - not even to the overlay.
- Nothing is written to disk except your settings, and nothing leaves your PC. There is no telemetry and no key logging.
- **Pause overlay** (tray menu) instantly stops all input being forwarded.
- Still: keys that *are* in your layout are shown on stream. Pause it, or use a small layout, when typing something private
  on those keys.

## Troubleshooting

- **Overlay doesn't react in a game** - if the game runs *as administrator*, Windows blocks input hooks from normal
  programs. Run `SleekKeys.exe` as administrator too.
- **Windows SmartScreen / antivirus warns about the file** - SleekKeys reads global keyboard and mouse input (that is its
  job), which some antivirus programs flag on unsigned apps. The full source is here: inspect it, or build it yourself with
  `build.bat`.
- **"port 7878 is already in use"** - another program uses it. Start with `SleekKeys.exe --port 7879` and use that port in
  OBS.
- **Black box instead of transparent** - make sure it is a *Browser* source, and Background is *Transparent* in the editor.
- **Logs** are in `%APPDATA%\SleekKeys\sleekkeys.log`.

## Uninstall

Tray menu -> turn off *Start with Windows* -> *Quit*. Delete `SleekKeys.exe`, the folder `%APPDATA%\SleekKeys` and the
Start-menu shortcut. In OBS remove the script and the `SleekKeys` source.

## Build / run from source

Python 3.10+ on Windows, standard library only.

```
python sleekkeys.py --editor      # run from source
build.bat                         # builds dist\SleekKeys.exe (PyInstaller, in a throwaway venv)
```

Tests (start the app with `--data-dir %TEMP%\sk_test --background` first, then):

```
python selftest.py          # input hooks, event stream, security rules
python tools/api_test.py    # settings API validation
python tools/tray_test.py   # tray icon + menu actions
```

How it works: `sleekkeys.py` installs Windows low-level keyboard and mouse hooks, turns scan codes into
layout-independent key names, and streams them as Server-Sent Events. `web/core.js` renders the keys and mouse; the
editor (`web/editor.js`) edits a plain JSON config (profiles -> style + layout). The editor window is Edge/Chrome in
`--app` mode (no tabs, no address bar).

## License

MIT - see [LICENSE](LICENSE). Free to use, share and modify. Contributions, layouts and themes are welcome.
