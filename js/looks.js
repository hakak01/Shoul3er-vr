// Procedural tissue materials (no textures). Colours/roughness come from assets/look.json.
import * as THREE from 'three';

const PATTERNS = { none: 0, porous: 1, fibre: 2, fascicle: 3, mottle: 4, lobule: 5 };

const NOISE = /* glsl */`
uniform vec3 uAxis; uniform float uScale; uniform float uAlong; uniform float uStrength; uniform vec3 uCut;
varying vec3 vNPos;
float hsh(vec3 p){ p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float vnoise(vec3 x){ vec3 i = floor(x); vec3 f = fract(x); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(hsh(i), hsh(i + vec3(1,0,0)), f.x), mix(hsh(i + vec3(0,1,0)), hsh(i + vec3(1,1,0)), f.x), f.y),
             mix(mix(hsh(i + vec3(0,0,1)), hsh(i + vec3(1,0,1)), f.x), mix(hsh(i + vec3(0,1,1)), hsh(i + vec3(1,1,1)), f.x), f.y), f.z); }
`;

const PATTERN_CODE = /* glsl */`
float patN = 0.5;
#if PATTERN == 1
  { vec3 p = vNPos * uScale; patN = vnoise(p) * 0.6 + vnoise(p * 2.7) * 0.4;
    float pore = smoothstep(0.70, 0.86, patN);
    diffuseColor.rgb *= 1.0 - uStrength * (0.6 * patN + 1.6 * pore); }
#elif PATTERN == 2 || PATTERN == 3
  { float s = dot(vNPos, uAxis); vec3 q = vNPos - s * uAxis;
    vec3 fp = q * uScale + uAxis * (s * uAlong);
    patN = vnoise(fp) * 0.7 + vnoise(fp * 2.3) * 0.3;
  #if PATTERN == 3
    patN = smoothstep(0.35, 0.65, patN);
  #endif
    diffuseColor.rgb *= 1.0 + uStrength * (patN * 2.0 - 1.0); }
#elif PATTERN == 4
  { vec3 p = vNPos * uScale; patN = vnoise(p) * 0.5 + vnoise(p * 3.1) * 0.5;
    diffuseColor.rgb *= 1.0 + uStrength * (patN * 2.0 - 1.0); }
#elif PATTERN == 5
  { vec3 p = vNPos * uScale, i = floor(p), f = fract(p); float d1 = 8.0, d2 = 8.0;   // fat lobules (cells)
    for (int z = -1; z <= 1; z++) for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) {
      vec3 g = vec3(x, y, z), o = vec3(hsh(i + g), hsh(i + g + 7.1), hsh(i + g + 13.7));
      float d = length(g + o - f); if (d < d1) { d2 = d1; d1 = d; } else if (d < d2) d2 = d; }
    float septum = 1.0 - smoothstep(0.03, 0.12, d2 - d1);
    patN = 1.0 - d1 * 0.6;
    diffuseColor.rgb *= (1.0 - uStrength * septum) * (0.9 + 0.2 * patN); }
#endif
`;

function patch(shader, mat) {
  const u = mat.userData.u;
  Object.assign(shader.uniforms, u);
  shader.defines = shader.defines || {};
  shader.defines.PATTERN = mat.userData.pattern;
  shader.vertexShader = shader.vertexShader
    .replace('#include <common>', '#include <common>\nuniform mat4 uNoiseMat; varying vec3 vNPos;')
    .replace('#include <begin_vertex>', '#include <begin_vertex>\nvNPos = (uNoiseMat * vec4(transformed, 1.0)).xyz;');
  shader.fragmentShader = shader.fragmentShader
    .replace('#include <common>', '#include <common>\n' + NOISE)
    .replace('#include <color_fragment>', '#include <color_fragment>\n' + PATTERN_CODE)
    .replace('#include <roughnessmap_fragment>',
      '#include <roughnessmap_fragment>\nroughnessFactor = clamp(roughnessFactor + uStrength * (patN - 0.5), 0.04, 1.0);')
    .replace('#include <opaque_fragment>',
      'if (!gl_FrontFacing) outgoingLight = uCut;\n#include <opaque_fragment>');
}

// Which look a mesh gets: by glTF material name first, then by layer.
export function lookKey(layer, matName, kind, structName) {
  const m = matName || '';
  if (layer === 'attachment') return kind === 'origin' ? 'origin' : 'insertion';
  if (m.includes('Cartilage')) return 'cartilage';
  if (m === 'Tendon') return 'tendon';
  if (layer === 'skin') return (m === 'Nail' || /Nail/.test(structName)) ? 'nail' : 'skin';
  return { bone: 'bone', muscle: 'muscle', ligament_capsule: 'ligament', fascia_retinacula: 'fascia',
    tendon_sheath: 'sheath', nerve: 'nerve', artery: 'artery', vein: 'vein', fat: 'fat' }[layer] || 'ligament';
}

// Main direction of a mesh (for lengthwise fibres), in model space.
function principalAxis(geom, m) {
  const pos = geom.attributes.position, n = pos.count, step = Math.max(1, Math.floor(n / 1500));
  const v = new THREE.Vector3(), mean = new THREE.Vector3(), pts = [];
  for (let i = 0; i < n; i += step) { v.fromBufferAttribute(pos, i).applyMatrix4(m); pts.push(v.clone()); mean.add(v); }
  mean.divideScalar(pts.length);
  const c = [0, 0, 0, 0, 0, 0]; // xx xy xz yy yz zz
  for (const p of pts) {
    const x = p.x - mean.x, y = p.y - mean.y, z = p.z - mean.z;
    c[0] += x * x; c[1] += x * y; c[2] += x * z; c[3] += y * y; c[4] += y * z; c[5] += z * z;
  }
  let a = new THREE.Vector3(0.3, 1, 0.2).normalize();
  for (let k = 0; k < 30; k++) {
    a = new THREE.Vector3(c[0] * a.x + c[1] * a.y + c[2] * a.z, c[1] * a.x + c[3] * a.y + c[4] * a.z,
      c[2] * a.x + c[4] * a.y + c[5] * a.z);
    if (a.lengthSq() === 0) return new THREE.Vector3(0, 1, 0);
    a.normalize();
  }
  return a;
}

// noiseMat: mesh -> model space (metres). clipPlanes: shared array.
export function makeMaterial(look, key, mesh, noiseMat, clipPlanes) {
  const L = look.looks[key];
  const mat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(L.color), roughness: L.roughness, metalness: 0,
    transparent: L.opacity < 1, opacity: L.opacity, depthWrite: L.opacity >= 1,
    clippingPlanes: clipPlanes, envMapIntensity: 0.7,
  });
  if (key === 'origin' || key === 'insertion') {
    mat.polygonOffset = true; mat.polygonOffsetFactor = -2; mat.polygonOffsetUnits = -4;
  }
  const pattern = PATTERNS[L.pattern || 'none'];
  const fib = pattern === 2 || pattern === 3;
  mat.userData = {
    key, baseOpacity: L.opacity, pattern,
    u: {
      uNoiseMat: { value: noiseMat.clone() },
      uAxis: { value: fib ? principalAxis(mesh.geometry, noiseMat) : new THREE.Vector3(0, 1, 0) },
      uScale: { value: L.patternScale || 1000 }, uAlong: { value: L.patternAlong || 50 },
      uStrength: { value: L.patternStrength || 0 },
      uCut: { value: new THREE.Color(L.color).multiplyScalar(0.8) },
    },
  };
  mat.onBeforeCompile = (shader) => patch(shader, mat);
  mat.customProgramCacheKey = () => 'anat' + pattern;
  return mat;
}
