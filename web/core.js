/* SleekKeys core: layouts, options, renderer and the live connection. Used by the overlay and the settings preview. */
(() => {
  'use strict';

  const BASE = 56; // key size in px at scale 1

  // ------------------------------------------------------------------ layouts
  const L = (code, label, w = 1) => ({ code, label, w });
  const letters = (s) => [...s].map((ch) => L('Key' + ch, ch));
  const row = (y, x, items) => {
    const out = [];
    let cx = x;
    for (const it of items) {
      if (typeof it === 'number') { cx += it; continue; } // spacer
      out.push({ c: it.code, l: it.label, x: cx, y, w: it.w });
      cx += it.w;
    }
    return out;
  };

  const LAYOUTS = {
    gamer: {
      name: 'Gamer (left hand)',
      keys: [
        ...row(0, 1.5, [L('Digit1', '1'), L('Digit2', '2'), L('Digit3', '3'), L('Digit4', '4'), L('Digit5', '5')]),
        ...row(1, 0, [L('Tab', 'TAB', 1.5), ...letters('QWERT')]),
        ...row(2, 0, [L('CapsLock', 'CAPS', 1.75), ...letters('ASDFG')]),
        ...row(3, 0, [L('ShiftLeft', 'SHIFT', 2.25), ...letters('ZXCV')]),
        ...row(4, 0, [L('ControlLeft', 'CTRL', 1.25), L('MetaLeft', 'WIN', 1.25), L('AltLeft', 'ALT', 1.25), L('Space', '', 3)]),
      ],
    },
    wasd: {
      name: 'WASD (compact)',
      keys: [
        ...row(0, 0, letters('QWER')),
        ...row(1, 0.3, letters('ASDF')),
        ...row(2, 0, [L('ShiftLeft', 'SHIFT', 1.5), L('Space', '', 2.6)]),
      ],
    },
    compact: {
      name: 'Full keyboard + arrows',
      keys: [
        ...row(0, 0, [L('Backquote', '`'), ...'1234567890'.split('').map((d) => L('Digit' + d, d)), L('Minus', '-'), L('Equal', '='), L('Backspace', 'BKSP', 2)]),
        ...row(1, 0, [L('Tab', 'TAB', 1.5), ...letters('QWERTYUIOP'), L('BracketLeft', '['), L('BracketRight', ']'), L('Backslash', '\\', 1.5)]),
        ...row(2, 0, [L('CapsLock', 'CAPS', 1.75), ...letters('ASDFGHJKL'), L('Semicolon', ';'), L('Quote', "'"), L('Enter', 'ENTER', 2.25)]),
        ...row(3, 0, [L('ShiftLeft', 'SHIFT', 2.25), ...letters('ZXCVBNM'), L('Comma', ','), L('Period', '.'), L('Slash', '/'), L('ShiftRight', 'SHIFT', 2.75)]),
        ...row(4, 0, [L('ControlLeft', 'CTRL', 1.25), L('MetaLeft', 'WIN', 1.25), L('AltLeft', 'ALT', 1.25), L('Space', '', 6.25), L('AltRight', 'ALT', 1.25), L('MetaRight', 'WIN', 1.25), L('ContextMenu', 'MENU', 1.25), L('ControlRight', 'CTRL', 1.25)]),
        ...row(3, 16, [L('ArrowUp', '▲')]),
        ...row(4, 15, [L('ArrowLeft', '◀'), L('ArrowDown', '▼'), L('ArrowRight', '▶')]),
      ],
    },
    mouse: { name: 'Mouse only', keys: [] },
  };

  // ------------------------------------------------------------------ options
  const DEFAULTS = {
    layout: 'gamer', theme: 'glass', accent: '#3dffb5', scale: 1, gap: 6, radius: 12, alpha: 0.62,
    glow: 0.6, label: 0.3, font: 'Segoe UI', mouse: 1, side: 'right', cps: 0, tilt: 1, bg: 'transparent',
  };

  function parse(search) {
    const q = new URLSearchParams(search);
    const o = { ...DEFAULTS };
    for (const k of Object.keys(DEFAULTS)) {
      if (!q.has(k)) continue;
      const v = q.get(k);
      if (typeof DEFAULTS[k] === 'number') { const n = Number(v); o[k] = Number.isFinite(n) ? n : DEFAULTS[k]; }
      else o[k] = v;
    }
    if (!LAYOUTS[o.layout]) o.layout = DEFAULTS.layout;
    return o;
  }

  function toQuery(o) {
    const q = new URLSearchParams();
    for (const k of Object.keys(DEFAULTS)) if (o[k] !== DEFAULTS[k]) q.set(k, o[k]);
    return q.toString();
  }

  function hexToRgb(hex) {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
    const n = parseInt(m ? m[1] : '3dffb5', 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  // ------------------------------------------------------------------ DOM helpers
  const el = (tag, cls, html) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  };

  const BODY = 'M60 5 C26 5 9 32 9 74 V118 C9 160 30 185 60 185 C90 185 111 160 111 118 V74 C111 32 94 5 60 5 Z';

  function mouseSvg() {
    return `
    <svg viewBox="-4 -14 128 214" xmlns="http://www.w3.org/2000/svg">
      <defs><clipPath id="skbody"><path d="${BODY}"/></clipPath></defs>
      <path class="m-body" d="${BODY}"/>
      <g clip-path="url(#skbody)">
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

  // ------------------------------------------------------------------ renderer
  function mount(root, o) {
    root.innerHTML = '';
    root.dataset.theme = o.theme;
    const unit = BASE * o.scale;
    const gap = o.gap * o.scale;
    const step = unit + gap;
    const [r, g, b] = hexToRgb(o.accent);
    const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    const s = root.style;
    s.setProperty('--u', unit + 'px');
    s.setProperty('--gap', gap + 'px');
    s.setProperty('--r', o.radius * o.scale + 'px');
    s.setProperty('--accent', o.accent);
    s.setProperty('--accent-rgb', `${r},${g},${b}`);
    s.setProperty('--accent-ink', lum > 0.55 ? '#07110c' : '#ffffff');
    s.setProperty('--alpha', String(o.alpha));
    s.setProperty('--glow', String(o.glow));
    s.setProperty('--fs', unit * o.label + 'px');
    s.setProperty('--font', `"${o.font}", "Segoe UI", system-ui, sans-serif`);

    const layout = LAYOUTS[o.layout];
    const wrap = el('div', 'wrap');
    wrap.dataset.side = o.side;
    const board = el('div', 'board');
    const keys = new Map();
    let maxX = 0, maxY = 0;
    for (const k of layout.keys) {
      const n = el('div', 'key', `<span>${k.l}</span>`);
      if (k.l.length > 1 && k.l.length <= 6 && !/[▲-◀]/.test(k.l)) n.classList.add('small');
      n.style.left = k.x * step + 'px';
      n.style.top = k.y * step + 'px';
      n.style.width = k.w * step - gap + 'px';
      n.style.height = unit + 'px';
      board.appendChild(n);
      keys.set(k.c, n);
      maxX = Math.max(maxX, k.x + k.w);
      maxY = Math.max(maxY, k.y + 1);
    }
    board.style.width = Math.max(0, maxX * step - gap) + 'px';
    board.style.height = Math.max(0, maxY * step - gap) + 'px';
    if (layout.keys.length) wrap.appendChild(board);

    let mouseEl = null, tiltEl = null, cpsEl = null;
    const parts = {};
    if (o.mouse) {
      mouseEl = el('div', 'mouse');
      tiltEl = el('div', 'mouse-tilt', mouseSvg());
      mouseEl.appendChild(tiltEl);
      if (o.cps) { cpsEl = el('div', 'cps', '<span data-c="l">L 0</span><span data-c="r">R 0</span>'); mouseEl.appendChild(cpsEl); }
      tiltEl.querySelectorAll('[data-b]').forEach((n) => { parts[n.dataset.b] = n; });
      wrap.appendChild(mouseEl);
    }
    root.appendChild(wrap);

    // ---- state changes
    const pulse = (node) => {
      const p = el('i', 'pulse');
      node.appendChild(p);
      p.addEventListener('animationend', () => p.remove());
    };
    const setKey = (code, down) => {
      const n = keys.get(code);
      if (!n) return;
      if (down) { if (!n.classList.contains('down')) pulse(n); n.classList.add('down'); }
      else n.classList.remove('down');
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
      const cls = dir > 0 ? 'sc-up' : 'sc-dn';
      w.classList.remove('sc-up', 'sc-dn');
      void w.getBoundingClientRect(); // restart the CSS animation
      w.classList.add(cls);
      const arrow = tiltEl.querySelector(dir > 0 ? '.m-arrow.up' : '.m-arrow.dn');
      arrow.classList.add('on');
      clearTimeout(arrow._t);
      arrow._t = setTimeout(() => arrow.classList.remove('on'), 160);
    };
    let vx = 0, vy = 0;
    const move = (dx, dy) => { vx += dx; vy += dy; };
    const releaseAll = () => {
      keys.forEach((n) => n.classList.remove('down'));
      Object.values(parts).forEach((n) => n.classList.remove('on'));
    };

    // ---- animation loop (mouse tilt + CPS counters)
    let raf = 0, lastCps = 0;
    const loop = (t) => {
      if (tiltEl && o.tilt) {
        vx *= 0.88; vy *= 0.88;
        const cx = Math.max(-40, Math.min(40, vx)), cy = Math.max(-40, Math.min(40, vy));
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

    const rect = wrap.getBoundingClientRect();
    return {
      codes: [...keys.keys()],
      size: { w: Math.ceil(rect.width), h: Math.ceil(rect.height) },
      setKey, setBtn, wheel, move, releaseAll,
      handle(ev) {
        if (ev.t === 'k') setKey(ev.c, ev.d);
        else if (ev.t === 'm') setBtn(ev.b, ev.d);
        else if (ev.t === 'w' && !ev.h) wheel(ev.v);
        else if (ev.t === 'mv') move(ev.x, ev.y);
        else if (ev.t === 's') { releaseAll(); ev.k.forEach((c) => setKey(c, 1)); ev.m.forEach((m) => setBtn(m, 1)); }
      },
      keyCodes: [...keys.keys()],
      destroy() { cancelAnimationFrame(raf); root.innerHTML = ''; },
    };
  }

  // ------------------------------------------------------------------ live connection
  function connect(ctrl, onStatus) {
    // Only ask the server for the keys this layout actually shows: everything else you type stays private.
    const url = '/events' + (ctrl.codes.length ? '?codes=' + ctrl.codes.join(',') : '?codes=_none_');
    const es = new EventSource(url);
    es.onopen = () => onStatus && onStatus(true);
    es.onerror = () => { onStatus && onStatus(false); ctrl.releaseAll(); };
    es.onmessage = (e) => { try { ctrl.handle(JSON.parse(e.data)); } catch (_) { /* ignore */ } };
    return { close: () => es.close() };
  }

  // fake input so you can preview themes without touching the keyboard
  function demo(ctrl) {
    let on = true;
    const codes = ctrl.keyCodes;
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

  window.SleekKeys = { BASE, LAYOUTS, DEFAULTS, parse, toQuery, mount, connect, demo };
})();
