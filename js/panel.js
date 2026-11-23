// Tiny canvas UI: buttons, sliders, text. Same canvas is used on screen (desktop/phone)
// and as a texture on a plane in VR.
import * as THREE from 'three';

export class Panel {
  constructor(w, h, widthM) {
    this.W = w; this.H = h;
    this.canvas = document.createElement('canvas');
    this.canvas.width = w; this.canvas.height = h;
    this.ctx = this.canvas.getContext('2d');
    this.tex = new THREE.CanvasTexture(this.canvas);
    this.tex.colorSpace = THREE.SRGBColorSpace;
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(widthM, widthM * h / w),
      new THREE.MeshBasicMaterial({ map: this.tex, transparent: true, toneMapped: false }));
    this.mesh.userData.panel = this;
    this.items = []; this.hover = null; this.drag = null;
  }
  clear() { this.items = []; }
  button(x, y, w, h, label, onClick, o = {}) { this.items.push({ t: 'btn', x, y, w, h, label, onClick, ...o }); }
  slider(x, y, w, h, value, onChange, o = {}) { this.items.push({ t: 'sld', x, y, w, h, value, onChange, ...o }); }
  text(x, y, label, o = {}) { this.items.push({ t: 'txt', x, y, label, ...o }); }

  draw() {
    const c = this.ctx;
    c.clearRect(0, 0, this.W, this.H);
    c.fillStyle = 'rgba(22,25,31,0.92)'; rr(c, 0, 0, this.W, this.H, 18); c.fill();
    c.textBaseline = 'middle';
    for (const it of this.items) {
      if (it.t === 'btn') {
        c.fillStyle = it.active ? (it.color || '#2d6cdf') : (it === this.hover ? '#4a515e' : '#343a45');
        rr(c, it.x, it.y, it.w, it.h, 10); c.fill();
        c.fillStyle = '#fff'; c.font = `${it.size || 24}px system-ui, sans-serif`; c.textAlign = 'center';
        c.fillText(fit(c, it.label, it.w - 10), it.x + it.w / 2, it.y + it.h / 2 + 1);
      } else if (it.t === 'sld') {
        const cy = it.y + it.h / 2;
        c.fillStyle = '#343a45'; rr(c, it.x, cy - 6, it.w, 12, 6); c.fill();
        c.fillStyle = '#2d6cdf'; rr(c, it.x, cy - 6, it.w * it.value, 12, 6); c.fill();
        c.fillStyle = it === this.hover || it === this.drag ? '#fff' : '#cfd6e2';
        c.beginPath(); c.arc(it.x + it.w * it.value, cy, it.h * 0.36, 0, 7); c.fill();
      } else {
        c.fillStyle = it.color || '#e6e6e6'; c.font = `${it.bold ? '600 ' : ''}${it.size || 24}px system-ui, sans-serif`;
        c.textAlign = it.align || 'left';
        const lines = it.wrap ? wrap(c, it.label, it.wrap) : [it.label];
        lines.slice(0, it.maxLines || 9).forEach((l, i) => c.fillText(l, it.x, it.y + i * (it.size || 24) * 1.2));
      }
    }
    this.tex.needsUpdate = true;
  }

  at(px, py) {
    for (let i = this.items.length - 1; i >= 0; i--) {
      const it = this.items[i];
      if (it.t !== 'txt' && px >= it.x - 4 && px <= it.x + it.w + 4 && py >= it.y - 4 && py <= it.y + it.h + 4) return it;
    }
    return null;
  }
  move(px, py) {
    if (this.drag) { this.setSlider(this.drag, px); return; }
    const h = this.at(px, py);
    if (h !== this.hover) { this.hover = h; this.draw(); }
  }
  down(px, py) {
    const it = this.at(px, py);
    if (!it) return false;
    if (it.t === 'sld') { this.drag = it; this.setSlider(it, px); } else if (it.onClick) it.onClick();
    return true;
  }
  up() { this.drag = null; }
  leave() { if (this.hover) { this.hover = null; this.draw(); } }
  setSlider(it, px) {
    it.value = Math.min(1, Math.max(0, (px - it.x) / it.w));
    it.onChange(it.value); this.draw();
  }
  // uv (from a raycast hit) -> canvas pixels
  uvToPx(uv) { return [uv.x * this.W, (1 - uv.y) * this.H]; }

  // Show the canvas on screen and wire mouse/touch.
  attachDom(id) {
    const cv = this.canvas; cv.id = id; cv.className = 'panel'; document.body.appendChild(cv);
    const px = (e) => { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * this.W / r.width, (e.clientY - r.top) * this.H / r.height]; };
    cv.addEventListener('pointerdown', (e) => { cv.setPointerCapture(e.pointerId); this.down(...px(e)); e.stopPropagation(); });
    cv.addEventListener('pointermove', (e) => this.move(...px(e)));
    cv.addEventListener('pointerup', () => this.up());
    cv.addEventListener('pointerleave', () => this.leave());
  }
}

function rr(c, x, y, w, h, r) {
  c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
}
function fit(c, s, w) {
  if (c.measureText(s).width <= w) return s;
  while (s.length > 1 && c.measureText(s + '…').width > w) s = s.slice(0, -1);
  return s + '…';
}
function wrap(c, s, w) {
  const out = []; let line = '';
  for (const word of s.split(' ')) {
    const t = line ? line + ' ' + word : word;
    if (c.measureText(t).width > w && line) { out.push(line); line = word; } else line = t;
  }
  if (line) out.push(line);
  return out;
}
