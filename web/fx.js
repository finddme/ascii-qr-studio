'use strict';
// Visual effects only. Nothing here affects conversion; app.js calls window.fx when present.
(() => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const P = ['#1f5c45', '#2b9a8a', '#a8276c', '#eba6cb', '#c99230', '#a3c7d2', '#a5392c', '#b29ad0', '#8db43c'];
  const BEAD = ['#fbf4e2', '#efe4cc', '#fffaf0'];
  const seeded = s => () => (s = (s * 1664525 + 1013904223) >>> 0) / 4294967296;
  const pick = (r, a) => a[Math.floor(r() * a.length)];
  const mix = (a, b, t) => {
    const p = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
    const x = p(a), y = p(b);
    return `rgb(${x.map((v, i) => Math.round(v + (y[i] - v) * t)).join(',')})`;
  };

  /* ── decor field: scattered pixel objects on a square grid ── */
  const field = document.createElement('canvas');
  field.className = 'field';
  field.setAttribute('aria-hidden', 'true');
  document.body.prepend(field);
  const fx = field.getContext('2d');
  let items = [], u = 14, dpr = 1, fieldTimer = 0;
  const SIZES = { sq: [1, 1], dots: [4, 1], bar: [1, 7], checker: [4, 4], rings: [4, 4], stairs: [6, 4], frame: [2, 2], diamond: [2, 2], pair: [2, 2] };
  const TYPES = ['sq', 'sq', 'sq', 'sq', 'sq', 'sq', 'dots', 'bar', 'checker', 'rings', 'stairs', 'frame', 'diamond', 'pair'];

  function buildField() {
    dpr = Math.min(2, devicePixelRatio || 1);
    const W = innerWidth, H = innerHeight;
    field.width = W * dpr; field.height = H * dpr;
    u = W < 720 ? 11 : 14;
    const r = seeded(20261126), cols = Math.floor(W / u), rows = Math.floor(H / u), occ = new Set();
    items = [];
    for (let i = 0, n = Math.round(cols * rows / 9); i < n; i++) {
      const type = pick(r, TYPES), [w, h] = SIZES[type];
      const x = Math.floor(r() * (cols - w)), y = Math.floor(r() * (rows - h));
      let ok = true;
      for (let a = x - 2; a <= x + w + 1 && ok; a++) for (let b = y - 2; b <= y + h + 1; b++) if (occ.has(a * 9973 + b)) { ok = false; break; }
      if (!ok) continue;
      for (let a = x - 1; a <= x + w; a++) for (let b = y - 1; b <= y + h; b++) occ.add(a * 9973 + b);
      items.push({ type, x, y, w, h, c: [pick(r, P), pick(r, P), pick(r, P)], phase: r() * 100, live: r() < .45 });
    }
  }

  function drawItem(it, t) {
    const s = u, X = it.x * s, Y = it.y * s, [c0, c1, c2] = it.c;
    const step = Math.floor(t * 2 + it.phase);
    fx.save();
    if (it.live && (it.type === 'sq' || it.type === 'diamond' || it.type === 'frame')) {
      const ang = [0, 0, 0, 12, 24, 12, 0, -12][step % 8] * Math.PI / 180;
      fx.translate(X + it.w * s / 2, Y + it.h * s / 2); fx.rotate(ang); fx.translate(-(X + it.w * s / 2), -(Y + it.h * s / 2));
    }
    switch (it.type) {
      case 'sq': fx.fillStyle = c0; fx.fillRect(X + 1, Y + 1, s - 2, s - 2); break;
      case 'pair': fx.fillStyle = c0; fx.fillRect(X, Y, s, s); fx.fillStyle = c1; fx.fillRect(X + s, Y + s, s, s); break;
      case 'dots':
        for (let i = 0; i < it.w; i++) {
          const bob = it.live && (step + i) % 4 === 0 ? -s * .25 : 0;
          fx.fillStyle = it.c[i % 3]; fx.beginPath(); fx.arc(X + i * s + s / 2, Y + s / 2 + bob, s * .46, 0, 7); fx.fill();
        }
        break;
      case 'bar':
        for (let j = 0; j < it.h; j++) { fx.fillStyle = mix(c0, c1, j / (it.h - 1)); fx.fillRect(X, Y + j * s, s, s - 1); }
        break;
      case 'checker':
        for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) { fx.fillStyle = (i + j) % 2 ? c0 : c1; fx.fillRect(X + i * s, Y + j * s, s, s); }
        break;
      case 'rings': {
        const k = it.live ? step % 3 : 0, cs = [c0, c1, c2, c0, c1, c2];
        [0, .6, 1.2, 1.7].forEach((inset, i) => { fx.fillStyle = cs[i + k]; fx.fillRect(X + inset * s, Y + inset * s, (4 - 2 * inset) * s, (4 - 2 * inset) * s); });
        break;
      }
      case 'stairs':
        for (let i = 0; i < it.w; i++) { const h = Math.max(1, it.h - Math.floor(i * .8)); fx.fillStyle = P[(i + it.x) % P.length]; fx.fillRect(X + i * s, Y + (it.h - h) * s, s - 1, h * s); }
        break;
      case 'frame': fx.strokeStyle = c0; fx.lineWidth = s * .4; fx.strokeRect(X + s * .3, Y + s * .3, s * 1.4, s * 1.4); break;
      case 'diamond':
        fx.translate(X + s, Y + s); fx.rotate(Math.PI / 4); fx.fillStyle = c0; fx.fillRect(-s * .62, -s * .62, s * 1.24, s * 1.24);
        fx.fillStyle = c1; fx.fillRect(-s * .28, -s * .28, s * .56, s * .56); break;
    }
    fx.restore();
  }

  function paintField() {
    const t = performance.now() / 1000;
    fx.setTransform(dpr, 0, 0, dpr, 0, 0);
    fx.clearRect(0, 0, field.width, field.height);
    fx.globalAlpha = .92;
    for (const it of items) drawItem(it, t);
  }
  function runField() {
    clearInterval(fieldTimer);
    paintField();
    if (!reduce.matches) fieldTimer = setInterval(() => { if (!document.hidden) paintField(); }, 250);
  }
  let resizeTimer;
  addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { buildField(); runField(); setBanner(banner.state, true); }, 150); });
  reduce.addEventListener?.('change', runField);
  buildField(); runField();

  /* ── READY banner: text rendered from the pixel font, shown as beads ── */
  const fontReady = document.fonts ? document.fonts.load('700 12px Galmuri').catch(() => null) : Promise.resolve();
  const TEXT = { idle: 'READY?', ready: 'READY?', busy: 'MAKING', done: 'DONE!', error: 'RETRY?' };
  const banner = { state: 'idle', cells: [], cols: 0, rows: 0, order: [], t0: 0, raf: 0 };

  function glyphs(text) {
    const c = document.createElement('canvas'), x = c.getContext('2d', { willReadFrequently: true });
    const font = '700 12px Galmuri, monospace';
    x.font = font; c.width = Math.ceil(x.measureText(text).width) + 4; c.height = 18;
    x.font = font; x.textBaseline = 'top'; x.fillStyle = '#000'; x.fillText(text, 2, 2);
    const d = x.getImageData(0, 0, c.width, c.height).data, cells = [];
    let minY = 99, maxY = 0, minX = 999, maxX = 0;
    for (let y = 0; y < c.height; y++) for (let i = 0; i < c.width; i++) if (d[(y * c.width + i) * 4 + 3] > 110) {
      cells.push([i, y]); minY = Math.min(minY, y); maxY = Math.max(maxY, y); minX = Math.min(minX, i); maxX = Math.max(maxX, i);
    }
    return { cells: cells.map(([i, y]) => [i - minX, y - minY]), cols: maxX - minX + 1, rows: maxY - minY + 1 };
  }

  async function setBanner(state, redraw = false) {
    const cv = document.querySelector('#generate canvas');
    if (!cv) return;
    if (state === banner.state && !redraw && banner.cells.length) return;
    const prev = banner.state;
    banner.state = state;
    await fontReady;
    if (banner.state !== state) return;
    const g = glyphs(TEXT[state] || 'READY?');
    Object.assign(banner, g);
    const r = seeded(state.length * 97 + 3);
    banner.order = g.cells.map(() => r());
    banner.t0 = performance.now();
    banner.animate = !reduce.matches && !redraw && !(prev === state);
    cancelAnimationFrame(banner.raf);
    frame();
  }

  function frame() {
    const cv = document.querySelector('#generate canvas');
    if (!cv) return;
    const w = cv.clientWidth, h = cv.clientHeight, d = Math.min(2, devicePixelRatio || 1);
    if (cv.width !== Math.round(w * d)) { cv.width = Math.round(w * d); cv.height = Math.round(h * d); }
    const x = cv.getContext('2d');
    x.setTransform(d, 0, 0, d, 0, 0); x.clearRect(0, 0, w, h);
    const s = Math.max(3, Math.floor(Math.min((w - 24) / banner.cols, (h - 18) / banner.rows)));
    const ox = Math.round((w - s * banner.cols) / 2), oy = Math.round((h - s * banner.rows) / 2 + 2);
    const t = performance.now() - banner.t0, st = banner.state;
    const reveal = banner.animate ? Math.min(1, t / 700) : 1;
    const tick = Math.floor(t / 90);
    let more = banner.animate && reveal < 1;
    banner.cells.forEach(([i, j], k) => {
      const o = banner.order[k];
      if (o > reveal) return;
      let alpha = st === 'idle' ? .34 : 1;
      if (st === 'busy' && !reduce.matches) { alpha = ((k * 7 + tick) % 11) < 2 ? .25 : 1; more = true; }
      x.globalAlpha = alpha;
      x.fillStyle = BEAD[(i * 3 + j * 5) % 3];
      const g = Math.max(1, Math.round(s * .14));
      x.fillRect(ox + i * s + g, oy + j * s + g, s - 2 * g, s - 2 * g);
      x.fillStyle = 'rgba(120,40,30,.18)';
      x.fillRect(ox + i * s + s - 2 * g, oy + j * s + g, g, s - 2 * g);
    });
    x.globalAlpha = 1;
    if (more) banner.raf = requestAnimationFrame(frame);
  }
  new ResizeObserver(() => frame()).observe(document.querySelector('#generate') || document.body);

  /* ── result assemble: the real image, cut into module cells, flies into place ── */
  let token = 0;
  async function assemble(img, { cells = 49, spread = .6, dur = 560, stagger = 700 } = {}) {
    const my = ++token;
    img.parentElement.querySelectorAll('.assemble').forEach(c => c.remove());
    img.style.visibility = '';
    if (reduce.matches) return;
    try { await img.decode(); } catch { return; }
    if (my !== token) return;
    const stage = img.parentElement, cs = getComputedStyle(img), pad = parseFloat(cs.paddingLeft) || 0;
    const size = img.clientWidth - 2 * pad;
    if (size < 40 || !img.naturalWidth) return;
    const d = Math.min(2, devicePixelRatio || 1), cv = document.createElement('canvas');
    cv.className = 'assemble'; cv.setAttribute('aria-hidden', 'true');
    cv.width = cv.height = Math.round(size * d);
    Object.assign(cv.style, { left: img.offsetLeft + pad + 'px', top: img.offsetTop + pad + 'px', width: size + 'px', height: size + 'px', overflow: 'visible' });
    stage.append(cv);
    img.style.visibility = 'hidden';
    const x = cv.getContext('2d'); x.imageSmoothingEnabled = false;
    const n = Math.max(8, Math.min(64, Math.round(cells))), c = size / n, src = img.naturalWidth / n, r = seeded(my * 31 + 7);
    const pieces = [];
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      const a = r() * Math.PI * 2, dist = size * spread * (.25 + r() * .75);
      const cx = (i + .5) / n - .5, cy = (j + .5) / n - .5;
      pieces.push({ i, j, dx: Math.cos(a) * dist, dy: Math.sin(a) * dist, rot: (r() - .5) * 2.4, delay: stagger * (.55 * r() + .45 * Math.min(1, Math.hypot(cx, cy) * 1.6)) });
    }
    const t0 = performance.now(), total = stagger + dur;
    const ease = p => 1 - Math.pow(1 - p, 3);
    (function tick() {
      if (my !== token) { cv.remove(); return; }
      const t = performance.now() - t0;
      x.setTransform(1, 0, 0, 1, 0, 0); x.clearRect(0, 0, cv.width, cv.height);
      for (const p of pieces) {
        const raw = Math.min(1, Math.max(0, (t - p.delay) / dur));
        if (raw <= 0 && t < p.delay - 180) continue;
        const e = ease(Math.ceil(raw * 7) / 7);
        const k = 1 - e, rot = Math.round(p.rot * k / .26) * .26;
        const px = (p.i * c + c / 2 + p.dx * k) * d, py = (p.j * c + c / 2 + p.dy * k) * d;
        x.globalAlpha = Math.min(1, .35 + raw * 2);
        x.setTransform(Math.cos(rot) * d, Math.sin(rot) * d, -Math.sin(rot) * d, Math.cos(rot) * d, px, py);
        x.drawImage(img, p.i * src, p.j * src, src, src, -c / 2 - .3, -c / 2 - .3, c + .6, c + .6);
      }
      if (t < total) requestAnimationFrame(tick);
      else { img.style.visibility = ''; cv.remove(); }
    })();
  }

  /* ── top tray ── */
  function tray(slot, src) {
    const el = document.querySelector(`.step[data-slot="${slot}"]`);
    if (!el) return;
    const img = el.querySelector('img');
    if (!src) { el.classList.remove('filled'); img.removeAttribute('src'); return; }
    el.classList.remove('filled'); void el.offsetWidth;
    img.onload = () => el.classList.add('filled');
    img.src = src;
  }

  /* ── occasional static burst: thin noise bands + brief RGB split ── */
  function glitch() {
    if (reduce.matches || document.hidden) return;
    document.body.classList.add('rgb-split');
    const r = Math.random, n = 1 + Math.floor(r() * 3);
    for (let i = 0; i < n; i++) {
      const b = document.createElement('div');
      b.className = 'glitch-band'; b.setAttribute('aria-hidden', 'true');
      Object.assign(b.style, { top: Math.round(r() * innerHeight) + 'px', height: (3 + Math.round(r() * 14)) + 'px', animationDelay: i * 40 + 'ms' });
      document.body.append(b);
      setTimeout(() => b.remove(), 260 + i * 40);
    }
    setTimeout(() => document.body.classList.remove('rgb-split'), 140);
  }
  (function schedule() { setTimeout(() => { glitch(); schedule(); }, 7000 + Math.random() * 6000); })();

  window.fx = { banner: setBanner, assemble, tray, glitch };
  setBanner('idle', true);
})();
