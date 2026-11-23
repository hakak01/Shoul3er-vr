// Registry of structures + visibility / ghost / isolate / clip / highlight state.
import * as THREE from 'three';
import { lookKey, makeMaterial } from './looks.js';

const GHOST = 0.25;
const mats = (m) => { const { present, real } = m.userData.mats; return real && real !== present ? [present, real] : [present]; };
const AXES = { sagittal: new THREE.Vector3(1, 0, 0), axial: new THREE.Vector3(0, 1, 0), coronal: new THREE.Vector3(0, 0, 1) };

export class Anatomy {
  // root: Group that the user moves. gltfScene: loaded scene. manifest: list. look: look.json
  constructor(root, gltfScene, manifest, look) {
    this.root = root; this.look = look;
    this.layers = JSON.parse(JSON.stringify(look.layers));
    this.showOrigins = this.showInsertions = this.layers.attachment.on;
    this.structs = []; this.byName = new Map();
    this.isolated = null; this.selected = null; this.onChange = () => {};
    this.worldPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 1e6);
    this.clipPlanes = [this.worldPlane];
    this.clip = { mode: 'off', pos: 0.5, flip: false };
    this.skinTone = look.skinTone ?? 0.2;
    this.highlight = new THREE.Color(look.highlight);

    // centre the model on its bounding box
    const box = new THREE.Box3().setFromObject(gltfScene);
    this.center = new THREE.Group();
    this.center.position.copy(box.getCenter(new THREE.Vector3())).negate();
    this.center.add(gltfScene); root.add(this.center);
    root.updateMatrixWorld(true);
    this.box = box.clone().translate(this.center.position);   // model-space box (centred)

    const info = new Map(manifest.map((e) => [e.name, e]));
    const sanitize = (s) => s.replace(/\s/g, '_').replace(/[\[\]\.:\/]/g, '');
    const bySan = new Map(manifest.map((e) => [sanitize(e.name), e]));
    const inv = new THREE.Matrix4().copy(root.matrixWorld).invert();
    for (const node of [...gltfScene.children]) {
      const e = info.get(node.userData.name) || bySan.get(node.name);
      if (!e) { console.warn('not in manifest', node.name); continue; }
      const s = { name: e.name, layer: e.layer, kind: e.kind || null, approx: !!e.approx, source: e.source,
        node, meshes: [], hidden: false, ghost: false };
      node.traverse((m) => {
        if (!m.isMesh) return;
        const key = lookKey(e.layer, m.material && m.material.name, s.kind, e.name);
        const nm = new THREE.Matrix4().multiplyMatrices(inv, m.matrixWorld);
        m.userData.gltfMat = m.material && m.material.name;
        m.material = makeMaterial(look, key, m, nm, this.clipPlanes);
        m.userData.mats = { present: m.material };   // 'real' is added by tissues.js
        m.userData.struct = s;
        s.meshes.push(m);
      });
      this.structs.push(s); this.byName.set(s.name, s);
    }
    this.structs.sort((a, b) => a.name.localeCompare(b.name));
    this.setSkinTone(this.skinTone);
    this.apply();
  }

  visibleOf(s) {
    const L = this.layers[s.layer];
    if (!L || !L.on || s.hidden) return false;
    if (s.kind === 'origin' && !this.showOrigins) return false;
    if (s.kind === 'insertion' && !this.showInsertions) return false;
    if (this.isolated && !this.isolated.has(s)) return false;
    return L.opacity > 0.01;
  }

  apply() {
    for (const s of this.structs) {
      const vis = this.visibleOf(s), f = this.layers[s.layer].opacity * (s.ghost ? GHOST : 1);
      for (const m of s.meshes) {
        m.visible = vis;
        for (const mat of mats(m)) {
          const op = mat.userData.baseOpacity * f, tr = op < 0.999;
          mat.opacity = op;
          if (mat.transparent !== tr) { mat.transparent = tr; mat.depthWrite = !tr; mat.needsUpdate = true; }
          mat.emissive.copy(s === this.selected ? this.highlight : new THREE.Color(0)).multiplyScalar(0.35);
        }
      }
    }
    this.pickables = this.structs.filter((s) => this.visibleOf(s)).flatMap((s) => s.meshes);
    this.onChange();
  }

  setLayer(layer, on) {
    this.layers[layer].on = on;
    if (layer === 'attachment') this.showOrigins = this.showInsertions = on;
    this.apply();
  }
  setLayerOpacity(layer, v) { this.layers[layer].opacity = v; this.apply(); }
  setFootprints(origins, insertions) {
    this.showOrigins = origins; this.showInsertions = insertions;
    this.layers.attachment.on = origins || insertions; this.apply();
  }
  select(s) { this.selected = s; this.apply(); }
  hide(s) { s.hidden = true; if (this.selected === s) this.selected = null; this.apply(); }
  toggleGhost(s) { s.ghost = !s.ghost; this.apply(); }
  isolate(s) {
    this.isolated = new Set([s]);
    if (!this.layers[s.layer].on) this.layers[s.layer].on = true;
    if (s.kind === 'origin') this.showOrigins = true;
    if (s.kind === 'insertion') this.showInsertions = true;
    s.hidden = false; this.apply();
  }
  showAll() {
    this.isolated = null;
    for (const s of this.structs) { s.hidden = false; s.ghost = false; }
    for (const k in this.layers) if (k !== 'attachment' && k !== 'fat') { this.layers[k].on = true; if (this.layers[k].opacity < 0.05) this.layers[k].opacity = 1; }
    this.apply();
  }
  search(q) {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    if (!words.length) return this.structs;
    return this.structs.filter((s) => words.every((w) => s.name.toLowerCase().includes(w)));
  }
  setSkinTone(t) {
    this.skinTone = t;
    const a = new THREE.Color(this.look.looks.skin.color), b = new THREE.Color(this.look.looks.skin.colorDark);
    const R = this.skinReal, ra = R && new THREE.Color(R.color), rb = R && new THREE.Color(R.colorDark || R.color);
    for (const s of this.structs) for (const m of s.meshes) for (const mat of mats(m)) {
      if (mat.userData.key !== 'skin') continue;
      if (mat.isMeshPhysicalMaterial) mat.color.lerpColors(ra, rb, t); else mat.color.lerpColors(a, b, t);
      mat.userData.u.uCut.value.copy(mat.color).multiplyScalar(0.8);
    }
  }
  // 'present' or 'realistic' (realistic materials must already exist, see tissues.js)
  setView(v) {
    this.view = v;
    for (const s of this.structs) for (const m of s.meshes) m.material = (v === 'realistic' && m.userData.mats.real) || m.userData.mats.present;
    this.setSkinTone(this.skinTone); this.apply();
  }

  // world-space centre + size of a structure
  bounds(s) {
    const b = new THREE.Box3();
    for (const m of s.meshes) b.expandByObject(m);
    return { center: b.getCenter(new THREE.Vector3()), size: b.getSize(new THREE.Vector3()).length() };
  }

  setClip(mode) {
    const wasOn = this.clip.mode !== 'off', on = mode !== 'off';
    this.clip.mode = mode;
    if (wasOn !== on) for (const s of this.structs) for (const m of s.meshes) for (const mat of mats(m)) {
      mat.side = on ? THREE.DoubleSide : THREE.FrontSide; mat.needsUpdate = true;
    }
    this.updateClip();
  }
  updateClip() {
    const c = this.clip;
    if (c.mode === 'off') { this.worldPlane.set(new THREE.Vector3(0, 1, 0), 1e6); return; }
    const n = AXES[c.mode].clone(), k = c.mode === 'sagittal' ? 'x' : c.mode === 'axial' ? 'y' : 'z';
    const p = new THREE.Vector3(); p[k] = this.box.min[k] + c.pos * (this.box.max[k] - this.box.min[k]);
    if (c.flip) n.negate();
    this.worldPlane.setFromNormalAndCoplanarPoint(n, p).applyMatrix4(this.root.matrixWorld);
  }
  // Is a world point on the visible side of the clip plane?
  kept(pt) { return this.clip.mode === 'off' || this.worldPlane.distanceToPoint(pt) >= 0; }

  pick(raycaster) {
    const hits = raycaster.intersectObjects(this.pickables, false).filter((h) => this.kept(h.point));
    const solid = hits.find((h) => h.object.material.opacity > 0.5);
    const h = solid || hits[0];
    return h ? { struct: h.object.userData.struct, distance: h.distance, point: h.point } : null;
  }
}
