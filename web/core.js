/* SleekKeys core: data model (profiles + layouts), renderer, live connection. Shared by the overlay and the editor. */
(() => {
  'use strict';

  const BASE = 56;            // key size in px at scale 1
  const MOUSE_W = 2.1;        // mouse width in key units (at mouse.scale 1)
  const MOUSE_H = MOUSE_W * 214 / 128;

  // ------------------------------------------------------------------ key catalogue (for the editor)
  // [code, label, default width]
  const CATALOG = [
    ['Escape', 'ESC', 1], ...[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((n) => ['F' + n, 'F' + n, 1]),
    ['Backquote', '`', 1], ...'1234567890'.split('').map((d) => ['Digit' + d, d, 1]), ['Minus', '-', 1], ['Equal', '=', 1], ['Backspace', 'BKSP', 2],
    ['Tab', 'TAB', 1.5], ...'QWERTYUIOP'.split('').map((c) => ['Key' + c, c, 1]), ['BracketLeft', '[', 1], ['BracketRight', ']', 1], ['Backslash', '\\', 1.5],
    ['CapsLock', 'CAPS', 1.75], ...'ASDFGHJKL'.split('').map((c) => ['Key' + c, c, 1]), ['Semicolon', ';', 1], ['Quote', "'", 1], ['Enter', 'ENTER', 2.25],
    ['ShiftLeft', 'SHIFT', 2.25], ...'ZXCVBNM'.split('').map((c) => ['Key' + c, c, 1]), ['Comma', ',', 1], ['Period', '.', 1], ['Slash', '/', 1], ['ShiftRight', 'SHIFT', 2.75],
    ['ControlLeft', 'CTRL', 1.25], ['MetaLeft', 'WIN', 1.25], ['AltLeft', 'ALT', 1.25], ['Space', '', 6.25], ['AltRight', 'ALT', 1.25], ['MetaRight', 'WIN', 1.25], ['ContextMenu', 'MENU', 1.25], ['ControlRight', 'CTRL', 1.25],
    ['ArrowUp', '\u25B2', 1], ['ArrowLeft', '\u25C0', 1], ['ArrowDown', '\u25BC', 1], ['ArrowRight', '\u25B6', 1],
    ['Insert', 'INS', 1], ['Delete', 'DEL', 1], ['Home', 'HOME', 1], ['End', 'END', 1], ['PageUp', 'PGUP', 1], ['PageDown', 'PGDN', 1],
    ['PrintScreen', 'PRT', 1], ['ScrollLock', 'SCR', 1], ['NumLock', 'NUM', 1],
    ...'0123456789'.split('').map((d) => ['Numpad' + d, 'N' + d, 1]),
    ['NumpadDivide', 'N/', 1], ['NumpadMultiply', 'N*', 1], ['NumpadSubtract', 'N-', 1], ['NumpadAdd', 'N+', 1], ['NumpadDecimal', 'N.', 1], ['NumpadEnter', 'N\u21B5', 1],
  ];
  const CATALOG_BY_CODE = {};
  CATALOG.forEach((k) => { if (!CATALOG_BY_CODE[k[0]]) CATALOG_BY_CODE[k[0]] = k; });

  // ------------------------------------------------------------------ built-in layouts
  const K = (c, l, w = 1) => ({ c, l, w });
  const letters = (s) => [...s].map((ch) => K('Key' + ch, ch));
  const row = (y, x, items) => {
    const out = [];
    let cx = x;
    for (const it of items) {
      if (typeof it === 'number') { cx += it; continue; }
      out.push({ c: it.c, l: it.l, x: cx, y, w: it.w, h: 1 });
      cx += it.w;
    }
    return out;
  };

  const PRESETS = {
    gamer: { name: 'Gamer (left hand)', build: () => ({
      keys: [
        ...row(0, 1.5, [K('Digit1', '1'), K('Digit2', '2'), K('Digit3', '3'), K('Digit4', '4'), K('Digit5', '5')]),
        ...row(1, 0, [K('Tab', 'TAB', 1.5), ...letters('QWERT')]),
        ...row(2, 0, [K('CapsLock', 'CAPS', 1.75), ...letters('ASDFG')]),
        ...row(3, 0, [K('ShiftLeft', 'SHIFT', 2.25), ...letters('ZXCV')]),
        ...row(4, 0, [K('ControlLeft', 'CTRL', 1.25), K('MetaLeft', 'WIN', 1.25), K('AltLeft', 'ALT', 1.25), K('Space', '', 3)]),
      ],
      mouse: { show: true, x: 7.5, y: 0.6, scale: 1 },
    }) },
    wasd: { name: 'WASD (compact)', build: () => ({
      keys: [
        ...row(0, 0, letters('QWER')),
        ...row(1, 0.3, letters('ASDF')),
        ...row(2, 0, [K('ShiftLeft', 'SHIFT', 1.5), K('Space', '', 2.6)]),
      ],
      mouse: { show: true, x: 4.6, y: 0, scale: 0.85 },
    }) },
    full: { name: 'Full keyboard + arrows', build: () => ({
      keys: [
        ...row(0, 0, [K('Backquote', '`'), ...'1234567890'.split('').map((d) => K('Digit' + d, d)), K('Minus', '-'), K('Equal', '='), K('Backspace', 'BKSP', 2)]),
        ...row(1, 0, [K('Tab', 'TAB', 1.5), ...letters('QWERTYUIOP'), K('BracketLeft', '['), K('BracketRight', ']'), K('Backslash', '\\', 1.5)]),
        ...row(2, 0, [K('CapsLock', 'CAPS', 1.75), ...letters('ASDFGHJKL'), K('Semicolon', ';'), K('Quote', "'"), K('Enter', 'ENTER', 2.25)]),
        ...row(3, 0, [K('ShiftLeft', 'SHIFT', 2.25), ...letters('ZXCVBNM'), K('Comma', ','), K('Period', '.'), K('Slash', '/'), K('ShiftRight', 'SHIFT', 2.75)]),
        ...row(4, 0, [K('ControlLeft', 'CTRL', 1.25), K('MetaLeft', 'WIN', 1.25), K('AltLeft', 'ALT', 1.25), K('Space', '', 6.25), K('AltRight', 'ALT', 1.25), K('MetaRight', 'WIN', 1.25), K('ContextMenu', 'MENU', 1.25), K('ControlRight', 'CTRL', 1.25)]),
        ...row(3, 16, [K('ArrowUp', '\u25B2')]),
        ...row(4, 15, [K('ArrowLeft', '\u25C0'), K('ArrowDown', '\u25BC'), K('ArrowRight', '\u25B6')]),
      ],
      mouse: { show: true, x: 18.7, y: 0.4, scale: 1 },
    }) },
    arrows: { name: 'Arrow keys only', build: () => ({
      keys: [...row(0, 1, [K('ArrowUp', '\u25B2')]), ...row(1, 0, [K('ArrowLeft', '\u25C0'), K('ArrowDown', '\u25BC'), K('ArrowRight', '\u25B6')])],
      mouse: { show: false, x: 4, y: 0, scale: 1 },
    }) },
    mouse: { name: 'Mouse only', build: () => ({ keys: [], mouse: { show: true, x: 0, y: 0, scale: 1 } }) },
  };

  // ------------------------------------------------------------------ options / profiles
  const DEFAULT_OPTS = {
    theme: 'glass', accent: '#3dffb5', scale: 1, gap: 6, radius: 12, alpha: 0.62,
    glow: 0.6, label: 0.3, font: 'Segoe UI', cps: 0, tilt: 1, bg: 'transparent',
  };
  const LIMITS = { scale: [0.3, 3], gap: [0, 24], radius: [0, 40], alpha: [0.05, 1], glow: [0, 2], label: [0.15, 0.6] };
  const THEMES = ['glass', 'neon', 'light', 'mono'];

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const num = (v, d) => (typeof v === 'number' && Number.isFinite(v) ? v : d);

  function makeLayout(presetId) {
    const p = PRESETS[presetId] || PRESETS.gamer;
    const l = p.build();
    l.name = p.name;
    return l;
  }

  // Never trust stored/imported data: clamp every number, whitelist strings, cap the key count.
  function normalizeLayout(raw) {
    const base = raw && typeof raw === 'object' ? raw : makeLayout('gamer');
    const keys = (Array.isArray(base.keys) ? base.keys : []).slice(0, 300).map((k) => ({
      c: String(k && k.c || '').slice(0, 32),
      l: String(k && k.l != null ? k.l : '').slice(0, 8),
      x: clamp(num(k && k.x, 0), 0, 60),
      y: clamp(num(k && k.y, 0), 0, 30),
      w: clamp(num(k && k.w, 1), 0.5, 20),
      h: clamp(num(k && k.h, 1), 0.5, 10),
    })).filter((k) => k.c);
    const m = base.mouse && typeof base.mouse === 'object' ? base.mouse : {};
    return {
      name: String(base.name || 'Custom').slice(0, 40),
      keys,
      mouse: { show: m.show !== false, x: clamp(num(m.x, 0), 0, 60), y: clamp(num(m.y, 0), 0, 30), scale: clamp(num(m.scale, 1), 0.4, 3) },
    };
  }

  function normalizeOpts(raw) {
    const o = { ...DEFAULT_OPTS, ...(raw && typeof raw === 'object' ? raw : {}) };
    for (const k of Object.keys(LIMITS)) o[k] = clamp(num(o[k], DEFAULT_OPTS[k]), LIMITS[k][0], LIMITS[k][1]);
    if (!THEMES.includes(o.theme)) o.theme = DEFAULT_OPTS.theme;
    if (!/^#[0-9a-f]{6}$/i.test(o.accent)) o.accent = DEFAULT_OPTS.accent;
    o.font = String(o.font || DEFAULT_OPTS.font).replace(/["\\<>]/g, '').slice(0, 40);
    o.cps = o.cps ? 1 : 0;
    o.tilt = o.tilt ? 1 : 0;
    o.bg = o.bg === 'green' || /^#[0-9a-f]{6}$/i.test(o.bg) ? o.bg : 'transparent';
    return o;
  }

  const normalizeProfile = (p) => ({ opts: normalizeOpts(p && p.opts), layout: normalizeLayout(p && p.layout) });

  function defaultConfig() {
    return { version: 1, active: 'Default', profiles: { Default: { opts: { ...DEFAULT_OPTS }, layout: makeLayout('gamer') } } };
  }

  function normalizeConfig(raw) {
    if (!raw || typeof raw !== 'object' || !raw.profiles || typeof raw.profiles !== 'object') return defaultConfig();
    const profiles = {};
    for (const [name, p] of Object.entries(raw.profiles).slice(0, 30)) profiles[String(name).slice(0, 40)] = normalizeProfile(p);
    if (!Object.keys(profiles).length) return defaultConfig();
    const active = profiles[raw.active] ? raw.active : Object.keys(profiles)[0];
    return { version: 1, active, profiles };
  }

  // ------------------------------------------------------------------ geometry
  function hexToRgb(hex) {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
    const n = parseInt(m ? m[1] : '3dffb5', 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  // size of the whole board in key units
  function bounds(layout, withCps) {
    let w = 0, h = 0;
    for (const k of layout.keys) { w = Math.max(w, k.x + k.w); h = Math.max(h, k.y + k.h); }
    if (layout.mouse.show) {
      w = Math.max(w, layout.mouse.x + MOUSE_W * layout.mouse.scale);
      h = Math.max(h, layout.mouse.y + MOUSE_H * layout.mouse.scale + (withCps ? 0.5 : 0));
    }
    return { w, h };
  }

  function applyTheme(el, o) {
    const unit = BASE * o.scale;
    const [r, g, b] = hexToRgb(o.accent);
    const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    const s = el.style;
    el.dataset.theme = o.theme;
    s.setProperty('--u', unit + 'px');
    s.setProperty('--gap', o.gap * o.scale + 'px');
    s.setProperty('--r', o.radius * o.scale + 'px');
    s.setProperty('--accent', o.accent);
    s.setProperty('--accent-rgb', `${r},${g},${b}`);
    s.setProperty('--accent-ink', lum > 0.55 ? '#07110c' : '#ffffff');
    s.setProperty('--alpha', String(o.alpha));
    s.setProperty('--glow', String(o.glow));
    s.setProperty('--fs', unit * o.label + 'px');
    s.setProperty('--font', `"${o.font}", "Segoe UI", system-ui, sans-serif`);
  }

  // ------------------------------------------------------------------ DOM helpers
  const el = (tag, cls) => { const e = document.createElement(tag); if (cls) e.className = cls; return e; };

  const BODY = 'M60 5 C26 5 9 32 9 74 V118 C9 160 30 185 60 185 C90 185 111 160 111 118 V74 C111 32 94 5 60 5 Z';
  function mouseSvg(uid) {
    return `
    <svg viewBox="-4 -14 128 214" xmlns="http://www.w3.org/2000/svg">
      <defs><clipPath id="skbody${uid}"><path d="${BODY}"/></clipPath></defs>
      <path class="m-body" d="${BODY}"/>
      <g clip-path="url(#skbody${uid})">
        <rect class="mb m-btn" data-b="l" x="0" y="0" width="59" height="84"/>
        <rect class="mb m-btn" data-b="r" x="61" y="0" width="60" height="84"/>
      </g>
      <path class="m-line" d="M60 5 V84 M10 84 H110"/>
      <rect class="mb m-wheel" data-b="m" x="52" y="28" width="16" height="34" rx="8"/>
      <path class="m-arrow up" d="M53 21 L60 13 L67 21"/>
      <path class="m-arrow dn" d="M53 69 L60 77 L67 69"/>
      <rect class="mb m-side" data-b="x1" x="-1" y="96" width="10" height="22" rx="5"/>
      <rect class="mb m-side" data-b="x2" x="-1" y="124" width="10" height="22" rx="5"/>
    </svg>`;
  }

  function keyNode(k, step, gap, unit) {
    const n = el('div', 'key');
    const s = document.createElement('span');
    s.textContent = k.l;
    n.appendChild(s);
    if (k.l.length > 1 && k.l.length <= 6 && !/[\u25B2-\u25C0]/.test(k.l)) n.classList.add('small');
    n.style.left = k.x * step + 'px';
    n.style.top = k.y * step + 'px';
    n.style.width = k.w * step - gap + 'px';
    n.style.height = k.h * step - gap + 'px';
    return n;
  }

  let uidCounter = 0;

  // ------------------------------------------------------------------ renderer
  function mount(root, o, layout) {
    root.innerHTML = '';
    applyTheme(root, o);
    const unit = BASE * o.scale, gap = o.gap * o.scale, step = unit + gap;

    const board = el('div', 'board');
    const keys = new Map();
    for (const k of layout.keys) {
      const n = keyNode(k, step, gap, unit);
      board.appendChild(n);
      if (!keys.has(k.c)) keys.set(k.c, []);
      keys.get(k.c).push(n);
    }
    const b = bounds(layout, o.cps);
    board.style.width = Math.max(0, b.w * step - gap) + 'px';
    board.style.height = Math.max(0, b.h * step - gap) + 'px';

    let tiltEl = null, cpsEl = null;
    const parts = {};
    if (layout.mouse.show) {
      const m = el('div', 'mouse');
      m.style.left = layout.mouse.x * step + 'px';
      m.style.top = layout.mouse.y * step + 'px';
      m.style.width = MOUSE_W * layout.mouse.scale * step + 'px';
      tiltEl = el('div', 'mouse-tilt');
      tiltEl.innerHTML = mouseSvg(++uidCounter);
      m.appendChild(tiltEl);
      if (o.cps) {
        cpsEl = el('div', 'cps');
        cpsEl.innerHTML = '<span data-c="l">L 0</span><span data-c="r">R 0</span>';
        m.appendChild(cpsEl);
      }
      tiltEl.querySelectorAll('[data-b]').forEach((n) => { parts[n.dataset.b] = n; });
      board.appendChild(m);
    }
    root.appendChild(board);

    const pulse = (node) => {
      const p = el('i', 'pulse');
      node.appendChild(p);
      p.addEventListener('animationend', () => p.remove());
    };
    const setKey = (code, down) => {
      const list = keys.get(code);
      if (!list) return;
      for (const n of list) {
        if (down) { if (!n.classList.contains('down')) pulse(n); n.classList.add('down'); }
        else n.classList.remove('down');
      }
    };
    const clicks = { l: [], r: [] };
    const setBtn = (btn, down) => {
      const n = parts[btn];
      if (!n) return;
      n.classList.toggle('on', !!down);
      if (down && clicks[btn]) clicks[btn].push(performance.now());
    };
    const wheel = (dir) => {
      const w = parts.m;
      if (!w) return;
      w.classList.remove('sc-up', 'sc-dn');
      void w.getBoundingClientRect();
      w.classList.add(dir > 0 ? 'sc-up' : 'sc-dn');
      const arrow = tiltEl.querySelector(dir > 0 ? '.m-arrow.up' : '.m-arrow.dn');
      arrow.classList.add('on');
      clearTimeout(arrow._t);
      arrow._t = setTimeout(() => arrow.classList.remove('on'), 160);
    };
    let vx = 0, vy = 0;
    const move = (dx, dy) => { vx += dx; vy += dy; };
    const releaseAll = () => {
      keys.forEach((list) => list.forEach((n) => n.classList.remove('down')));
      Object.values(parts).forEach((n) => n.classList.remove('on'));
    };

    let raf = 0, lastCps = 0;
    const loop = (t) => {
      if (tiltEl && o.tilt) {
        vx *= 0.88; vy *= 0.88;
        const cx = clamp(vx, -40, 40), cy = clamp(vy, -40, 40);
        tiltEl.style.transform = `translate(${(cx * 0.22).toFixed(2)}px, ${(cy * 0.22).toFixed(2)}px) rotate(${(cx * 0.16).toFixed(2)}deg)`;
      }
      if (cpsEl && t - lastCps > 100) {
        lastCps = t;
        for (const side of ['l', 'r']) {
          clicks[side] = clicks[side].filter((x) => t - x < 1000);
          cpsEl.querySelector(`[data-c="${side}"]`).textContent = `${side.toUpperCase()} ${clicks[side].length}`;
        }
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    const rect = board.getBoundingClientRect();
    const codes = [...keys.keys()];
    return {
      codes,
      size: { w: Math.ceil(rect.width), h: Math.ceil(rect.height) },
      setKey, setBtn, wheel, move, releaseAll,
      handle(ev) {
        if (ev.t === 'k') setKey(ev.c, ev.d);
        else if (ev.t === 'm') setBtn(ev.b, ev.d);
        else if (ev.t === 'w' && !ev.h) wheel(ev.v);
        else if (ev.t === 'mv') move(ev.x, ev.y);
        else if (ev.t === 's') { releaseAll(); ev.k.forEach((c) => setKey(c, 1)); ev.m.forEach((m) => setBtn(m, 1)); }
      },
      destroy() { cancelAnimationFrame(raf); root.innerHTML = ''; },
    };
  }

  // ------------------------------------------------------------------ live connection
  // Only the keys the layout shows are requested, so everything else you type never leaves the keyboard hook.
  function connect(ctrl, handlers) {
    const url = '/events?codes=' + (ctrl.codes.length ? ctrl.codes.map(encodeURIComponent).join(',') : '_none_');
    const es = new EventSource(url);
    es.onopen = () => handlers.status && handlers.status(true);
    es.onerror = () => { handlers.status && handlers.status(false); ctrl.releaseAll(); };
    es.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data);
        if (ev.t === 'cfg') handlers.config && handlers.config(ev);
        else ctrl.handle(ev);
      } catch (_) { /* ignore */ }
    };
    return { close: () => es.close() };
  }

  function demo(ctrl) {
    let on = true;
    const codes = ctrl.codes;
    const tick = () => {
      if (!on) return;
      if (codes.length && Math.random() < 0.8) {
        const c = codes[Math.floor(Math.random() * codes.length)];
        ctrl.setKey(c, 1);
        setTimeout(() => ctrl.setKey(c, 0), 120 + Math.random() * 380);
      }
      const r = Math.random();
      if (r < 0.2) { const b = Math.random() < 0.7 ? 'l' : 'r'; ctrl.setBtn(b, 1); setTimeout(() => ctrl.setBtn(b, 0), 90 + Math.random() * 200); }
      else if (r < 0.32) ctrl.wheel(Math.random() < 0.5 ? 1 : -1);
      if (Math.random() < 0.4) ctrl.move((Math.random() - 0.5) * 90, (Math.random() - 0.5) * 60);
      setTimeout(tick, 140 + Math.random() * 220);
    };
    tick();
    return { stop() { on = false; } };
  }

  window.SleekKeys = {
    BASE, MOUSE_W, MOUSE_H, CATALOG, CATALOG_BY_CODE, PRESETS, DEFAULT_OPTS, LIMITS, THEMES,
    makeLayout, normalizeLayout, normalizeOpts, normalizeProfile, normalizeConfig, defaultConfig,
    bounds, applyTheme, hexToRgb, mouseSvg, keyNode, mount, connect, demo,
  };
})();
