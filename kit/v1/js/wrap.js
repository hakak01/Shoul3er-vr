// Phase D2 (assets/wrap.json, built by tools/build_wrap.py):
// - scapulothoracic contact: small extra scapula rotation about the AC joint so its costal surface stays on a thorax
//   ellipsoid (Seth 2016 idea), same steps as contact() in tools/rig_pose.py
// - corrective shapes (morph targets made offline at 6 poses), blended from the arm sliders (weights() in
//   tools/wrap_morph.py)
import * as THREE from 'three';

const V = (a) => new THREE.Vector3(...a), clamp01 = (x) => Math.min(Math.max(x, 0), 1);
export const POSE_NAMES = ['abd90', 'fullElev', 'erSide', 'irSide', 'aber', 'crossBody'];

// meshopt stores morph deltas quantized like the positions: undo with the linear part of the position fix Q
export function prepareMorphs(m, Q) {
  const mp = m.geometry.morphAttributes.position; if (!mp) return;
  const L = new THREE.Matrix3().setFromMatrix4(Q), v = new THREE.Vector3();
  m.geometry.morphAttributes.position = mp.map((a) => {
    const o = new Float32Array(a.count * 3);
    for (let i = 0; i < a.count; i++) v.fromBufferAttribute(a, i).applyMatrix3(L).toArray(o, i * 3);
    return new THREE.BufferAttribute(o, 3);
  });
}

export class Wrap {
  constructor(rig, data) {
    this.rig = rig; this.d = data; const T = data.thorax;
    this.T = { c: V(T.c), col: [0, 1, 2].map((j) => new THREE.Vector3(T.axes[0][j], T.axes[1][j], T.axes[2][j])), r: T.r,
      s: T.samples.map(V), tgt: T.target };
    this.morphs = rig.skinned.filter((m) => m.morphTargetDictionary && 'abd90' in m.morphTargetDictionary)
      .map((m) => ({ m, idx: POSE_NAMES.map((n) => m.morphTargetDictionary[n]) }));
    this.extra = 0; this.w = POSE_NAMES.map(() => 0);
  }

  // weights of the 6 corrective shapes from the sliders: exact at the 6 poses, 0 at rest
  weights(p) {
    const B = this.d.blend, c = clamp01, e = p.elev, r = p.rot;
    const hi = c((e - B.elevMid) / (B.elevFull - B.elevMid)), mid = c((e - B.elev0) / (B.elevMid - B.elev0)) - hi, lo = 1 - mid - hi;
    const er = c((r - B.rot0) / (B.rotER - B.rot0)), ir = c((r - B.rot0) / (B.rotIR - B.rot0));
    const x = c(p.plane / B.planeCross), ab = c(r / B.rotABER);
    return [mid * (1 - x) * (1 - ab), hi, lo * er, lo * ir, mid * (1 - x) * ab, mid * x];
  }

  level(x, out) {
    const T = this.T, d = x.clone().sub(T.c), y = T.col.map((a, j) => d.dot(a) / T.r[j]);
    if (out) out.y = y;
    return Math.hypot(...y);
  }

  // extra rotation (Matrix4) of the scapula about the posed AC joint piv; Qs = scapula delta rotation, hs = rest AC
  contact(Qs, hs, piv) {
    const T = this.T, X0 = T.s.map((s) => s.clone().sub(hs).applyMatrix4(Qs).add(piv)), Rx = new THREE.Matrix4();
    const q = new THREE.Quaternion(), x = new THREE.Vector3();
    for (let it = 0; it < 8; it++) {
      let k = -1, vk = 1e-4, lk = 0, yk = null;
      X0.forEach((p, i) => { x.copy(p).sub(piv).applyMatrix4(Rx).add(piv); const o = {}, l = this.level(x, o), v = T.tgt[i] - l;
        if (v > vk) { vk = v; k = i; lk = l; yk = o.y; } });
      if (k < 0) break;
      const g = new THREE.Vector3(); T.col.forEach((a, j) => g.addScaledVector(a, yk[j] / T.r[j] / lk));
      const gn = g.length(), n = g.clone().divideScalar(gn);
      x.copy(X0[k]).sub(piv).applyMatrix4(Rx);
      const ax = x.clone().cross(n), s = ax.length(); if (s < 1e-6) break;
      Rx.premultiply(new THREE.Matrix4().makeRotationFromQuaternion(q.setFromAxisAngle(ax.divideScalar(s), Math.min(vk / gn / s, 0.1745))));
    }
    this.extra = THREE.MathUtils.radToDeg(2 * Math.acos(Math.min(1, Math.abs(new THREE.Quaternion().setFromRotationMatrix(Rx).w))));
    return Rx;
  }

  update(p) {
    this.w = this.weights(p);
    for (const { m, idx } of this.morphs) idx.forEach((k, i) => { if (k !== undefined) m.morphTargetInfluences[k] = this.w[i]; });
  }
}
