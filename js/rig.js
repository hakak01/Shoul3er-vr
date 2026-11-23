// Phase D1 movement: ISB angles -> bone rotations (assets/rig.json), scapulohumeral rhythm (assets/rhythm.json),
// muscle bulge (cross-section x sqrt(rest length / length)) and ligament tension colours (look.json "tension").
// Humerus = humerothoracic plane / elevation / rotation (swing, then twist; ER +). Scapula and clavicle: ISB Y-X-Z.
import * as THREE from 'three';

const R = THREE.MathUtils.degToRad, V = (a) => new THREE.Vector3(...a);
const M = () => new THREE.Matrix4();
const basis = (F) => M().makeBasis(V([F[0][0], F[1][0], F[2][0]]), V([F[0][1], F[1][1], F[2][1]]), V([F[0][2], F[1][2], F[2][2]]));
const yxz = (a, b, c) => M().makeRotationY(R(a)).multiply(M().makeRotationX(R(b))).multiply(M().makeRotationZ(R(c)));
const interp = (k, x) => {
  if (x <= k[0][0]) return k[0][1];
  for (let i = 1; i < k.length; i++) if (x <= k[i][0]) { const [x0, y0] = k[i - 1], [x1, y1] = k[i]; return y0 + (y1 - y0) * (x - x0) / (x1 - x0); }
  return k[k.length - 1][1];
};
export const ST_KEYS = [['clavicle', 'retraction'], ['clavicle', 'elevation'], ['clavicle', 'posteriorRotation'],
  ['scapula', 'upwardRotation'], ['scapula', 'posteriorTilt'], ['scapula', 'externalRotation']];

const VERT = /* glsl */`
#ifdef RIG_BULGE
{ vec3 ab = uBB - uBA; float t = clamp(dot(transformed - uBA, ab) / max(dot(ab, ab), 1e-10), 0.0, 1.0);
  vec3 c = uBA + ab * t; transformed = c + (transformed - c) * (1.0 + (uBulge - 1.0) * sin(3.14159 * t)); }
#endif
#ifdef RIG_TEN
vTen = uTen[int(rigSector + 0.5)];
#endif
`;
const FRAG = /* glsl */`
#ifdef RIG_TEN
if (uTenOn > 0.5) diffuseColor.rgb = vTen < uTenAt.x ? mix(uTenC0, uTenC1, clamp(vTen / uTenAt.x, 0.0, 1.0))
  : mix(uTenC1, uTenC2, clamp((vTen - uTenAt.x) / (uTenAt.y - uTenAt.x), 0.0, 1.0));
#endif
`;

// Call right after loading, before Anatomy: meshopt folds position quantization into each file's inverse bind
// matrices. Undo that (positions back to metres, so tissue patterns keep their scale) and bind every skinned
// mesh of all files to one skeleton (the first file's bones) with plain inverse bind matrices.
export function prepareSkins(scene) {
  scene.updateMatrixWorld(true);
  const sk = []; scene.traverse((o) => { if (o.isSkinnedMesh) sk.push(o); });
  if (!sk.length) return;
  const bones = sk[0].skeleton.bones, shared = new THREE.Skeleton(bones, bones.map((b) => M().copy(b.matrixWorld).invert()));
  const v = new THREE.Vector3();
  for (const m of sk) {
    const Q = M().copy(m.matrixWorld).invert().multiply(m.skeleton.bones[0].matrixWorld).multiply(m.skeleton.boneInverses[0])
      .multiply(m.bindMatrix);
    const pos = m.geometry.attributes.position, a = new Float32Array(pos.count * 3);
    for (let i = 0; i < pos.count; i++) v.fromBufferAttribute(pos, i).applyMatrix4(Q).toArray(a, i * 3);
    m.geometry.setAttribute('position', new THREE.BufferAttribute(a, 3));
    m.geometry.computeBoundingBox(); m.geometry.computeBoundingSphere();
    m.bind(shared, m.matrixWorld); m.frustumCulled = false;
  }
}

export class Rig {
  constructor(app, rig, rhythm, look) {
    this.app = app; this.A = app.anatomy; this.rig = rig; this.rh = rhythm; this.lim = rhythm.limits;
    this.scene = this.A.center.children[0];
    const skinned = []; this.A.center.traverse((o) => { if (o.isSkinnedMesh) skinned.push(o); });
    this.ok = skinned.length > 0; if (!this.ok) { console.warn('no skinned meshes: run tools/build_rig.py'); return; }
    this.skel = skinned[0].skeleton;
    this.skinned = skinned;
    this.bone = {}; this.skel.bones.forEach((b, i) => { this.bone[(b.userData.name || b.name).replace(/^rig:?/, '')] = b; b.userData.i = i; });
    const F = rig.frames; this.F = {}; for (const k in F) this.F[k] = basis(F[k]);
    this.ax = { elbow: V(rig.axes.elbow).normalize(), forearm: V(rig.axes.forearm).normalize() };
    const r = rig.rest; this.rest = r;
    this.p = { plane: r.humerus[0], elev: r.humerus[1], rot: r.humerus[2], elbow: r.elbowFlexion, sup: r.supination };
    this.home = { ...this.p };
    this.manual = false; this.st = this.rhythmAt(this.p.elev); this.tensionOn = false;
    const T = look.tension || {};
    this.tu = { uTenOn: { value: 0 }, uTenAt: { value: new THREE.Vector2(T.midAt ?? 0.04, T.tightAt ?? 0.08) },
      uTenC0: { value: new THREE.Color(T.slack || '#8c8c8c') }, uTenC1: { value: new THREE.Color(T.mid || '#f2c400') },
      uTenC2: { value: new THREE.Color(T.tight || '#e02a1b') } };
    this.setup(); this.dirty = true;
  }

  // per-mesh uniforms for bulge (muscles) and tension (ligaments with fibre data); labels follow their bone
  setup() {
    const g = this.scene, gi = M().copy(g.matrixWorld).invert(), v = new THREE.Vector3();
    this.mus = []; this.ligs = [];
    for (const s of this.A.structs) {
      const ml = this.rig.muscles[s.name], lg = this.rig.ligaments[s.name];
      for (const m of s.meshes) {
        if (!m.isSkinnedMesh) continue;
        const u = m.userData.rigU = {}, defs = [];
        if (ml && s.layer === 'muscle') {
          Object.assign(u, { uBA: { value: new THREE.Vector3() }, uBB: { value: new THREE.Vector3() }, uBulge: { value: 1 } });
          this.mus.push({ m, u, a: V(ml.a), b: V(ml.b), ba: this.bone[ml.ba], bb: this.bone[ml.bb], L0: V(ml.a).distanceTo(V(ml.b)) });
          defs.push('RIG_BULGE');
        }
        if (s.layer === 'ligament_capsule') {
          const pos = m.geometry.attributes.position, sec = new Float32Array(pos.count), toG = M().multiplyMatrices(gi, m.matrixWorld);
          if (lg) {
            const c = V(lg.c), uu = V(lg.u), rr = V(lg.r), q = uu.clone().cross(rr);
            for (let i = 0; i < pos.count; i++) {
              v.fromBufferAttribute(pos, i).applyMatrix4(toG).sub(c);
              sec[i] = Math.floor((Math.atan2(v.dot(q), v.dot(rr)) + Math.PI) / (2 * Math.PI) * lg.n) % lg.n;
            }
            this.ligs.push({ s, u, lg, b1: this.bone[lg.bones[0]], b2: this.bone[lg.bones[1]],
              fib: lg.fib.map(([p1, p2, L]) => ({ p1: V(p1), p2: V(p2), L0: L || V(p1).distanceTo(V(p2)) })) });
          }
          m.geometry.setAttribute('rigSector', new THREE.BufferAttribute(sec, 1));
          Object.assign(u, this.tu, { uTen: { value: new Float32Array(8) } }); defs.push('RIG_TEN');
        }
        if (defs.length) for (const mat of [m.userData.mats.present, m.userData.mats.real]) this.decorate(m, mat);
      }
    }
    this.labels = (this.A.labels ? this.A.labels.items : []).map((it) => ({ it, b: this.bone[this.rig.dominant[it.s.name] || 'thorax'],
      sp: it.sp.position.clone(), ln: it.line.geometry.attributes.position.array.slice() }));
  }

  // add the movement shader code to one material of mesh m (also called by tissues.js for realistic materials)
  decorate(m, mat) {
    const u = m.userData.rigU; if (!mat || !u || mat.userData.rigDone) return;
    mat.userData.rigDone = true;
    const flags = (u.uBulge ? 'B' : '') + (u.uTen ? 'T' : ''), prev = mat.onBeforeCompile, key = mat.customProgramCacheKey;
    mat.onBeforeCompile = (sh, r) => {
      prev.call(mat, sh, r); Object.assign(sh.uniforms, u);
      const head = (u.uBulge ? '#define RIG_BULGE\nuniform vec3 uBA, uBB; uniform float uBulge;\n' : '') +
        (u.uTen ? '#define RIG_TEN\nattribute float rigSector; uniform float uTen[8]; varying float vTen;\n' : '');
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\n' + head)
        .replace('#include <skinning_vertex>', '#include <skinning_vertex>\n' + VERT);
      if (u.uTen) sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\n#define RIG_TEN\n' +
        'varying float vTen; uniform float uTenOn; uniform vec2 uTenAt; uniform vec3 uTenC0, uTenC1, uTenC2;\n')
        .replace('#include <color_fragment>', '#include <color_fragment>\n' + FRAG);
    };
    mat.customProgramCacheKey = () => key.call(mat) + 'rig' + flags;
    mat.needsUpdate = true;
  }

  // scapula / clavicle changes (deg, anatomical +) from the rhythm, relative to the model's rest elevation
  rhythmAt(e) {
    const o = {}, e0 = this.rest.humerus[1];
    for (const [seg, k] of ST_KEYS) o[seg + '.' + k] = interp(this.rh[seg][k], e) - interp(this.rh[seg][k], e0);
    return o;
  }
  maxElev(plane) { return interp(this.lim.maxElevationByPlane, plane); }
  clamp() {
    const p = this.p, L = this.lim, c = THREE.MathUtils.clamp;
    p.plane = c(p.plane, ...L.plane); p.elev = c(p.elev, L.elevation[0], Math.min(L.elevation[1], this.maxElev(p.plane)));
    p.rot = c(p.rot, ...L.rotation); p.elbow = c(p.elbow, Math.min(L.elbow[0], this.rest.elbowFlexion), L.elbow[1]);
    p.sup = c(p.sup, L.supination[0], Math.max(L.supination[1], this.rest.supination));
  }
  set(vals) { Object.assign(this.p, vals); this.clamp(); this.dirty = true; }
  setST(key, v) { this.st[key] = v; this.dirty = true; }
  setManual(on) { if (on && !this.manual) this.st = this.rhythmAt(this.p.elev); this.manual = on; this.dirty = true; }
  setTension(on) { this.tensionOn = on; this.tu.uTenOn.value = on ? 1 : 0; }

  // humerothoracic rotation (thorax axes) from plane / elevation / rotation
  ht(p) {
    return M().makeRotationY(R(p.plane)).multiply(M().makeRotationX(R(-p.elev))).multiply(M().makeRotationY(R(-p.plane)))
      .multiply(M().makeRotationY(R(-p.rot)));
  }
  // bone delta rotations (glTF space, relative to rest)
  deltas() {
    const r = this.rest, p = this.p, d = this.manual ? this.st : this.rhythmAt(p.elev), F = this.F, Ft = F.thorax;
    const seg = (rel, Fs) => M().multiplyMatrices(Ft, rel).multiply(M().copy(Fs).transpose());
    const Q = { thorax: M() };
    Q.clavicle = seg(yxz(r.clavicle[0] - d['clavicle.retraction'], r.clavicle[1] - d['clavicle.elevation'],
      r.clavicle[2] + d['clavicle.posteriorRotation']), F.clavicle);
    Q.scapula = seg(yxz(r.scapula[0] - d['scapula.externalRotation'], r.scapula[1] - d['scapula.upwardRotation'],
      r.scapula[2] + d['scapula.posteriorTilt']), F.scapula);
    Q.humerus = seg(this.ht(p), F.humerus);
    Q.ulna = M().copy(Q.humerus).multiply(M().makeRotationAxis(this.ax.elbow, R(p.elbow - r.elbowFlexion)));
    Q.radius = M().copy(Q.ulna).multiply(M().makeRotationAxis(this.ax.forearm, R(p.sup - r.supination)));
    return Q;
  }

  update() {
    if (!this.ok || !this.dirty) return;
    this.dirty = false;
    const Q = this.deltas(), q = new THREE.Quaternion(), names = this.rig.bones;
    names.forEach((n, i) => {
      const par = this.rig.parents[i];
      const loc = par < 0 ? Q[n] : M().copy(Q[names[par]]).transpose().multiply(Q[n]);
      this.bone[n].quaternion.copy(q.setFromRotationMatrix(loc));
    });
    this.A.root.updateMatrixWorld(true);
    const D = this.D = {}, gi = M().copy(this.scene.matrixWorld).invert();
    for (const n of names) { const b = this.bone[n]; D[n] = M().multiplyMatrices(gi, b.matrixWorld).multiply(this.skel.boneInverses[b.userData.i]); }
    const dOf = (b) => D[names[b.userData.i]], w = new THREE.Vector3(), z = new THREE.Vector3();
    for (const x of this.mus) {
      w.copy(x.a).applyMatrix4(dOf(x.ba)); z.copy(x.b).applyMatrix4(dOf(x.bb));
      x.r = w.distanceTo(z) / x.L0; x.k = THREE.MathUtils.clamp(Math.sqrt(1 / Math.max(x.r, 1e-3)), 0.85, 1.3);
      const toM = M().copy(x.m.matrixWorld).invert().multiply(this.scene.matrixWorld);
      x.u.uBA.value.copy(w).applyMatrix4(toM); x.u.uBB.value.copy(z).applyMatrix4(toM); x.u.uBulge.value = x.k;
    }
    for (const x of this.ligs) {
      x.e = x.fib.map((f) => w.copy(f.p1).applyMatrix4(dOf(x.b1)).distanceTo(z.copy(f.p2).applyMatrix4(dOf(x.b2))) / f.L0 - 1);
      x.u.uTen.value.set(x.e.map((e) => Math.max(e, 0)));
    }
    for (const L of this.labels) {
      const d = dOf(L.b), a = L.it.line.geometry.attributes.position;
      L.it.sp.position.copy(L.sp).applyMatrix4(d);
      for (let i = 0; i < 2; i++) { w.fromArray(L.ln, i * 3).applyMatrix4(d); a.setXYZ(i, w.x, w.y, w.z); }
      a.needsUpdate = true;
    }
    for (const m of this.skinned) { m.boundingSphere = null; m.boundingBox = null; }
    this.app.onPose && this.app.onPose();
  }

  // VR: squeeze near the forearm (elbow -> wrist, within 6 cm) to swing the arm with the controller
  tryGrab(pt) {
    if (!this.ok || !this.D) return false;
    const L = this.rig.landmarks, d = this.D.ulna, w = (p) => this.scene.localToWorld(p.applyMatrix4(d));
    const a = w(V(this.rig.joints.ulna)), b = w(V(L.US).add(V(L.RS)).multiplyScalar(0.5));
    const t = THREE.MathUtils.clamp(pt.clone().sub(a).dot(b.clone().sub(a)) / b.distanceToSquared(a), 0, 1);
    const s = this.scene.getWorldScale(new THREE.Vector3()).x;
    if (pt.distanceTo(a.lerp(b, t)) > 0.06 * s) return false;
    this.grab = this.bone.humerus.worldToLocal(pt.clone()); return true;
  }
  dragTo(pt) {
    const hb = this.bone.humerus, gh = hb.getWorldPosition(new THREE.Vector3());
    const cur = hb.localToWorld(this.grab.clone()).sub(gh).normalize(), to = pt.clone().sub(gh).normalize();
    const gq = this.scene.getWorldQuaternion(new THREE.Quaternion());
    const q = gq.clone().invert().multiply(new THREE.Quaternion().setFromUnitVectors(cur, to)).multiply(gq);
    const Rh = M().copy(this.F.thorax).transpose().multiply(M().makeRotationFromQuaternion(q))
      .multiply(this.deltas().humerus).multiply(this.F.humerus), e = Rh.elements;
    const dx = -e[4], dy = -e[5], dz = -e[6], elev = THREE.MathUtils.radToDeg(Math.acos(THREE.MathUtils.clamp(-dy, -1, 1)));
    const plane = elev > 2 ? THREE.MathUtils.radToDeg(Math.atan2(dx, dz)) : this.p.plane;
    const T = M().copy(this.ht({ plane, elev, rot: 0 })).transpose().multiply(Rh).elements;
    this.set({ plane, elev, rot: -THREE.MathUtils.radToDeg(Math.atan2(T[8], T[0])) });
  }

  // one line for the info panel: ligament stretch or muscle length vs the neutral (rest) pose
  info(s) {
    const l = this.ok && this.ligs.find((x) => x.s === s);
    if (l && l.e) return 'Stretch vs neutral: ' + (100 * Math.max(...l.e)).toFixed(1) + '% (most stretched part)';
    const m = this.ok && this.mus.find((x) => x.m.userData.struct === s);
    if (m && m.r) return 'Length vs neutral (origin-insertion line): ' + (100 * (m.r - 1)).toFixed(0) + '%';
    return '';
  }
}
