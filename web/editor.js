/* SleekKeys editor: appearance, drag & drop layout maker, profiles, general. */
(() => {
  'use strict';
  const SK = window.SleekKeys;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const r3 = (v) => Math.round(v * 1000) / 1000;

  // ------------------------------------------------------------------ state
  let cfg = SK.defaultConfig();
  let editing = cfg.active;
  let info = {};
  let tab = 'appearance';
  let sel = -1;            // selected key index, -1 none
  let selMouse = false;
  let capture = null;      // null | 'add' | 'assign'
  let demoOn = false, previewReady = false, saveTimer = 0;
  const undoStack = [], redoStack = [];

  const P = () => cfg.profiles[editing];
  const post = (path, body) => fetch(path, {
    method: 'POST', headers: { 'X-SleekKeys': '1', 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body),
  }).then((r) => r.json());

  // ------------------------------------------------------------------ persistence
  function saved() {
    $('saved').classList.add('show');
    clearTimeout(saved.t);
    saved.t = setTimeout(() => $('saved').classList.remove('show'), 1400);
  }
  function save() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      try { const r = await post('/api/config', cfg); if (r.ok) saved(); else toast('Could not save: ' + r.message); }
      catch (_) { toast('Could not reach SleekKeys - is it running?'); }
    }, 350);
  }
  function pushPreview() {
    if (!previewReady) return;
    $('preview').contentWindow.postMessage({ type: 'profile', profile: P(), demo: demoOn }, location.origin);
  }
  function changed(opts = {}) {
    if (!opts.noSave) save();
    pushPreview();
    if (opts.canvas !== false && tab === 'layout') renderCanvas();
    if (opts.inspector !== false && tab === 'layout') renderInspector();
  }

  // ------------------------------------------------------------------ small UI helpers
  function toast(t) {
    $('toast').textContent = t; $('toast').classList.add('show');
    clearTimeout(toast.t); toast.t = setTimeout(() => $('toast').classList.remove('show'), 1800);
  }
  function modal(html, onMount) {
    $('dlg').innerHTML = html; $('modal').classList.add('on');
    const close = () => $('modal').classList.remove('on');
    $('modal').onclick = (e) => { if (e.target === $('modal')) close(); };
    onMount && onMount(close);
    return close;
  }
  function askText(title, value, okLabel = 'OK') {
    return new Promise((resolve) => {
      const close = modal(`<h3>${esc(title)}</h3><input type="text" id="askInput" maxlength="40"><div class="btnrow"><button class="btn" id="askNo">Cancel</button><button class="btn primary" id="askYes">${esc(okLabel)}</button></div>`, (c) => {
        const inp = $('askInput'); inp.value = value || ''; inp.focus(); inp.select();
        const done = (v) => { c(); resolve(v); };
        $('askNo').onclick = () => done(null);
        $('askYes').onclick = () => done(inp.value.trim() || null);
        inp.onkeydown = (e) => { if (e.key === 'Enter') done(inp.value.trim() || null); if (e.key === 'Escape') done(null); };
      });
      void close;
    });
  }
  function confirmBox(title, text, okLabel = 'Yes') {
    return new Promise((resolve) => {
      modal(`<h3>${esc(title)}</h3><p style="color:#b6bed4">${esc(text)}</p><div class="btnrow"><button class="btn" id="cfNo">Cancel</button><button class="btn primary" id="cfYes">${esc(okLabel)}</button></div>`, (c) => {
        $('cfNo').onclick = () => { c(); resolve(false); };
        $('cfYes').onclick = () => { c(); resolve(true); };
      });
    });
  }
  const bindSwitch = (id, get, set) => {
    const n = $(id);
    const paint = () => n.classList.toggle('on', !!get());
    n.onclick = async () => { await set(!get()); paint(); };
    paint();
    return paint;
  };

  // ------------------------------------------------------------------ tabs
  function setTab(name) {
    tab = name;
    document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('on', t.dataset.tab === name));
    document.querySelectorAll('section.page').forEach((s) => s.classList.toggle('on', s.id === 'page-' + name));
    capture = null;
    if (name === 'layout') { renderCanvas(); renderInspector(); }
    if (name === 'profiles') renderProfiles();
    if (name === 'general') renderGeneral();
  }
  $('tabs').addEventListener('click', (e) => { const t = e.target.closest('.tab'); if (t) setTab(t.dataset.tab); });

  // ------------------------------------------------------------------ profile selector
  function renderProfileSelect() {
    const s = $('profileSelect');
    s.innerHTML = '';
    for (const name of Object.keys(cfg.profiles)) s.add(new Option((name === cfg.active ? '★ ' : '') + name, name));
    s.value = editing;
  }
  $('profileSelect').onchange = () => { editing = $('profileSelect').value; sel = -1; selMouse = false; refreshAll(); };

  function refreshAll() {
    $('layName').value = layout().name;
    renderProfileSelect();
    syncAppearance();
    pushPreview();
    if (tab === 'layout') { renderCanvas(); renderInspector(); }
    if (tab === 'profiles') renderProfiles();
    if (tab === 'general') renderGeneral();
  }

  // ------------------------------------------------------------------ APPEARANCE
  const SLIDERS = [
    ['scale', 'Overall scale', 0.3, 3, 0.05, (v) => v.toFixed(2) + '×'],
    ['gap', 'Key spacing', 0, 24, 1, (v) => v + 'px'],
    ['radius', 'Corner radius', 0, 40, 1, (v) => v + 'px'],
    ['alpha', 'Key opacity', 0.05, 1, 0.01, (v) => Math.round(v * 100) + '%'],
    ['glow', 'Glow strength', 0, 2, 0.05, (v) => Math.round(v * 100) + '%'],
    ['label', 'Label size', 0.15, 0.6, 0.01, (v) => Math.round(v * 100) + '%'],
  ];
  const SWATCHES = ['#3dffb5', '#4cc9ff', '#a66bff', '#ff5fa2', '#ffb347', '#ff5555', '#ffffff'];

  function buildAppearance() {
    SLIDERS.forEach(([key, label, min, max, step]) => {
      const row = document.createElement('div');
      row.className = 'field';
      row.innerHTML = `<label for="s-${key}">${label}</label><input type="range" id="s-${key}" min="${min}" max="${max}" step="${step}"><output id="o-${key}"></output>`;
      $('sliders').appendChild(row);
      row.querySelector('input').addEventListener('input', (e) => { P().opts[key] = Number(e.target.value); syncAppearance(); changed({ inspector: false }); });
    });
    SWATCHES.forEach((c) => {
      const s = document.createElement('div');
      s.className = 'sw'; s.style.background = c; s.dataset.c = c;
      s.onclick = () => { P().opts.accent = c; syncAppearance(); changed({ inspector: false }); };
      $('swatches').appendChild(s);
    });
    const bind = (id, key) => $(id).addEventListener('input', () => { P().opts[key] = $(id).value; syncAppearance(); changed({ inspector: false }); });
    bind('theme', 'theme'); bind('accent', 'accent'); bind('font', 'font');
    $('t-tilt').onclick = () => { P().opts.tilt = P().opts.tilt ? 0 : 1; syncAppearance(); changed({ inspector: false }); };
    $('t-cps').onclick = () => { P().opts.cps = P().opts.cps ? 0 : 1; syncAppearance(); changed({ inspector: false }); };
    $('bgmode').addEventListener('input', () => {
      const m = $('bgmode').value;
      P().opts.bg = m === 'custom' ? $('bgcolor').value : m;
      syncAppearance(); changed({ inspector: false });
    });
    $('bgcolor').addEventListener('input', () => { P().opts.bg = $('bgcolor').value; changed({ inspector: false }); });
  }

  function syncAppearance() {
    const o = P().opts;
    $('theme').value = o.theme; $('accent').value = o.accent; $('font').value = o.font;
    SLIDERS.forEach(([key, , , , , fmt]) => { $('s-' + key).value = o[key]; $('o-' + key).textContent = fmt(Number(o[key])); });
    document.querySelectorAll('.sw').forEach((s) => s.classList.toggle('on', s.dataset.c.toLowerCase() === o.accent.toLowerCase()));
    $('t-tilt').classList.toggle('on', !!o.tilt);
    $('t-cps').classList.toggle('on', !!o.cps);
    const preset = o.bg === 'transparent' || o.bg === 'green';
    $('bgmode').value = preset ? o.bg : 'custom';
    $('bgcolor-row').style.display = preset ? 'none' : '';
    if (!preset) $('bgcolor').value = o.bg;
  }

  $('demo').onclick = () => {
    demoOn = !demoOn;
    $('demo').textContent = demoOn ? '■ Stop demo' : '▶ Demo presses';
    pushPreview();
  };

  // ------------------------------------------------------------------ LAYOUT MAKER
  const layout = () => P().layout;
  const snapVal = () => Number($('snap').value);
  const snap = (v) => { const s = snapVal(); return r3(Math.max(0, s ? Math.round(v / s) * s : v)); };
  const zoom = () => Number($('zoom').value);

  function snapshot() {
    undoStack.push(JSON.stringify(layout()));
    if (undoStack.length > 60) undoStack.shift();
    redoStack.length = 0;
  }
  function restore(json) {
    P().layout = SK.normalizeLayout(JSON.parse(json));
    sel = -1; selMouse = false;
    changed();
  }
  function undo() { if (!undoStack.length) return; redoStack.push(JSON.stringify(layout())); restore(undoStack.pop()); }
  function redo() { if (!redoStack.length) return; undoStack.push(JSON.stringify(layout())); restore(redoStack.pop()); }
  $('undo').onclick = undo; $('redo').onclick = redo;

  function renderCanvas() {
    const o = P().opts, L = layout();
    const eo = { ...o, scale: o.scale * zoom() };
    if (document.activeElement !== $('layName')) $('layName').value = L.name;
    const c = $('canvas');
    c.innerHTML = '';
    SK.applyTheme(c, eo);
    const unit = SK.BASE * eo.scale, gap = eo.gap * eo.scale, step = unit + gap;
    c.style.setProperty('--grid', step + 'px');
    const b = SK.bounds(L, false);
    const board = document.createElement('div');
    board.className = 'board';
    board.style.width = (Math.max(b.w, 14) + 3) * step + 'px';
    board.style.height = (Math.max(b.h, 5) + 2) * step + 'px';
    c.appendChild(board);

    L.keys.forEach((k, i) => {
      const n = SK.keyNode(k, step, gap, unit);
      n.dataset.i = i;
      if (i === sel) n.classList.add('sel');
      const rz = document.createElement('i');
      rz.className = 'rz';
      n.appendChild(rz);
      n.addEventListener('pointerdown', (e) => {
        if (e.target === rz) return startResize(e, n, k, step, gap);
        select(i, false);
        startDrag(e, n, k, step, 'key');
      });
      board.appendChild(n);
    });

    if (L.mouse.show) {
      const m = document.createElement('div');
      m.className = 'mouse' + (selMouse ? ' sel' : '');
      m.style.left = L.mouse.x * step + 'px';
      m.style.top = L.mouse.y * step + 'px';
      m.style.width = SK.MOUSE_W * L.mouse.scale * step + 'px';
      m.innerHTML = '<div class="mouse-tilt">' + SK.mouseSvg('e') + '</div>';
      m.addEventListener('pointerdown', (e) => { select(-1, true); startDrag(e, m, L.mouse, step, 'mouse'); });
      board.appendChild(m);
    }
    board.addEventListener('pointerdown', (e) => { if (e.target === board) select(-1, false); });
  }

  function select(i, mouse) {
    const same = i === sel && mouse === selMouse;
    sel = i; selMouse = mouse;
    document.querySelectorAll('#canvas .key').forEach((n) => n.classList.toggle('sel', Number(n.dataset.i) === sel));
    const m = document.querySelector('#canvas .mouse');
    if (m) m.classList.toggle('sel', selMouse);
    if (!same) renderInspector();
  }

  function startDrag(e, node, item, step, kind) {
    e.preventDefault();
    node.setPointerCapture(e.pointerId);
    const sx = e.clientX, sy = e.clientY, ox = item.x, oy = item.y;
    let moved = false;
    node.classList.add('dragging');
    const move = (ev) => {
      const dx = ev.clientX - sx, dy = ev.clientY - sy;
      if (!moved && Math.abs(dx) + Math.abs(dy) < 3) return;
      if (!moved) { snapshot(); moved = true; }
      item.x = snap(ox + dx / step); item.y = snap(oy + dy / step);
      node.style.left = item.x * step + 'px'; node.style.top = item.y * step + 'px';
      fillInspectorPos();
    };
    const up = () => {
      node.removeEventListener('pointermove', move);
      node.removeEventListener('pointerup', up);
      node.classList.remove('dragging');
      if (moved) changed({ inspector: false });
    };
    node.addEventListener('pointermove', move);
    node.addEventListener('pointerup', up);
  }

  function startResize(e, node, k, step, gap) {
    e.preventDefault(); e.stopPropagation();
    node.setPointerCapture(e.pointerId);
    select(Number(node.dataset.i), false);
    const sx = e.clientX, sy = e.clientY, ow = k.w, oh = k.h;
    let moved = false;
    const move = (ev) => {
      if (!moved) { snapshot(); moved = true; }
      k.w = Math.max(0.5, snap(ow + (ev.clientX - sx) / step)); k.h = Math.max(0.5, snap(oh + (ev.clientY - sy) / step));
      node.style.width = k.w * step - gap + 'px'; node.style.height = k.h * step - gap + 'px';
      fillInspectorPos();
    };
    const up = () => {
      node.removeEventListener('pointermove', move); node.removeEventListener('pointerup', up);
      if (moved) changed({ inspector: false });
    };
    node.addEventListener('pointermove', move); node.addEventListener('pointerup', up);
  }

  // ---- inspector
  function fillInspectorPos() {
    const item = selMouse ? layout().mouse : layout().keys[sel];
    if (!item) return;
    for (const f of ['x', 'y', 'w', 'h']) { const el = $('f-' + f); if (el && item[f] !== undefined) el.value = item[f]; }
  }

  function nextFreeSpot() {
    const L = layout();
    const bottom = L.keys.reduce((m, k) => Math.max(m, k.y + k.h), 0);
    return { x: 0, y: bottom + (L.keys.length ? 0.5 : 0) };
  }
  function addKey(code, label, w) {
    snapshot();
    const spot = nextFreeSpot();
    layout().keys.push({ c: code, l: label, x: spot.x, y: spot.y, w, h: 1 });
    sel = layout().keys.length - 1; selMouse = false;
    changed();
  }

  function numField(id, label, value, step = 0.25, min = 0) {
    return `<div><label class="lbl" for="${id}">${label}</label><input type="number" id="${id}" value="${value}" step="${step}" min="${min}"></div>`;
  }

  function renderInspector() {
    const box = $('inspector');
    const L = layout();
    if (capture) {
      box.innerHTML = `<h3>${capture === 'add' ? 'Add keys by pressing them' : 'Assign a key'}</h3>
        <div class="capture">Press the key on your keyboard&hellip;<br><span class="hint">${capture === 'add' ? 'Keep pressing to add more.' : ''} Esc to stop.</span></div>
        <button class="btn" id="stopCapture">Done</button>`;
      $('stopCapture').onclick = () => { capture = null; renderInspector(); };
      return;
    }
    if (selMouse && L.mouse.show) {
      box.innerHTML = `<h3>Mouse</h3>
        <div class="grid2">${numField('f-x', 'X (key units)', L.mouse.x)}${numField('f-y', 'Y (key units)', L.mouse.y)}</div>
        <div class="field two" style="grid-template-columns:70px 1fr"><label>Size</label><input type="range" id="f-ms" min="0.4" max="3" step="0.05" value="${L.mouse.scale}"></div>
        <div class="btnrow"><button class="btn danger" id="hideMouse">Remove mouse</button></div>`;
      $('f-x').oninput = (e) => { snapshot(); L.mouse.x = r3(Math.max(0, Number(e.target.value) || 0)); changed({ inspector: false }); };
      $('f-y').oninput = (e) => { snapshot(); L.mouse.y = r3(Math.max(0, Number(e.target.value) || 0)); changed({ inspector: false }); };
      $('f-ms').oninput = (e) => { L.mouse.scale = Number(e.target.value); changed({ inspector: false }); };
      $('f-ms').onpointerdown = () => snapshot();
      $('hideMouse').onclick = () => { snapshot(); L.mouse.show = false; selMouse = false; changed(); };
      return;
    }
    const k = sel >= 0 ? L.keys[sel] : null;
    if (k) {
      const codes = SK.CATALOG.map((c) => c[0]).filter((c, i, a) => a.indexOf(c) === i);
      if (!codes.includes(k.c)) codes.unshift(k.c);
      box.innerHTML = `<h3>Key</h3>
        <div class="grid2"><div><label class="lbl" for="f-l">Label</label><input type="text" id="f-l" maxlength="8"></div>
        <div><label class="lbl" for="f-c">Key</label><select id="f-c"></select></div></div>
        <div class="grid2">${numField('f-x', 'X', k.x)}${numField('f-y', 'Y', k.y)}${numField('f-w', 'Width', k.w, 0.25, 0.5)}${numField('f-h', 'Height', k.h, 0.25, 0.5)}</div>
        <div class="btnrow" style="margin-bottom:10px"><button class="btn" id="assign">Assign by pressing a key</button></div>
        <div class="btnrow"><button class="btn small" id="dup">Duplicate</button><button class="btn small danger" id="del">Delete</button></div>
        <p class="hint" style="margin-top:14px">Drag the key to move it, drag the green corner to resize. Arrow keys nudge. Del removes.</p>`;
      $('f-l').value = k.l;
      const sc = $('f-c');
      codes.forEach((c) => sc.add(new Option(c, c)));
      sc.value = k.c;
      $('f-l').oninput = (e) => { snapshot(); k.l = e.target.value.slice(0, 8); changed({ inspector: false }); };
      sc.onchange = (e) => {
        snapshot();
        const old = SK.CATALOG_BY_CODE[k.c]; const nu = SK.CATALOG_BY_CODE[e.target.value];
        if (nu && (!k.l || (old && k.l === old[1]))) k.l = nu[1];
        k.c = e.target.value; changed();
      };
      for (const f of ['x', 'y', 'w', 'h']) {
        $('f-' + f).oninput = (e) => {
          const v = Number(e.target.value);
          if (!Number.isFinite(v)) return;
          snapshot(); k[f] = r3(Math.max(f === 'w' || f === 'h' ? 0.5 : 0, v)); changed({ inspector: false });
        };
      }
      $('assign').onclick = () => { capture = 'assign'; renderInspector(); };
      $('dup').onclick = () => { snapshot(); L.keys.push({ ...k, x: r3(k.x + 0.5), y: r3(k.y + 0.5) }); sel = L.keys.length - 1; changed(); };
      $('del').onclick = () => deleteSelected();
      return;
    }
    // nothing selected: add keys
    box.innerHTML = `<h3>Add keys</h3>
      <div class="btnrow" style="margin-bottom:10px"><button class="btn primary" id="addPress">+ Add by pressing a key</button></div>
      <input type="search" id="catSearch" placeholder="Or search: A, shift, F5, numpad&hellip;">
      <div class="catalog" id="catalog"></div>
      <h3>Mouse</h3>
      <div class="btnrow">${L.mouse.show ? '<button class="btn small" id="selMouse">Select mouse</button>' : '<button class="btn small primary" id="showMouse">+ Add mouse</button>'}</div>
      <p class="hint" style="margin-top:16px">Click a key on the canvas to edit it. Everything here is the exact size it will have in OBS (use Zoom to inspect).</p>`;
    $('addPress').onclick = () => { capture = 'add'; renderInspector(); };
    const fill = (q) => {
      const cat = $('catalog'); cat.innerHTML = '';
      const needle = q.trim().toLowerCase();
      SK.CATALOG.filter((c, i, a) => a.findIndex((x) => x[0] === c[0]) === i)
        .filter((c) => !needle || c[0].toLowerCase().includes(needle) || c[1].toLowerCase().includes(needle))
        .forEach((c) => {
          const chip = document.createElement('span');
          chip.className = 'chip'; chip.textContent = c[1] || 'SPACE'; chip.title = c[0];
          chip.onclick = () => addKey(c[0], c[1], c[2]);
          cat.appendChild(chip);
        });
    };
    fill('');
    $('catSearch').oninput = (e) => fill(e.target.value);
    if ($('selMouse')) $('selMouse').onclick = () => select(-1, true);
    if ($('showMouse')) $('showMouse').onclick = () => { snapshot(); L.mouse.show = true; selMouse = true; changed(); };
  }

  function deleteSelected() {
    if (sel < 0) return;
    snapshot(); layout().keys.splice(sel, 1); sel = -1; changed();
  }

  // ---- presets / name / export / import
  function buildLayoutToolbar() {
    for (const [id, p] of Object.entries(SK.PRESETS)) $('presetSel').add(new Option(p.name, id));
    $('loadPreset').onclick = async () => {
      if (!(await confirmBox('Load preset?', 'This replaces the current layout of this profile (you can undo).', 'Load'))) return;
      snapshot();
      const keepName = layout().name;
      P().layout = SK.normalizeLayout(SK.makeLayout($('presetSel').value));
      P().layout.name = keepName;
      sel = -1; selMouse = false; changed();
    };
    $('layName').oninput = (e) => { layout().name = e.target.value.slice(0, 40); save(); };
    $('zoom').oninput = () => renderCanvas();
    $('snap').onchange = () => renderCanvas();
    $('exportBtn').onclick = () => {
      modal(`<h3>Export layout</h3><p class="hint">Copy this text to share your layout. Friends can paste it with Import.</p><textarea id="exp" readonly></textarea><div class="btnrow"><button class="btn" id="expClose">Close</button><button class="btn primary" id="expCopy">Copy</button></div>`, (c) => {
        $('exp').value = JSON.stringify(layout(), null, 1);
        $('expClose').onclick = c;
        $('expCopy').onclick = async () => { try { await navigator.clipboard.writeText($('exp').value); } catch (_) { $('exp').select(); document.execCommand('copy'); } toast('Layout copied'); };
      });
    };
    $('importBtn').onclick = () => {
      modal(`<h3>Import layout</h3><p class="hint">Paste a layout exported from SleekKeys. It replaces this profile&rsquo;s layout (you can undo).</p><textarea id="imp"></textarea><div class="btnrow"><button class="btn" id="impNo">Cancel</button><button class="btn primary" id="impYes">Import</button></div>`, (c) => {
        $('impNo').onclick = c;
        $('impYes').onclick = () => {
          try {
            const parsed = JSON.parse($('imp').value);
            if (!parsed || !Array.isArray(parsed.keys)) throw new Error('not a layout');
            snapshot(); P().layout = SK.normalizeLayout(parsed); sel = -1; selMouse = false; c(); changed(); toast('Layout imported');
          } catch (_) { toast('That is not a valid layout'); }
        };
      });
    };
  }

  // keyboard handling for the layout tab (nudge / delete / undo / capture)
  addEventListener('keydown', (e) => {
    if (tab !== 'layout') return;
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement && document.activeElement.tagName);
    if (capture) {
      e.preventDefault(); e.stopPropagation();
      if (e.code === 'Escape') { capture = null; renderInspector(); return; }
      const cat = SK.CATALOG_BY_CODE[e.code];
      const label = cat ? cat[1] : (e.key.length === 1 ? e.key.toUpperCase() : e.code.slice(0, 6).toUpperCase());
      if (capture === 'add') { addKey(e.code, label, cat ? cat[2] : 1); capture = 'add'; renderInspector(); }
      else if (sel >= 0) {
        snapshot(); const k = layout().keys[sel]; const old = SK.CATALOG_BY_CODE[k.c];
        if (!k.l || (old && k.l === old[1])) k.l = label;
        k.c = e.code; capture = null; changed();
      }
      return;
    }
    if (e.ctrlKey && e.code === 'KeyZ') { e.preventDefault(); undo(); return; }
    if (e.ctrlKey && (e.code === 'KeyY' || (e.shiftKey && e.code === 'KeyZ'))) { e.preventDefault(); redo(); return; }
    if (typing) return;
    if (e.code === 'Delete' || e.code === 'Backspace') { e.preventDefault(); deleteSelected(); return; }
    if (e.ctrlKey && e.code === 'KeyD' && sel >= 0) {
      e.preventDefault(); const k = layout().keys[sel];
      snapshot(); layout().keys.push({ ...k, x: r3(k.x + 0.5), y: r3(k.y + 0.5) }); sel = layout().keys.length - 1; changed(); return;
    }
    const step = snapVal() || 0.25;
    const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.code];
    if (d) {
      const item = selMouse ? layout().mouse : layout().keys[sel];
      if (!item) return;
      e.preventDefault(); snapshot();
      item.x = r3(Math.max(0, item.x + d[0])); item.y = r3(Math.max(0, item.y + d[1])); changed();
    }
  }, true);

  // ------------------------------------------------------------------ PROFILES
  const profileUrl = (name) => `${location.origin}/overlay` + (name === cfg.active ? '' : '?profile=' + encodeURIComponent(name));

  function uniqueName(base) {
    let n = base, i = 2;
    while (cfg.profiles[n]) n = `${base} ${i++}`;
    return n;
  }

  function renderProfiles() {
    const wrap = $('cards');
    wrap.innerHTML = '';
    for (const [name, p] of Object.entries(cfg.profiles)) {
      const card = document.createElement('div');
      card.className = 'card' + (name === editing ? ' cur' : '');
      card.innerHTML = `<h3><span class="n"></span>${name === cfg.active ? '<span class="badge mint">OBS DEFAULT</span>' : ''}${name === editing ? '<span class="badge">EDITING</span>' : ''}</h3>
        <p>${esc(p.layout.name)} &middot; ${p.layout.keys.length} keys${p.layout.mouse.show ? ' + mouse' : ''} &middot; ${esc(p.opts.theme)} theme</p>
        <div class="btnrow"><button class="btn small primary" data-a="edit">Edit</button>
        ${name !== cfg.active ? '<button class="btn small" data-a="default">Use in OBS</button>' : ''}
        <button class="btn small" data-a="rename">Rename</button><button class="btn small" data-a="dup">Duplicate</button>
        <button class="btn small" data-a="url">Copy URL</button>
        ${Object.keys(cfg.profiles).length > 1 ? '<button class="btn small danger" data-a="del">Delete</button>' : ''}</div>`;
      card.querySelector('.n').textContent = name;
      card.querySelector('.btnrow').onclick = async (e) => {
        const a = e.target.dataset.a;
        if (!a) return;
        if (a === 'edit') { editing = name; sel = -1; refreshAll(); }
        else if (a === 'default') { cfg.active = name; changed({ canvas: false }); renderProfileSelect(); renderProfiles(); toast(`"${name}" is now your OBS overlay`); }
        else if (a === 'dup') { const nn = uniqueName(name + ' copy'); cfg.profiles[nn] = JSON.parse(JSON.stringify(p)); editing = nn; save(); refreshAll(); }
        else if (a === 'url') { try { await navigator.clipboard.writeText(profileUrl(name)); toast('URL copied'); } catch (_) { toast(profileUrl(name)); } }
        else if (a === 'rename') {
          const nn = await askText('Rename profile', name, 'Rename');
          if (!nn || nn === name) return;
          if (cfg.profiles[nn]) return toast('That name is already used');
          const next = {};
          for (const [k, v] of Object.entries(cfg.profiles)) next[k === name ? nn : k] = v;
          cfg.profiles = next;
          if (cfg.active === name) cfg.active = nn;
          if (editing === name) editing = nn;
          save(); refreshAll();
        } else if (a === 'del') {
          if (!(await confirmBox('Delete profile?', `"${name}" will be removed. Overlays using its URL will show your default profile instead.`, 'Delete'))) return;
          delete cfg.profiles[name];
          if (cfg.active === name) cfg.active = Object.keys(cfg.profiles)[0];
          if (editing === name) editing = cfg.active;
          save(); refreshAll();
        }
      };
      wrap.appendChild(card);
    }
  }
  $('newProfile').onclick = async () => {
    const name = await askText('New profile name', uniqueName('Profile'), 'Create');
    if (!name) return;
    if (cfg.profiles[name]) return toast('That name is already used');
    cfg.profiles[name] = { opts: { ...SK.DEFAULT_OPTS }, layout: SK.makeLayout('gamer') };
    editing = name; save(); refreshAll();
    setTab('layout');
    toast('Profile created - build your layout!');
  };

  // ------------------------------------------------------------------ GENERAL
  function renderGeneral() {
    $('obsUrl').value = `${location.origin}/overlay`;
    $('size').textContent = sourceSize();
    $('ver').textContent = 'v' + (info.version || '');
    $('dataDir').textContent = info.dataDir || '';
    bindSwitch('t-autostart', () => info.autostart, async (v) => { const r = await post('/api/autostart', { enabled: v }); info.autostart = r.autostart; toast(r.autostart ? 'SleekKeys will start with Windows' : 'Autostart off'); });
    bindSwitch('t-pause', () => info.paused, async () => { const r = await post('/api/pause'); info.paused = r.paused; toast(r.paused ? 'Overlay paused' : 'Overlay resumed'); });
  }
  $('copyUrl').onclick = async () => {
    try { await navigator.clipboard.writeText($('obsUrl').value); } catch (_) { $('obsUrl').select(); document.execCommand('copy'); }
    toast('Copied - paste it into an OBS Browser Source');
  };
  $('quit').onclick = async () => {
    if (!(await confirmBox('Quit SleekKeys?', 'The overlay in OBS will stop reacting until you start SleekKeys again.', 'Quit'))) return;
    try { await post('/api/quit'); } catch (_) {}
    $('status').textContent = 'SleekKeys has stopped.'; $('dot').classList.remove('ok');
    setTimeout(() => window.close(), 400);
  };

  // ------------------------------------------------------------------ messages from the preview iframe
  addEventListener('message', (e) => {
    if (e.origin !== location.origin || !e.data) return;
    if (e.data.type === 'ready') { previewReady = true; pushPreview(); }
    else if (e.data.type === 'status') {
      $('dot').classList.toggle('ok', e.data.ok);
      $('status').textContent = e.data.ok ? 'Listening' : 'Not connected';
    }
  });

  // size of the OBS browser source for the default profile (board + the overlay's 14px padding on each side)
  function sourceSize() {
    const p = cfg.profiles[cfg.active];
    const b = SK.bounds(p.layout, p.opts.cps);
    const step = (SK.BASE + p.opts.gap) * p.opts.scale;
    return `${Math.ceil(b.w * step - p.opts.gap * p.opts.scale) + 28} × ${Math.ceil(b.h * step - p.opts.gap * p.opts.scale) + 28}`;
  }

  // ------------------------------------------------------------------ boot
  async function boot() {
    buildAppearance();
    buildLayoutToolbar();
    try { info = await (await fetch('/api/info')).json(); } catch (_) {}
    try { cfg = SK.normalizeConfig(await (await fetch('/api/config', { cache: 'no-store' })).json()); } catch (_) { cfg = SK.defaultConfig(); }
    editing = cfg.active;
    $('layName').value = layout().name;
    renderProfileSelect();
    syncAppearance();
    pushPreview();
    $('layName').value = layout().name;
  }
  boot();
})();
