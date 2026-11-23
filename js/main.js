// Entry point: renderer, loading, desktop/phone controls, render loop.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { Anatomy } from './anatomy.js';
import { Menus } from './menu.js';
import { XR } from './xr.js';
import { Realism } from './tissues.js';

const GLB_SIZE = 2.9e6, GAPS_SIZE = 0.7e6;   // used for the loading bar if the server gives no size
const app = { fps: 0 };
window.app = app;

const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('c3d'), antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.localClippingEnabled = true;
app.renderer = renderer;

const scene = new THREE.Scene(); app.scene = scene;
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
const hemi = new THREE.HemisphereLight(0xffffff, 0x445566, 0.6); scene.add(hemi);
const sun = new THREE.DirectionalLight(0xffffff, 1.4); sun.position.set(0.5, 1, 1.2); scene.add(sun);
app.lights = { hemi, sun };
const camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 0.01, 50);
const controls = new OrbitControls(camera, renderer.domElement);
app.camera = camera; app.controls = controls;
controls.enableDamping = true; controls.minDistance = 0.03; controls.maxDistance = 5;
const root = new THREE.Group(); scene.add(root); app.root = root;

const fill = document.getElementById('fill'), loadText = document.getElementById('loadText');
const fail = (e) => { loadText.textContent = 'Loading failed: ' + e; console.error(e); };

async function load() {
  const [look, manifest, gapsMan] = await Promise.all(['assets/look.json', 'assets/manifest.json', 'assets/gaps.json']
    .map((u) => fetch(u, { cache: 'no-cache' }).then((r) => r.ok ? r.json() : [])));
  app.bg = new THREE.Color(look.background); scene.background = app.bg;
  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  const got = {}, tot = {};
  const bar = () => { fill.style.width = Math.min(100, 100 * (got.h + got.g || 0) / ((tot.h || GLB_SIZE) + (tot.g || GAPS_SIZE))) + '%'; };
  const prog = (k) => (e) => { got[k] = e.loaded; tot[k] = e.total; bar(); };
  got.h = got.g = 0;
  const [gltf, gaps] = await Promise.all([loader.loadAsync('assets/hand.glb', prog('h')),
    loader.loadAsync('assets/gaps.glb', prog('g')).catch((e) => { console.warn('gaps.glb not loaded', e); return null; })]);
  if (gaps) for (const n of [...gaps.scene.children]) gltf.scene.add(n);   // approximate (Phase C) structures
  loadText.textContent = 'Preparing…';
  const A = new Anatomy(root, gltf.scene, manifest.concat(gapsMan || []), look); app.anatomy = A;
  app.menus = new Menus(app);
  A.onChange = () => app.menus && app.menus.buildInfo();
  app.menus.menu.attachDom('menuCanvas'); app.menus.info.attachDom('infoCanvas');
  app.xr = new XR(app);
  resetView();
  renderer.compile(scene, camera);
  document.getElementById('loading').style.display = 'none';
  app.realism = new Realism(app);   // realistic view loads in the background, then switches if startView says so
  const cfg = await fetch('assets/tissues.json', { cache: 'no-cache' }).then((r) => r.json()).catch(() => ({}));
  if (cfg.startView && cfg.startView !== 'present') app.realism.setView(cfg.startView);
}

function resetView() {
  root.position.set(0, 0, 0); root.quaternion.identity(); root.scale.setScalar(1);
  if (app.xr && app.xr.mode) { app.xr.needPlace = true; return; }
  camera.position.set(0, 0, 0.95); controls.target.set(0, 0, 0); controls.update();
}
function focus(s) {
  if (app.xr && app.xr.mode) return app.xr.focus(s);
  root.updateMatrixWorld(true);
  const { center, size } = app.anatomy.bounds(s);
  const dir = camera.position.clone().sub(controls.target).normalize();
  controls.target.copy(center);
  camera.position.copy(center).addScaledVector(dir, Math.max(size * 2.2, 0.08));
  controls.update();
}
Object.assign(app, {
  resetView, focus,
  inXR: () => !!(app.xr && app.xr.mode),
  exitXR: () => app.xr && app.xr.end(),
  onXREnd: () => { app.xr.cursor.visible = false; resetView(); },
});

// menu button (show/hide the on-screen menu)
const menuBtn = document.getElementById('menuBtn');
menuBtn.onclick = () => { const c = document.getElementById('menuCanvas'); c.style.display = c.style.display === 'none' ? '' : 'none'; };
if (innerWidth < 700) setTimeout(() => menuBtn.onclick(), 0);   // phones start with the menu closed
addEventListener('keydown', (e) => {
  if (!app.menus) return;
  if (e.key === 'v' && app.menus.tab !== 'search') return app.realism && app.realism.toggle();
  app.menus.key(e);
});

// click / tap to select (ignore drags)
const ray = new THREE.Raycaster(); let downAt = null;
renderer.domElement.addEventListener('pointerdown', (e) => { downAt = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener('pointerup', (e) => {
  if (!downAt || !app.anatomy || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 6) return;
  ray.setFromCamera(new THREE.Vector2(e.clientX / innerWidth * 2 - 1, -e.clientY / innerHeight * 2 + 1), camera);
  const hit = app.anatomy.pick(ray);
  app.anatomy.select(hit ? hit.struct : null); app.menus.refresh();
});
addEventListener('resize', () => {
  if (renderer.xr.isPresenting) return;
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight);
});

const clock = new THREE.Clock(); let frames = 0, tFps = 0;
renderer.setAnimationLoop(() => {
  const dt = Math.min(clock.getDelta(), 0.1);
  frames++; tFps += dt;
  if (tFps >= 1) {
    app.fps = Math.round(frames / tFps); frames = 0; tFps = 0;
    if (app.menus && app.menus.tab === 'tools') app.menus.refresh();
  }
  if (app.xr) app.xr.update(dt);
  if (app.realism) app.realism.update();
  if (!app.inXR()) controls.update();
  if (app.anatomy) { root.updateMatrixWorld(); app.anatomy.updateClip(); }
  renderer.render(scene, camera);
});

load().catch(fail);
