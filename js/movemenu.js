// "Move" tab of the wrist menu: arm sliders, preset poses, manual scapula, tension toggle.
import { ST_KEYS } from './rig.js';

const ARM = [['plane', 'Plane of elev.', 'plane'], ['elev', 'Elevation', 'elevation'], ['rot', 'Rotation ER+/IR−', 'rotation'],
  ['elbow', 'Elbow flexion', 'elbow'], ['sup', 'Supination+/Pron−', 'supination']];
const ST_LABEL = { 'clavicle.retraction': 'Clav. retraction', 'clavicle.elevation': 'Clav. elevation',
  'clavicle.posteriorRotation': 'Clav. post. rotation', 'scapula.upwardRotation': 'Scap. upward rot.',
  'scapula.posteriorTilt': 'Scap. post. tilt', 'scapula.externalRotation': 'Scap. ext. rotation' };
const PRESETS = [['Rest', null], ['Abd 90°', { plane: 0, elev: 90, rot: 0 }], ['Full elev.', { plane: 30, elev: 170, rot: 0 }],
  ['ER 90° side', { elev: 0, rot: 90, elbow: 90 }], ['IR side', { elev: 0, rot: -80, elbow: 90 }],
  ['ABER', { plane: 0, elev: 90, rot: 90, elbow: 90 }], ['Cross-body', { plane: 135, elev: 90, rot: 0, elbow: 90 }],
  ['Elbow 90°', { elbow: 90 }]];

function row(p, y, label, v, lo, hi, set) {
  p.text(20, y + 24, label, { size: 20 });
  p.text(625, y + 24, Math.round(v) + '°', { size: 20, align: 'right' });
  const val = p.items[p.items.length - 1];
  p.slider(230, y, 330, 48, (v - lo) / (hi - lo), (t) => { const x = lo + t * (hi - lo); set(x); val.label = Math.round(x) + '°'; });
}

export function tabMove(menus, p) {
  const R = menus.app.rig; let y = 84;
  if (!R || !R.ok) { p.text(20, 120, 'Movement data not loaded (assets/rig.json).', { size: 22, wrap: 600 }); return; }
  const L = R.lim, P = R.p;
  p.text(20, y + 12, 'Arm vs thorax (ISB), elbow, forearm', { size: 21, bold: true }); y += 30;
  for (const [k, label, lk] of ARM) {
    const lo = k === 'elbow' ? Math.min(L.elbow[0], R.rest.elbowFlexion) : L[lk][0];
    const hi = k === 'elev' ? R.maxElev(P.plane) : k === 'sup' ? Math.max(L[lk][1], R.rest.supination) : L[lk][1];
    row(p, y, label, P[k], lo, hi, (x) => R.set({ [k]: x })); y += 52;
  }
  PRESETS.forEach(([t, v], i) => p.button(15 + (i % 4) * 153, y + Math.floor(i / 4) * 56, 147, 50, t,
    () => { R.set(v || R.home); menus.refresh(); }, { size: 20 }));
  y += 116;
  p.button(15, y, 300, 50, 'Show tension: ' + (R.tensionOn ? 'ON' : 'off'), () => { R.setTension(!R.tensionOn); menus.refresh(); },
    { active: R.tensionOn, size: 20 });
  p.button(325, y, 300, 50, 'Manual scapula: ' + (R.manual ? 'ON' : 'off'), () => { R.setManual(!R.manual); menus.refresh(); },
    { active: R.manual, size: 20 }); y += 58;
  const d = R.manual ? R.st : R.rhythmAt(P.elev, P.plane), gh = P.elev - d['scapula.upwardRotation'];
  p.text(20, y + 12, `Scapula: upward rot ${d['scapula.upwardRotation'].toFixed(0)}°, post. tilt ${d['scapula.posteriorTilt'].toFixed(0)}° ` +
    `(change from rest) · GH ≈ ${gh.toFixed(0)}°` + (R.wrap ? ` · thorax contact +${R.wrap.extra.toFixed(0)}°` : ''), { size: 18, color: '#9aa', wrap: 610 }); y += 30;
  if (R.manual) for (const [seg, k] of ST_KEYS) {
    const key = seg + '.' + k; row(p, y, ST_LABEL[key], R.st[key], -40, 70, (x) => R.setST(key, x)); y += 48;
  }
  else p.text(20, y + 12, 'Scapula + clavicle follow assets/rhythm.json. In VR: squeeze grip on the forearm to move the arm.',
    { size: 18, color: '#9aa', wrap: 610 });
}
