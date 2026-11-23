// Realistic view: one MeshPhysicalMaterial per tissue (wet clearcoat, triplanar KTX2 detail maps with
// fibres along each structure), a Poly Haven HDRI and an overhead operating-theatre light.
// Settings: assets/tissues.json. The "present" view (looks.js) stays as it was.
import * as THREE from 'three';
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';
import { addFibreFrames } from './fibres.js';

const BASIS = 'https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/basis/';

const VERT_HEAD = /* glsl */`
uniform mat4 uNoiseMat; uniform float uTile; uniform vec3 uFrameT, uFrameB;
varying vec3 vTq, vFT, vFB;
#ifdef FIBRE
attribute vec3 fibreQ, fibreT, fibreB;
#endif
`;
const VERT_BODY = /* glsl */`
#ifdef FIBRE
  vTq = fibreQ * uTile; vec3 fT = fibreT, fB = fibreB;
#else
  vTq = (uNoiseMat * vec4(transformed, 1.0)).xyz * uTile; vec3 fT = uFrameT, fB = uFrameB;
#endif
  vFT = normalize(mat3(modelViewMatrix) * fT); vFB = normalize(mat3(modelViewMatrix) * fB);
`;
const FRAG_HEAD = /* glsl */`
uniform sampler2D uTex; uniform float uBump, uCav, uRVar; uniform vec3 uCut;
varying vec3 vTq, vFT, vFB;
vec3 tnrm(vec4 t, float sx) { vec2 xy = (t.xy * 2.0 - 1.0) * uBump; xy.x *= sx;
  return vec3(xy, sqrt(max(0.0, 1.0 - dot(xy, xy)))); }
`;
// Triplanar in the fibre frame (B = across, T = along, N = across). Texture fibres run along v,
// so the two side projections (zy, xy) put fibres along T. Whiteout blend (Golus 2017).
const FRAG_BODY = /* glsl */`
{
  vec3 Bv = normalize(vFB), Tv = normalize(vFT - Bv * dot(vFT, Bv)), Nv = cross(Bv, Tv);
  vec3 nf = vec3(dot(normal, Bv), dot(normal, Tv), dot(normal, Nv));
  vec3 w = pow(abs(nf), vec3(4.0)); w /= (w.x + w.y + w.z);
  vec3 sg = vec3(nf.x < 0.0 ? -1.0 : 1.0, nf.y < 0.0 ? -1.0 : 1.0, nf.z < 0.0 ? -1.0 : 1.0);
  vec4 tX = texture2D(uTex, vec2(vTq.z * sg.x, vTq.y));
  vec4 tY = texture2D(uTex, vec2(vTq.x * sg.y, vTq.z));
  vec4 tZ = texture2D(uTex, vec2(-vTq.x * sg.z, vTq.y));
  vec3 nX = tnrm(tX, sg.x), nY = tnrm(tY, sg.y), nZ = tnrm(tZ, -sg.z);
  nX = vec3(nX.xy + nf.zy, abs(nX.z) * nf.x);
  nY = vec3(nY.xy + nf.xz, abs(nY.z) * nf.y);
  nZ = vec3(nZ.xy + nf.xy, abs(nZ.z) * nf.z);
  vec3 nn = normalize(nX.zyx * w.x + nY.xzy * w.y + nZ.xyz * w.z);
  normal = normalize(Bv * nn.x + Tv * nn.y + Nv * nn.z);
  float cav = tX.b * w.x + tY.b * w.y + tZ.b * w.z;
  diffuseColor.rgb *= 1.0 + uCav * (cav * 2.0 - 1.0);
  roughnessFactor = clamp(roughnessFactor + uRVar * (0.5 - cav), 0.04, 1.0);
}
`;

function patch(shader, mat) {
  Object.assign(shader.uniforms, mat.userData.u);
  shader.vertexShader = shader.vertexShader
    .replace('#include <common>', '#include <common>\n' + VERT_HEAD)
    .replace('#include <begin_vertex>', '#include <begin_vertex>\n' + VERT_BODY);
  shader.fragmentShader = shader.fragmentShader
    .replace('#include <common>', '#include <common>\n' + FRAG_HEAD)
    .replace('#include <normal_fragment_maps>', '#include <normal_fragment_maps>\n' + FRAG_BODY)
    .replace('#include <opaque_fragment>', 'if (!gl_FrontFacing) outgoingLight = uCut;\n#include <opaque_fragment>');
}

// Structure name (+ layer, glTF material name) -> tissue key, or null to keep the present look.
export function tissueOf(cfg, name, layer, matName, kind) {
  if (layer === 'attachment' || kind) return null;
  const m = matName || '';
  if (m.includes('Cartilage')) return 'cartilage';
  if (m === 'Tendon') return 'tendon';
  if (m === 'Nail') return 'nail';
  if (cfg.overrides[name]) return cfg.overrides[name];
  for (const [re, t] of cfg.rules) if (new RegExp(re, 'i').test(name)) return t;
  return cfg.layerDefault[layer] || null;
}

export class Realism {
  constructor(app) {
    this.app = app; this.view = 'present'; this.ready = false; this.busy = false; this.status = '';
    this.present = { env: app.scene.environment, hemi: app.lights.hemi.intensity, sun: app.lights.sun.intensity };
  }

  async load() {
    if (this.ready || this.busy) return this.loading;
    this.busy = true; this.status = 'loading…'; this.app.menus.refresh();
    this.loading = (async () => {
      const cfg = this.cfg = await fetch('assets/tissues.json', { cache: 'no-cache' }).then((r) => r.json());
      const { renderer, scene } = this.app;
      const ktx = new KTX2Loader().setTranscoderPath(BASIS).detectSupport(renderer);
      const names = [...new Set(Object.values(cfg.tissues).map((t) => t.tex))];
      const tex = {};
      await Promise.all(names.map((n) => ktx.loadAsync('assets/tex/' + n + '.ktx2').then((t) => {
        t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.NoColorSpace;
        t.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy()); tex[n] = t;
      })));
      this.env = await new RGBELoader().loadAsync(cfg.hdri).then((h) => {
        h.mapping = THREE.EquirectangularReflectionMapping;
        const pm = new THREE.PMREMGenerator(renderer), rt = pm.fromEquirectangular(h);
        h.dispose(); pm.dispose(); return rt.texture;
      }).catch(() => { console.warn('HDRI not found:', cfg.hdri, '- using built-in room light'); return this.present.env; });
      const L = cfg.otLight;
      this.ot = new THREE.SpotLight(L.color, 0, 0, THREE.MathUtils.degToRad(L.angle), L.penumbra, 2);
      scene.add(this.ot, this.ot.target);
      this.buildMaterials(tex);
      ktx.dispose();
      this.ready = true; this.busy = false; this.status = '';
    })().catch((e) => { this.busy = false; this.status = 'failed: ' + e.message; console.error(e); this.app.menus.refresh(); });
    return this.loading;
  }

  buildMaterials(tex) {
    const A = this.app.anatomy, cfg = this.cfg, base = {};
    for (const [k, T] of Object.entries(cfg.tissues)) {
      base[k] = new THREE.MeshPhysicalMaterial({ color: new THREE.Color(T.color), roughness: T.roughness, metalness: 0,
        clearcoat: T.clearcoat, clearcoatRoughness: T.clearcoatRoughness, ior: 1.4, envMapIntensity: cfg.envIntensity });
      base[k].name = 'tissue:' + k;
    }
    const counts = {}; this.mats = [];
    for (const s of A.structs) for (const m of s.meshes) {
      const pm = m.userData.mats.present, key = tissueOf(cfg, s.name, s.layer, m.userData.gltfMat, s.kind);
      if (!key || !base[key]) { m.userData.mats.real = pm; continue; }
      const T = cfg.tissues[key], nm = pm.userData.u.uNoiseMat.value, op = T.opacity ?? 1;
      const mat = base[key].clone();
      mat.clippingPlanes = pm.clippingPlanes; mat.side = pm.side;
      mat.transparent = op < 1; mat.depthWrite = op >= 1;
      if (T.fibre) { addFibreFrames(m.geometry, nm); mat.defines = { ...mat.defines, FIBRE: 1 }; }
      const inv = new THREE.Matrix3().setFromMatrix4(nm).invert();
      mat.userData = { key, baseOpacity: op, u: {
        uNoiseMat: { value: nm }, uTile: { value: 1000 / T.tile }, uTex: { value: tex[T.tex] },
        uFrameT: { value: new THREE.Vector3(0, 1, 0).applyMatrix3(inv).normalize() },
        uFrameB: { value: new THREE.Vector3(1, 0, 0).applyMatrix3(inv).normalize() },
        uBump: { value: T.bump }, uCav: { value: T.cavity }, uRVar: { value: T.roughVar },
        uCut: { value: new THREE.Color(T.color).multiplyScalar(0.8) } } };
      mat.onBeforeCompile = (sh) => patch(sh, mat);
      mat.customProgramCacheKey = () => 'tissue' + (T.fibre ? 'F' : 'I');
      m.userData.mats.real = mat; this.mats.push(mat); counts[key] = (counts[key] || 0) + 1;
    }
    console.log('realistic materials per tissue:', counts);
    A.skinReal = cfg.tissues.skin;
  }

  // Palette = tissues.json "tissues" + the overrides in "palettes"[name].tissues (living = no overrides).
  tissue(key) { return { ...this.cfg.tissues[key], ...(this.cfg.palettes?.[this.palette]?.tissues?.[key] || {}) }; }
  applyPalette(name) {
    this.palette = name;
    for (const mat of this.mats) {
      const T = this.tissue(mat.userData.key), u = mat.userData.u;
      mat.color.set(T.color); mat.roughness = T.roughness;
      mat.clearcoat = T.clearcoat; mat.clearcoatRoughness = T.clearcoatRoughness;
      u.uBump.value = T.bump; u.uCav.value = T.cavity; u.uRVar.value = T.roughVar;
      u.uCut.value.set(T.color).multiplyScalar(0.8);
    }
    this.app.anatomy.skinReal = this.tissue('skin');
  }

  // 'present' | 'realistic' (living palette) | 'cadaver' (realistic view, cadaver palette)
  async setView(v) {
    if (v !== 'present' && !this.ready) { await this.load(); if (!this.ready) return; }
    this.view = v;
    const real = v !== 'present', { scene, lights } = this.app, cfg = this.cfg;
    if (real) this.applyPalette(v === 'cadaver' ? 'cadaver' : 'living');
    scene.environment = real ? this.env : this.present.env;
    scene.environmentRotation.set(0, real ? THREE.MathUtils.degToRad(cfg.hdriRotation || 0) : 0, 0);
    lights.hemi.intensity = real ? cfg.fillLights.hemisphere : this.present.hemi;
    lights.sun.intensity = real ? cfg.fillLights.directional : this.present.sun;
    if (this.ot) this.ot.intensity = real ? cfg.otLight.intensity : 0;
    this.app.anatomy.setView(real ? 'realistic' : 'present');
    this.app.menus.refresh();
  }
  toggle() { return this.setView({ present: 'realistic', realistic: 'cadaver' }[this.view] || 'present'); }

  // Keep the OT light above the model (world space), slightly towards the viewer.
  update() {
    if (!this.ot || this.view !== 'realistic') return;
    const L = this.cfg.otLight, root = this.app.root, cam = this.app.renderer.xr.isPresenting
      ? this.app.renderer.xr.getCamera() : this.app.camera;
    const p = root.getWorldPosition(new THREE.Vector3()), eye = cam.getWorldPosition(new THREE.Vector3());
    const toward = eye.sub(p).setY(0); if (toward.lengthSq() > 1e-6) toward.normalize();
    this.ot.position.copy(p).add(new THREE.Vector3(0, L.height, 0)).addScaledVector(toward, L.towardViewer);
    this.ot.target.position.copy(p);
  }
}
