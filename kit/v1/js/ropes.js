// Phase D2 nerves and vessels as light ropes (assets/wrap.json "ropes", built by tools/wrap_rope.py).
// Particles every ~5 mm on each centreline. Pinned particles follow their bone (or the soft tissue); free ones are
// carried with the tissue, pulled gently towards it, kept from stretching past their rest length unless the pins
// force it, and pushed out of simple bone shapes (head sphere, humeral shaft, clavicle, coracoid, thorax ellipsoid).
// The tube meshes are rebuilt from the particles after every pose change. Stretch = length now / rest length.
import * as THREE from 'three';

const V = (a) => new THREE.Vector3(...a), TOTAL = 300, PER_FRAME = 30, TETHER = 0.001;
const v1 = new THREE.Vector3(), v2 = new THREE.Vector3(), v3 = new THREE.Vector3();

export class Ropes {
  constructor(rig, d) {
    this.rig = rig; this.d = d; const n = d.p.length, B = rig.rig.bones;
    d.w = d.w.map((w) => { const t = w.reduce((x, y) => x + y, 0); return w.map((x) => x / t); });   // rounded in the file: sum exactly 1
    this.x0 = d.p.map(V); this.x = this.x0.map((p) => p.clone()); this.T = this.x0.map((p) => p.clone());
    this.pin = new Int8Array(n).fill(-2); for (const [i, b] of d.pin) this.pin[i] = b;     // -2 free, -1 tissue, >=0 bone
    this.dom = d.w.map((w) => w.indexOf(Math.max(...w)));
    this.L0 = d.seg.map(([a, b]) => this.x0[a].distanceTo(this.x0[b]));
    this.links = d.link.map(([a, b]) => [a, b, this.x0[a].distanceTo(this.x0[b])]);
    this.prev = new Int32Array(n).fill(-1); this.next = new Int32Array(n).fill(-1);
    for (const [a, b] of d.seg) { this.next[a] = b; this.prev[b] = a; }
    this.t0 = this.x0.map((_, i) => this.tangent(this.x0, i));
    this.pulleys = (d.pulley || []).map(([si, p, b]) => ({ p0: V(p), b, segs: d.seg.map((s, k) => k).filter((k) => d.s[d.seg[k][0]] === si) }));
    this.cols = d.colliders.map((c) => ({ ...c, bi: B.indexOf(c.bone), c: c.c && V(c.c), a: c.a && V(c.a), b: c.b && V(c.b),
      col: c.axes && [0, 1, 2].map((j) => new THREE.Vector3(c.axes[0][j], c.axes[1][j], c.axes[2][j])) }));
    this.bind();
  }

  tangent(X, i) {
    const a = this.prev[i] >= 0 ? X[this.prev[i]] : X[i], b = this.next[i] >= 0 ? X[this.next[i]] : X[i];
    return b.clone().sub(a).normalize();
  }

  // each tube vertex -> nearest segment of its own structure (a, b, t) + offset and normal in rest space
  bind() {
    const R = this.rig, gi = new THREE.Matrix4().copy(R.scene.matrixWorld).invert(); this.meshes = [];
    this.d.names.forEach((name, si) => {
      const s = R.A.byName.get(name); if (!s) return;
      const segs = this.d.seg.filter(([a]) => this.d.s[a] === si);
      for (const m of s.meshes) {
        if (!m.isSkinnedMesh) continue;
        const g = m.geometry, pos = g.attributes.position, nrm = g.attributes.normal, N = pos.count;
        const toG = new THREE.Matrix4().multiplyMatrices(gi, m.matrixWorld), nm = new THREE.Matrix3().getNormalMatrix(toG);
        const bnd = { m, toL: toG.clone().invert(), nmL: new THREE.Matrix3().getNormalMatrix(toG.clone().invert()),
          a: new Int32Array(N), b: new Int32Array(N), t: new Float32Array(N), off: [], nor: [] };
        for (let i = 0; i < N; i++) {
          const p = v1.fromBufferAttribute(pos, i).applyMatrix4(toG); let best = 1e9;
          for (const [a, b] of segs) {
            const A = this.x0[a], ab = v2.copy(this.x0[b]).sub(A), t = THREE.MathUtils.clamp(v3.copy(p).sub(A).dot(ab) / ab.lengthSq(), 0, 1);
            const d = v3.copy(A).addScaledVector(ab, t).distanceToSquared(p);
            if (d < best) { best = d; bnd.a[i] = a; bnd.b[i] = b; bnd.t[i] = t; }
          }
          bnd.off.push(p.clone().sub(v2.copy(this.x0[bnd.a[i]]).lerp(this.x0[bnd.b[i]], bnd.t[i])));
          bnd.nor.push(nrm ? new THREE.Vector3().fromBufferAttribute(nrm, i).applyMatrix3(nm).normalize() : new THREE.Vector3());
        }
        const si4 = g.attributes.skinIndex, sw4 = g.attributes.skinWeight;    // the tube now follows the ropes (thorax bone = no skinning)
        for (let i = 0; i < N; i++) { si4.setXYZW(i, 0, 0, 0, 0); sw4.setXYZW(i, 1, 0, 0, 0); }
        si4.needsUpdate = sw4.needsUpdate = true;
        g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pos.array), 3));
        if (nrm) g.setAttribute('normal', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
        this.meshes.push(bnd);
      }
    });
  }

  // D: {bone name: delta Matrix4 (glTF space)}. Starts the solve; step() keeps refining over the next frames.
  update(D) {
    const B = this.rig.rig.bones, Ds = this.Ds = B.map((b) => D[b]), n = this.x.length, d = this.d;
    for (let i = 0; i < n; i++) {
      const T = this.T[i].set(0, 0, 0), x0 = this.x0[i], w = d.w[i];
      if (this.pin[i] >= 0) T.copy(x0).applyMatrix4(Ds[this.pin[i]]);
      else for (let b = 0; b < w.length; b++) if (w[b]) T.addScaledVector(v1.copy(x0).applyMatrix4(Ds[b]), w[b]);
    }
    this.x.forEach((x, i) => x.copy(this.T[i]));          // start from the tissue: same pose -> same result
    this.cur = this.cols.map((c) => c.type === 'ellipsoid' ? c : { ...c, c: c.c && c.c.clone().applyMatrix4(Ds[c.bi]),
      a: c.a && c.a.clone().applyMatrix4(Ds[c.bi]), b: c.b && c.b.clone().applyMatrix4(Ds[c.bi]) });
    this.pul = this.pulleys.map((q) => q.p0.clone().applyMatrix4(Ds[q.b]));
    this.near = [];                                         // colliders each free particle can reach (within 4 cm now)
    for (let i = 0; i < n; i++) { const l = []; if (this.pin[i] < -1) this.cur.forEach((c, k) => { if (this.clear(c, this.x[i]) < d.need[i][k] + 0.04) l.push(k); }); this.near.push(l); }
    this.left = TOTAL; this.step(PER_FRAME);
  }

  // more solver passes (alternating direction so tension spreads along the chains); then rebuild the tubes
  step(k) {
    const d = this.d, X = this.x, n = X.length, S = d.seg, m = S.length, fixed = (i) => this.pin[i] > -2;
    for (let it = 0; it < k; it++) {
      const back = (this.left - it) % 2;
      for (let j = 0; j < m; j++) { const q = back ? m - 1 - j : j; this.limit(S[q][0], S[q][1], this.L0[q], fixed, false); }
      for (const [a, b, L] of this.links) this.limit(a, b, L, fixed, true);
      this.pulleys.forEach((q, i) => this.through(q.segs, this.pul[i], fixed));
      const hit = it % 2 === 1 || it === k - 1;
      for (let i = 0; i < n; i++) {
        if (fixed(i)) { X[i].copy(this.T[i]); continue; }
        X[i].lerp(this.T[i], TETHER);
        if (hit) for (const c of this.near[i]) this.collide(this.cur[c], X[i], d.need[i][c]);
      }
    }
    this.left -= k; this.rebuild(this.Ds);
  }

  limit(a, b, L, fixed, both) {
    const X = this.x, dv = v1.copy(X[b]).sub(X[a]), len = dv.length();
    if (len < 1e-9) return;
    const fa = fixed(a), fb = fixed(b); if (fa && fb) return;
    // shortening is resisted gently, so slack ropes bend instead of shrinking
    const k = (len - L) / len * (both || len > L ? 1 : 0.3), wa = fa ? 0 : fb ? 1 : 0.5, wb = fb ? 0 : fa ? 1 : 0.5;
    X[a].addScaledVector(dv, k * wa); X[b].addScaledVector(dv, -k * wb);
  }

  // pulley: the nearest segment of the rope is moved to pass through point P (the rope can slide through it)
  through(segs, P, fixed) {
    let best = 1e9, A = 0, Bi = 0, T = 0;
    for (const k of segs) {
      const [a, b] = this.d.seg[k], ab = v2.copy(this.x[b]).sub(this.x[a]);
      const t = THREE.MathUtils.clamp(v3.copy(P).sub(this.x[a]).dot(ab) / Math.max(ab.lengthSq(), 1e-12), 0, 1);
      const dd = v3.copy(this.x[a]).addScaledVector(ab, t).distanceToSquared(P);
      if (dd < best) { best = dd; A = a; Bi = b; T = t; }
    }
    const c = v1.copy(this.x[A]).lerp(this.x[Bi], T), e = v2.copy(P).sub(c), wa = fixed(A) ? 0 : 1 - T, wb = fixed(Bi) ? 0 : T;
    const s = wa * wa + wb * wb; if (s < 1e-9) return;
    this.x[A].addScaledVector(e, wa / s); this.x[Bi].addScaledVector(e, wb / s);
  }

  // signed clearance of x from collider c; leaves the outward direction (not unit) in v2
  clear(c, x) {
    if (c.type === 'sphere') { v2.copy(x).sub(c.c); return v2.length() - c.r; }
    if (c.type === 'capsule') {
      const ab = v3.copy(c.b).sub(c.a), t = THREE.MathUtils.clamp(v2.copy(x).sub(c.a).dot(ab) / ab.lengthSq(), 0, 1);
      v2.copy(x).sub(v3.copy(c.a).addScaledVector(ab, t)); return v2.length() - c.r;
    }
    v3.copy(x).sub(c.c); const C = c.col, r = c.r;
    const y0 = v3.dot(C[0]) / r[0], y1 = v3.dot(C[1]) / r[1], y2 = v3.dot(C[2]) / r[2];
    v2.copy(C[0]).multiplyScalar(y0 / r[0]).addScaledVector(C[1], y1 / r[1]).addScaledVector(C[2], y2 / r[2]);
    return (Math.sqrt(y0 * y0 + y1 * y1 + y2 * y2) - 1) * (c.rmin || (c.rmin = Math.min(r[0], r[1], r[2])));
  }

  collide(c, x, need) {
    const clr = this.clear(c, x); if (clr >= need) return;
    const l = v2.length(); if (l > 1e-9) x.addScaledVector(v2, (need - clr) / l);
  }

  rebuild(Ds) {
    const n = this.x.length, R = [], q = new THREE.Quaternion(), m3 = new THREE.Matrix3();
    for (let i = 0; i < n; i++) {
      const base = new THREE.Matrix4().extractRotation(Ds[this.pin[i] >= 0 ? this.pin[i] : this.dom[i]]);
      const t0 = this.t0[i].clone().applyMatrix4(base), t1 = this.tangent(this.x, i);
      R.push(new THREE.Matrix4().makeRotationFromQuaternion(q.setFromUnitVectors(t0, t1)).multiply(base));
    }
    for (const B of this.meshes) {
      const pos = B.m.geometry.attributes.position, nrm = B.m.geometry.attributes.normal;
      for (let i = 0; i < pos.count; i++) {
        const a = B.a[i], b = B.b[i], t = B.t[i];
        v1.copy(B.off[i]).applyMatrix4(R[a]).add(this.x[a]); v2.copy(B.off[i]).applyMatrix4(R[b]).add(this.x[b]);
        v1.lerp(v2, t).applyMatrix4(B.toL); pos.setXYZ(i, v1.x, v1.y, v1.z);
        if (nrm) { v1.copy(B.nor[i]).transformDirection(R[a]); v2.copy(B.nor[i]).transformDirection(R[b]);
          v1.lerp(v2, t).applyMatrix3(m3.copy(B.nmL)).normalize(); nrm.setXYZ(i, v1.x, v1.y, v1.z); }
      }
      pos.needsUpdate = true; if (nrm) nrm.needsUpdate = true;
      B.m.geometry.computeBoundingSphere(); B.m.geometry.computeBoundingBox();
    }
  }

  // stretch of one structure: whole length and the most stretched part between fixed points (%)
  stretch(name) {
    const si = this.d.names.indexOf(name); if (si < 0) return null;
    let L = 0, L0 = 0, s = 0, s0 = 0, worst = -1;
    const end = () => { if (s0 > 0.01) worst = Math.max(worst, s / s0 - 1); s = s0 = 0; };
    this.d.seg.forEach(([a, b], k) => {
      if (this.d.s[a] !== si) return;
      if (this.prev[a] < 0 || this.pin[a] > -2) end();
      const l = this.x[a].distanceTo(this.x[b]); L += l; L0 += this.L0[k]; s += l; s0 += this.L0[k];
    });
    end(); return { whole: L / L0 - 1, part: worst };
  }
}
