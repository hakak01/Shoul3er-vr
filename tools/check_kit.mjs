// Phase E headless test of the kit as ANOTHER repo would use it (not part of the site). Needs Playwright and a local
// three@0.170.0 copy (the CDN is blocked in the cloud session). Put this repo and a fake other repo side by side and
// serve their parent folder:  python3 -m http.server 8765 --bind 127.0.0.1   (from the folder that holds Shoul3er-vr/)
// Run:  node tools/check_kit.mjs <dir with node_modules/three> <kit path, e.g. /Shoul3er-vr/kit/v1/> [screenshot.png]
import { createRequire } from 'module'; const { chromium } = createRequire(import.meta.url)('playwright');
import fs from 'fs';
const [S, KIT, SHOT] = process.argv.slice(2), HOST = 'http://127.0.0.1:8765';
const page = `<!doctype html><html><head><script type="importmap">{ "imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/" } }</script></head>
<body style="margin:0"><canvas id="c" style="width:900px;height:700px"></canvas><script type="module">
import * as THREE from 'three';
import { loadShoulder, BONES } from '${KIT}js/kit.js';
const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('c') }); renderer.setSize(900, 700);
renderer.toneMapping = THREE.NeutralToneMapping;
const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(45, 900 / 700, 0.01, 50);
camera.position.set(-0.35, 0.05, 0.75); camera.lookAt(0, -0.12, 0);
window.T = { THREE, renderer, scene, camera, BONES };
window.kit = await loadShoulder({ renderer, scene, camera });
</script></body></html>`;
const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const p = await b.newPage({ viewport: { width: 900, height: 700 } });
const errs = [];
p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 200)); });
p.on('pageerror', (e) => errs.push('pageerror: ' + e.message.slice(0, 300)));
await p.route('https://cdn.jsdelivr.net/npm/three@0.170.0/**', (r) => {
  const f = S + '/node_modules/three/' + r.request().url().split('three@0.170.0/')[1];
  r.fulfill({ body: fs.readFileSync(f), contentType: f.endsWith('.js') ? 'text/javascript' : 'application/octet-stream' });
});
await p.route(HOST + '/other-repo/test.html', (r) => r.fulfill({ body: page, contentType: 'text/html' }));
await p.goto(HOST + '/other-repo/test.html');
try { await p.waitForFunction(() => window.kit, null, { timeout: 120000 }); } catch (e) { console.log('LOAD FAILED\n' + errs.join('\n')); process.exit(1); }
const out = await p.evaluate(async () => {
  const { THREE } = T, r = {}, near = (a, b) => a.distanceTo(b) < 1e-5;
  r.structures = kit.names().length; r.bones = kit.names('bone').join(',');
  r.get = !!kit.get('Axillary nerve') && kit.find('rotator cable').length;
  kit.show('Deltoid region', false); r.hide = kit.get('Deltoid region').meshes.every((m) => !m.visible);
  kit.show('Deltoid region', true); r.show = kit.get('Deltoid region').meshes.every((m) => m.visible);
  kit.isolate(['Humerus', 'Scapula']); r.isolate = kit.get('Clavicle').meshes.every((m) => !m.visible); kit.isolate(null);
  const screwAt = new THREE.Vector3(...kit.center).add(new THREE.Vector3(-0.02, 0, 0));
  const scr = new THREE.Mesh(new THREE.SphereGeometry(0.003), new THREE.MeshBasicMaterial({ color: 'red' }));
  scr.position.copy(screwAt); kit.addMesh(scr, { bone: 'humerus', name: 'Test screw', layer: 'implant' });
  const wp = (o) => { kit.root.updateMatrixWorld(true); return o.getWorldPosition(new THREE.Vector3()); };
  kit.settle(); r.restGH_mm = +(1000 * wp(scr).distanceTo(kit.toWorld(screwAt))).toFixed(4);
  r.restRoot_mm = +(1000 * kit.toWorld(new THREE.Vector3(...kit.center)).length()).toFixed(4);   // GH at kit.root origin
  const el0 = kit.landmark('EL');
  kit.setPose({ plane: 0, elev: 90, rot: 0 }).settle(); const pose = kit.getPose();
  r.pose = [pose.plane, pose.elev, pose.rot].map(Math.round).join('/');
  r.followsHumerus_mm = +(1000 * wp(scr).distanceTo(kit.toWorld(kit.posed(screwAt, 'humerus')))).toFixed(4);
  r.ELmoved_mm = Math.round(1000 * kit.landmark('EL').distanceTo(el0));
  r.stretchAxillary = kit.stretch('Axillary nerve');
  r.pick = (() => { const rc = new THREE.Raycaster(); rc.setFromCamera(new THREE.Vector2(0, 0), T.camera); const h = kit.pick(rc); return h ? h.struct.name : null; })();
  kit.removeMesh('Test screw'); r.removed = !kit.get('Test screw') && !scr.parent;
  let nan = 0; for (const m of kit.rig.ropes.meshes) for (const v of m.m.geometry.attributes.position.array) if (!isFinite(v)) nan++;
  r.ropeNaN = nan;
  await kit.setView('realistic'); r.view = kit.realism.view;
  kit.update(); T.renderer.render(T.scene, T.camera);
  return r;
});
for (const [k, v] of Object.entries(out)) console.log(k.padEnd(18), v);
if (SHOT) { await p.waitForTimeout(500); await p.locator('#c').screenshot({ path: SHOT }); console.log('screenshot', SHOT); }
console.log('errors', errs.length ? errs.slice(0, 8).join('\n') : 'none');
await b.close();
