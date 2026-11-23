// Landmark labels: a text sprite and a thin leader line for each structure whose manifest entry has
// a "label" point (glTF metres). Shown when the toggle is on and the structure itself is visible.
import * as THREE from 'three';

const COLOR = '#7fe3ff', HEIGHT = 0.011;   // label text height in metres (model scale)

function sprite(text) {
  const c = document.createElement('canvas'), g = c.getContext('2d'), font = 'bold 48px system-ui, sans-serif';
  g.font = font; const w = Math.ceil(g.measureText(text).width) + 28;
  c.width = w; c.height = 68;
  g.font = font; g.textBaseline = 'middle';
  g.fillStyle = 'rgba(15,20,28,0.72)'; g.beginPath(); g.roundRect(0, 0, w, 68, 14); g.fill();
  g.fillStyle = COLOR; g.fillText(text, 14, 36);
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true, toneMapped: false }));
  s.scale.set(HEIGHT * w / 68, HEIGHT, 1); s.renderOrder = 20;
  return s;
}

export class Labels {
  constructor(A, on) {
    this.A = A; this.on = on; this.items = [];
    const parent = A.center, lineMat = new THREE.LineBasicMaterial({ color: COLOR, depthTest: false, transparent: true, opacity: 0.8 });
    parent.updateMatrixWorld(true);
    for (const s of A.structs) {
      if (!s.label) continue;
      const at = new THREE.Vector3(...s.label), box = new THREE.Box3();
      for (const m of s.meshes) box.expandByObject(m);
      const from = parent.worldToLocal(box.getCenter(new THREE.Vector3()));
      const sp = sprite(s.name); sp.position.copy(at);
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([from, at]), lineMat);
      line.renderOrder = 19;
      sp.userData.struct = line.userData.struct = s;
      parent.add(sp, line); this.items.push({ s, sp, line });
    }
    this.update();
  }
  set(on) { this.on = on; this.update(); }
  update() {
    for (const { s, sp, line } of this.items) sp.visible = line.visible = this.on && this.A.visibleOf(s);
  }
}
