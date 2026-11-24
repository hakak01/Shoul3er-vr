# Shoulder kit v1 — how other repos use it (read only this file)
**Where:** https://hakak01.github.io/Shoul3er-vr/kit/v1/ (SPEC's "shoulder-vr" = this repo, Shoul3er-vr). Load it from there; never copy it. `kit/v1/` is frozen: never edit it; changes go to a new `kit/v2/` (`python3 -I tools/freeze_kit.py v2`). Check v1 is untouched: `python3 -I tools/freeze_kit.py v1 --check`.
**Contents:** `js/kit.js` (the API) + viewer modules · `assets/` shoulder.glb, gaps.glb, landmarks.glb, manifest/gaps/landmarks.json (structure names, layers, approx), rig.json (ISB frames, joints, landmarks), rhythm.json (Ludewig 2009 + limits), wrap.json (correctives, ropes), look.json, tissues.json, tex/, env/ · `index.html` (full viewer) · `demo.html` (smallest host page) · `FILES.json` (sha256). 17 MB; licence CC BY-SA 4.0 (ATTRIBUTION.md).
## Host page (same site, so no CORS problems)
```html
<script type="importmap">{ "imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/",
  "shoulder/": "/Shoul3er-vr/kit/v1/js/" } }</script>
<script type="module">
import { loadShoulder } from 'shoulder/kit.js';
const kit = await loadShoulder({ renderer, scene, camera });          // your THREE renderer/scene/camera
renderer.setAnimationLoop(() => { kit.update(); renderer.render(scene, camera); });
</script>
```
three must be exactly 0.170.0 (one copy). Options: `parent` (default scene), `lights:false` (kit adds a hemisphere + directional light otherwise), `view:'present'|'realistic'|'cadaver'`, `onProgress(f)`, `base` (folder holding assets/; default = the kit folder). Headless tests: clone this repo beside yours, serve the PARENT folder on port 8765 so `/Shoul3er-vr/kit/v1/js/` resolves, route the three CDN to a local npm copy (example: tools/check_kit.mjs).
## Functions (`kit.`…; names exactly as in the manifests, e.g. 'Humerus', 'Axillary nerve', 'Rotator cable')
- `names(layer?)`, `get(name)` → {name, layer, kind, approx, node, meshes}, `find(text)`, `layers()`
- `show(name, on)`, `ghost(name, on)`, `isolate([names] | null)`, `showAll()`, `setLayer(layer, on, opacity?)`, `select(name|null)`, `labels(on)`, `setClip('off'|'sagittal'|'axial'|'coronal', pos 0–1, flip)`, `pick(raycaster)` → {struct, point}
- `setView(v)` (Promise) · `setTension(on)` (ligament colours) · `stretch(name)` (text: nerve/ligament stretch, muscle length vs neutral)
- Pose (degrees): `setPose({plane, elev, rot, elbow, sup})` any subset, clamped to rhythm.json limits. plane 0 = abduction, 90 = flexion, >90 cross-body; elev = humerothoracic elevation; rot + = external; elbow 0 = straight; sup 0 = thumb up, + = supination. `getPose()`, `restPose()`, `resetPose()`. Scapula/clavicle follow the rhythm; `setScapula({'scapula.upwardRotation': d, …})` overrides (keys = SCAPULA_KEYS), `setScapula(null)` returns to the rhythm. `settle()` finishes the nerve ropes now (else ~10 frames). `kit.onPose = (kit) => …` runs after each pose change.
- `addMesh(mesh, {bone, name, layer})`: your mesh built in file coordinates (below), at the REST pose. bone = 'thorax'|'clavicle'|'scapula'|'humerus'|'ulna'|'radius' (moves with it) or null. With a name it acts like a structure (show/ghost/isolate/pick). `removeMesh(name)`.
- Points: `landmark(id)` posed ISB landmark (IJ PX C7 T8 SC AC AA TS AI GH EL EM RS US), `joint(bone)` posed joint centre, `posed(point, bone)`, `boneDelta(bone)` (Matrix4 rest→now), `toWorld(p)`, `fromWorld(p)`.
- Raw parts if needed: `kit.model` (glTF scene), `kit.anatomy`, `kit.rig`, `kit.realism`, `kit.root`.
## Coordinate system
- File coordinates = the GLB files = Z-Anatomy world, metres, RIGHT side only: +X = patient's LEFT, +Y = up, +Z = anterior. Standing adult male; right GH centre `kit.center` = (−0.1675, 1.3809, −0.0268).
- `kit.root` (a Group; move/scale it for VR) has the GH centre at its origin with the same axes. Bone frames: ISB (Wu 2005) in rig.json "frames" (columns = X anterior, Y superior, Z lateral).
- Structures with approx:true (gaps.glb, landmarks) are drawn from the literature, not from the source model.
## Not in the kit API
VR controls, wrist menu and panels (js/xr.js, menu.js) belong to index.html's own app; copy that pattern if needed.
