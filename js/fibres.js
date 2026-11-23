// Fibre frames without UVs: follow each mesh's centreline so fibres stay lengthwise around bends.
// Adds vertex attributes fibreQ ("straightened" position in metres: x = across, y = along, z = across),
// fibreT (fibre direction) and fibreB (across direction); T and B are in the mesh's own space.
import * as THREE from 'three';

const BIN = 0.004;   // centreline sample spacing (m)

function pca(pts) {
  const mean = new THREE.Vector3();
  for (const p of pts) mean.add(p);
  mean.divideScalar(pts.length);
  const c = [0, 0, 0, 0, 0, 0];
  for (const p of pts) {
    const x = p.x - mean.x, y = p.y - mean.y, z = p.z - mean.z;
    c[0] += x * x; c[1] += x * y; c[2] += x * z; c[3] += y * y; c[4] += y * z; c[5] += z * z;
  }
  let a = new THREE.Vector3(0.3, 1, 0.2).normalize();
  for (let k = 0; k < 30; k++) {
    const b = new THREE.Vector3(c[0] * a.x + c[1] * a.y + c[2] * a.z, c[1] * a.x + c[3] * a.y + c[4] * a.z,
      c[2] * a.x + c[4] * a.y + c[5] * a.z);
    if (b.lengthSq() < 1e-30) break;
    a = b.normalize();
  }
  return { mean, axis: a };
}

function anyPerp(t) {
  const h = Math.abs(t.y) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
  return h.sub(t.clone().multiplyScalar(h.dot(t))).normalize();
}

// geom: BufferGeometry; toModel: Matrix4 mesh -> model space (metres)
export function addFibreFrames(geom, toModel) {
  if (geom.attributes.fibreQ) return;
  const pos = geom.attributes.position, n = pos.count;
  const used = new Uint8Array(n);
  if (geom.index) for (const i of geom.index.array) used[i] = 1; else used.fill(1);
  const P = new Array(n), pts = [];
  for (let i = 0; i < n; i++) if (used[i]) { P[i] = new THREE.Vector3().fromBufferAttribute(pos, i).applyMatrix4(toModel); pts.push(P[i]); }
  if (pts.length < 3) return;
  const { mean, axis } = pca(pts);
  // 1. bins along the main axis -> raw centreline
  let smin = Infinity, smax = -Infinity;
  for (const p of pts) { const s = p.clone().sub(mean).dot(axis); smin = Math.min(smin, s); smax = Math.max(smax, s); }
  const K = Math.max(2, Math.min(40, Math.round((smax - smin) / BIN))), w = (smax - smin) / K || 1e-6;
  const sum = Array.from({ length: K }, () => new THREE.Vector3()), cnt = new Array(K).fill(0);
  const binOf = (p) => (p.clone().sub(mean).dot(axis) - smin) / w - 0.5;
  for (const p of pts) { const b = Math.min(K - 1, Math.max(0, Math.round(binOf(p)))); sum[b].add(p); cnt[b]++; }
  let C = [];
  for (let k = 0; k < K; k++) C.push(cnt[k] ? sum[k].divideScalar(cnt[k]) : null);
  for (let k = 0; k < K; k++) if (!C[k]) {          // fill empty bins by straight line along the axis
    let a = k - 1; while (a >= 0 && !C[a]) a--;
    let b = k + 1; while (b < K && !C[b]) b++;
    const base = a >= 0 ? C[a] : C[b], off = (k - (a >= 0 ? a : b)) * w;
    C[k] = base.clone().addScaledVector(axis, off);
  }
  for (let it = 0; it < 2; it++)                      // smooth
    C = C.map((c, k) => (k === 0 || k === K - 1) ? c : c.clone().multiplyScalar(0.5).addScaledVector(C[k - 1], 0.25).addScaledVector(C[k + 1], 0.25));
  // 2. tangents, parallel-transported across vectors, arc length
  const T = C.map((c, k) => {
    const d = C[Math.min(K - 1, k + 1)].clone().sub(C[Math.max(0, k - 1)]);
    return d.lengthSq() > 1e-12 ? d.normalize() : axis.clone();
  });
  const B = [anyPerp(T[0])], S = [0];
  for (let k = 1; k < K; k++) {
    const b = B[k - 1].clone().sub(T[k].clone().multiplyScalar(B[k - 1].dot(T[k])));
    B.push(b.lengthSq() > 1e-12 ? b.normalize() : anyPerp(T[k]));
    S.push(S[k - 1] + C[k].distanceTo(C[k - 1]));
  }
  // 3. per-vertex frame by interpolating between bins
  const inv = new THREE.Matrix3().setFromMatrix4(toModel).invert();
  const q = new Float32Array(n * 3), ft = new Float32Array(n * 3), fb = new Float32Array(n * 3);
  const c = new THREE.Vector3(), t = new THREE.Vector3(), b = new THREE.Vector3(), nn = new THREE.Vector3(), d = new THREE.Vector3();
  for (let i = 0; i < n; i++) {
    if (!used[i]) continue;
    const x = Math.min(K - 1, Math.max(0, binOf(P[i]))), k0 = Math.min(K - 2, Math.floor(x)), f = x - k0;
    c.lerpVectors(C[k0], C[k0 + 1], f); t.lerpVectors(T[k0], T[k0 + 1], f).normalize();
    b.lerpVectors(B[k0], B[k0 + 1], f); b.sub(t.clone().multiplyScalar(b.dot(t))).normalize();
    nn.crossVectors(b, t);
    d.subVectors(P[i], c);
    const s = S[k0] + f * (S[k0 + 1] - S[k0]);
    q[i * 3] = d.dot(b); q[i * 3 + 1] = s + d.dot(t); q[i * 3 + 2] = d.dot(nn);
    const tl = t.clone().applyMatrix3(inv).normalize(), bl = b.clone().applyMatrix3(inv).normalize();
    ft.set([tl.x, tl.y, tl.z], i * 3); fb.set([bl.x, bl.y, bl.z], i * 3);
  }
  geom.setAttribute('fibreQ', new THREE.BufferAttribute(q, 3));
  geom.setAttribute('fibreT', new THREE.BufferAttribute(ft, 3));
  geom.setAttribute('fibreB', new THREE.BufferAttribute(fb, 3));
}
