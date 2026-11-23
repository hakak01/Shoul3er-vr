// Wrist menu (Layers / Search / Tools) and the selection info panel.
import { Panel } from './panel.js';

const LAYER_LABEL = { skin: 'Skin', fat: 'Subcutaneous fat', fascia_retinacula: 'Fascia & retinacula', muscle: 'Muscles & tendons',
  tendon_sheath: 'Tendon sheaths', ligament_capsule: 'Ligaments & capsules', nerve: 'Nerves',
  artery: 'Arteries', vein: 'Veins', bone: 'Bones', attachment: 'Origins/insertions' };
const KEYS = ['ABCDEFGHI', 'JKLMNOPQR', 'STUVWXYZ-'];

export class Menus {
  // app: { anatomy, resetView(), focus(s), exitXR(), inXR() , fps }
  constructor(app) {
    this.app = app; this.tab = 'layers'; this.query = ''; this.page = 0;
    this.menu = new Panel(640, 800, 0.22);
    this.info = new Panel(640, 330, 0.22);
    this.refresh();
  }
  get A() { return this.app.anatomy; }
  refresh() { if (!this.menu.drag) this.buildMenu(); this.buildInfo(); }

  buildMenu() {
    const p = this.menu; p.clear();
    [['layers', 'Layers'], ['search', 'Search'], ['tools', 'Tools']].forEach(([k, l], i) =>
      p.button(15 + i * 205, 12, 195, 56, l, () => { this.tab = k; this.refresh(); }, { active: this.tab === k, size: 26 }));
    this['tab_' + this.tab](p);
    p.draw();
  }

  tab_layers(p) {
    const A = this.A; let y = 86;
    p.text(300, y + 10, 'show', { size: 18, color: '#9aa' }); p.text(440, y + 10, 'opacity', { size: 18, color: '#9aa' });
    y += 26;
    for (const k of Object.keys(LAYER_LABEL)) {
      const L = A.layers[k]; if (!L) continue;
      p.button(15, y, 265, 46, (L.on ? '✓ ' : '   ') + (L.label || LAYER_LABEL[k]),
        () => { A.setLayer(k, !L.on); this.refresh(); }, { active: L.on, size: 22 });
      p.text(625, y + 23, Math.round(L.opacity * 100) + '%', { size: 20, align: 'right' });
      const pct = p.items[p.items.length - 1];
      p.slider(300, y, 255, 46, L.opacity, (v) => { A.setLayerOpacity(k, v); pct.label = Math.round(v * 100) + '%'; });
      y += 52;
    }
    p.button(15, y + 10, 300, 56, 'Show all', () => { A.showAll(); this.refresh(); });
    p.button(325, y + 10, 300, 56, 'Reset view', () => this.app.resetView());
  }

  tab_search(p) {
    const A = this.A, res = A.search(this.query), per = 6;
    this.page = Math.min(this.page, Math.max(0, Math.ceil(res.length / per) - 1));
    p.text(20, 105, '🔍 ' + (this.query || 'type a name…') + (this.query ? '' : ''), { size: 26, color: this.query ? '#fff' : '#889' });
    p.text(625, 105, res.length + ' found', { size: 18, align: 'right', color: '#9aa' });
    let y = 135;
    res.slice(this.page * per, this.page * per + per).forEach((s) => {
      p.button(15, y, 540, 46, s.name, () => { A.select(s); this.refresh(); },
        { size: 20, active: A.selected === s });
      y += 52;
    });
    p.button(565, 135, 60, 150, '▲', () => { this.page = Math.max(0, this.page - 1); this.refresh(); });
    p.button(565, 293, 60, 150, '▼', () => { this.page++; this.refresh(); });
    y = 455;
    const type = (ch) => { this.query += ch; this.page = 0; this.refresh(); };
    KEYS.forEach((row) => {
      [...row].forEach((ch, i) => p.button(15 + i * 68, y, 62, 62, ch, () => type(ch.toLowerCase()), { size: 26 }));
      y += 70;
    });
    p.button(15, y, 300, 62, 'Space', () => type(' '));
    p.button(325, y, 145, 62, '⌫', () => { this.query = this.query.slice(0, -1); this.refresh(); });
    p.button(480, y, 145, 62, 'Clear', () => { this.query = ''; this.page = 0; this.refresh(); });
  }

  tab_tools(p) {
    const A = this.A, c = A.clip; let y = 90;
    p.text(20, y + 10, 'Cross-section (clipping plane)', { size: 22, bold: true }); y += 34;
    ['off', 'axial', 'sagittal', 'coronal'].forEach((m, i) =>
      p.button(15 + i * 154, y, 146, 52, m[0].toUpperCase() + m.slice(1), () => { A.setClip(m); this.refresh(); },
        { active: c.mode === m, size: 22 }));
    y += 64;
    p.slider(15, y, 460, 52, c.pos, (v) => { c.pos = v; A.updateClip(); });
    p.button(490, y, 135, 52, 'Flip', () => { c.flip = !c.flip; A.updateClip(); this.refresh(); }, { active: c.flip });
    y += 58;
    p.text(20, y + 8, 'Right thumbstick also moves the plane.', { size: 18, color: '#9aa' }); y += 34;
    p.text(20, y + 10, 'Muscle footprints', { size: 22, bold: true }); y += 34;
    p.button(15, y, 300, 52, 'Origins (red)', () => { A.setFootprints(!A.showOrigins, A.showInsertions); this.refresh(); },
      { active: A.showOrigins, color: '#c0392b' });
    p.button(325, y, 300, 52, 'Insertions (blue)', () => { A.setFootprints(A.showOrigins, !A.showInsertions); this.refresh(); },
      { active: A.showInsertions, color: '#2449e0' });
    y += 70;
    p.text(20, y + 10, 'Skin tone', { size: 22, bold: true }); y += 30;
    p.slider(15, y, 610, 52, A.skinTone, (v) => A.setSkinTone(v)); y += 70;
    const R = this.app.realism, view = R ? R.view : 'present';
    p.text(20, y + 10, 'View' + (R && R.status ? '  (' + R.status + ')' : ''), { size: 22, bold: true }); y += 30;
    [['Present', 'present'], ['Realistic', 'realistic'], ['Cadaver', 'cadaver']].forEach(([t, v], i) =>
      p.button(15 + i * 205, y, 200, 52, t, () => R && R.setView(v), { active: view === v })); y += 66;
    p.button(15, y, 300, 56, 'Show all', () => { A.showAll(); this.refresh(); });
    p.button(325, y, 300, 56, 'Reset view', () => this.app.resetView()); y += 66;
    if (this.app.inXR()) p.button(15, y, 610, 60, 'Exit VR / MR', () => this.app.exitXR(), { active: true, color: '#b03030' });
    p.text(625, 785, this.app.fps ? this.app.fps + ' fps' : '', { size: 18, align: 'right', color: '#9aa' });
  }

  buildInfo() {
    const p = this.info, A = this.A, s = A.selected; p.clear();
    if (!s) {
      p.text(20, 60, this.app.inXR() ? 'Point the right controller at a structure and pull the trigger.'
        : 'Click or tap a structure to select it.', { size: 24, wrap: 600, color: '#bbb' });
      p.button(15, 250, 300, 62, 'Show all', () => { A.showAll(); this.refresh(); });
    } else {
      p.text(20, 36, s.name, { size: 30, bold: true, wrap: 560, maxLines: 2 });
      p.button(575, 12, 50, 50, '✕', () => { A.select(null); this.refresh(); });
      p.text(20, 120, 'Layer: ' + (LAYER_LABEL[s.layer] || s.layer) + (s.kind ? ' · ' + s.kind : ''), { size: 21, color: '#bcd' });
      p.text(20, 150, 'Source: ' + (s.source || ''), { size: 18, color: '#99a', wrap: 600, maxLines: 1 });
      if (s.approx) p.text(20, 182, 'APPROXIMATE – check', { size: 24, bold: true, color: '#ffb02e' });
      const b = [['Hide', () => A.hide(s)], ['Ghost', () => A.toggleGhost(s)], ['Isolate', () => A.isolate(s)],
        ['Show all', () => A.showAll()], ['Focus', () => this.app.focus(s)]];
      b.forEach(([l, f], i) => p.button(15 + i * 123, 240, 116, 72, l, () => { f(); this.refresh(); },
        { size: 22, active: (l === 'Ghost' && s.ghost) || (l === 'Isolate' && !!A.isolated) }));
    }
    p.draw();
  }

  // physical keyboard on desktop
  key(e) {
    if (this.tab !== 'search') return;
    if (e.key === 'Backspace') this.query = this.query.slice(0, -1);
    else if (e.key.length === 1 && /[\w \-]/.test(e.key)) this.query += e.key.toLowerCase();
    else return;
    this.page = 0; this.refresh();
  }
}
