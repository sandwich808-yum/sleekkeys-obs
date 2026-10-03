# SleekKeys

A clean, sleek **keyboard + mouse overlay for OBS** - a modern alternative to NohBoard.
Keys glow and pulse when pressed, the mouse tilts as you move it, the scroll wheel animates, and
the background is **truly transparent** (no green screen / chroma key needed).

It runs as a tiny background app (Python, standard library only - nothing to install) and shows up in OBS
as a normal **Browser Source**.

```
SleekKeys/
  sleekkeys.py        the app (input hooks + local web server)
  web/                the overlay + settings page
  obs/sleekkeys_obs.lua   optional OBS script: one-click setup inside OBS
  start.bat           run with a console window   (also opens the settings page)
  start-hidden.vbs    run silently in the background
  stop.bat            stop it
  selftest.py         automated check (python selftest.py while the app runs)
```

## Quick start (2 minutes)

1. Double-click **`start.bat`**. Your browser opens the **settings page** (`http://127.0.0.1:7878/`).
2. Pick a layout / theme / colour. The live preview reacts to your real keyboard and mouse.
   *Gamer (left hand)* is the same layout as your NohBoard screenshot.
3. Click **Copy URL**.
4. In OBS: **Sources -> + -> Browser** -> name it `SleekKeys` -> paste the URL -> set the width/height shown on the
   settings page -> OK. Leave the custom CSS alone.

That's it. Drag it where you want it on your scene.

### The easy way: the OBS script

In OBS go to **Tools -> Scripts -> +** and pick `obs/sleekkeys_obs.lua`. Then:

| Button | What it does |
|---|---|
| Start SleekKeys | launches the app (it also auto-starts when OBS opens, and stops when OBS closes) |
| Open settings page | style the overlay, then paste its URL into the "Overlay URL" box |
| **Add / update overlay in current scene** | creates the `SleekKeys` browser source for you |

If `pythonw` isn't found, put the full path to your `pythonw.exe` in "Python launcher".

## Layouts and themes

- **Layouts:** Gamer (left hand), WASD, Full keyboard + arrows, Mouse only.
- **Themes:** Glass, Neon, Light, Mono - plus any accent colour, scale, spacing, corner radius, opacity, glow, font.
- **Mouse:** left/right/middle/side buttons, scroll wheel (with up/down arrows), tilt with movement, optional clicks-per-second.
- Every setting lives in the URL, so one URL = one look. Use a different URL in each OBS scene if you like.

## Privacy

An input overlay needs to see your keystrokes, so here is exactly what happens:

- The app only listens on **127.0.0.1** (your own PC) and rejects requests that aren't addressed to localhost.
  It sends no CORS headers, so other websites cannot read the stream.
- The overlay asks the app for **only the keys in its layout**. Everything else you type (passwords, chat, ...)
  is never sent anywhere, not even to the overlay.
- Nothing is written to disk and nothing leaves your PC. There is no logging.
- **Pause overlay** (settings page) stops all input being forwarded instantly.
- Still: the keys that *are* in the layout are shown on stream. Pause or hide the source when typing something private
  on keys it displays (e.g. in the *Full keyboard* layout).

## Troubleshooting

- **Overlay doesn't react in a game** - if the game/app runs *as administrator*, Windows blocks input hooks from a normal
  program. Run `start.bat` as administrator too. (Games with kernel anti-cheat generally still work, since SleekKeys only
  reads input and never touches the game.)
- **"Could not start on port 7878"** - it's already running (check the settings page) or something else uses the port.
  Use `python sleekkeys.py --port 7879` and use that port in the URL.
- **Black box instead of transparent** - make sure you used a *Browser* source (not Window Capture) and didn't set the
  Background to a colour.
- **Wrong size/cropped** - set the source Width x Height to the numbers shown on the settings page.

## How it works (for tinkering)

`sleekkeys.py` installs Windows low-level keyboard and mouse hooks (`SetWindowsHookEx`), turns scan codes into
layout-independent key names, and streams them as Server-Sent Events from `/events`. `web/core.js` draws the keys and
reacts. New layouts are just a list of `{code, label, x, y, w}` in `core.js`.

Run `python selftest.py` (with the app running) to check the hooks, the stream and the security rules.

## License

MIT - see [LICENSE](LICENSE). Free to use, share and modify. Contributions and new layouts/themes are welcome.

