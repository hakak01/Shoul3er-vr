# PROGRESS (updated 2026-11-24, Phase E done: kit/v1 frozen; waiting for headset review = Phase F)
Repo: github.com/hakak01/Shoul3er-vr ("should3r-vr"); site https://hakak01.github.io/Shoul3er-vr/ (SPEC's "shoulder-vr" URLs mean this repo).
## Done
- A: shoulder.glb (314 objects; lateral femoral cutaneous n. removed 2026-11-24, region.py fixed). B: viewer, landmarks. C: gaps.glb. D1: 6-bone ISB rig, rhythm, Move tab, bulge, ligament tension, VR forearm grab.
- D2: tools/build_wrap.py (+ rig_pose, wrap_fit, wrap_morph, wrap_rope; ~2 min) → 6 corrective morph targets in shoulder/gaps.glb + assets/wrap.json. js/wrap.js (scapula-thorax contact, shape blending), js/ropes.js (nerve/vessel ropes, stretch % in the info panel).
- rhythm.json now = Ludewig 2009 eAppendix tables E-1,2,3,7,8,9 (raising), per plane 0/40/90° (abduction/scapular/flexion).
- E: js/kit.js API (loadShoulder → show/hide/ghost/isolate, setPose, landmarks, addMesh on a bone), demo.html, kit/v1/ frozen (39 files, 16.4 MB, sha256 in FILES.json), docs/KIT.md, tools/freeze_kit.py, tools/check_kit.mjs.
## Decisions
- Rhythm: change from the 15° row; the "peak" row placed at GH+ST elevation (abd 135°, scaption 138°, flexion 132°); 135→180° = half the last slope (approx). JS/Python interpolate between planes, clamp outside 0–90°.
- Scapula contact (Seth 2016 idea): ellipsoid fitted to 2336 rib vertices under the scapula's path, centre (thorax frame) −66/−147/+63 mm, radii 92/191/78 mm; 80 scapula samples stay at level ≥ min(rest, 0.98) by an extra rotation about AC: 4.2° at 90° abd, 9.3° at 150° scaption, 9.8° at full elevation (shown in Move tab). Ribs stay clear.
- Correctives at abd90, full elev (plane 30/170°), ER 90° side, IR −80° side, ABER, cross-body (135/90°): push out of head sphere (22.4+1.5 mm), thorax ellipsoid (girdle tissue only) and real bones, never deeper than at rest; 10 relax passes (5 mm spatial smoothing), volume restore for closed muscles (≤3 mm). Damped inverse back to rest space. 57 meshes, 100,820 vertices → 9.7 MB GPU (limit 60). No morph normals.
- Blend weights = piecewise linear in sliders (elevation side→90→170; rotation ER/IR at side; plane abd→cross-body and ABER at 90°): exact at the 6 poses, 0 at rest.
- Ropes: 25 structures (roots→cords, MC, axillary, suprascapular, radial, ulnar, median, axillary a./v., cephalic v.), 789 particles @5 mm, 50 junction links. Pinned where ≤2.5 mm+radius from bone (not clavicle) and axillary n. ≤8 mm from surgical neck (=QS lateral border); roots at the vertebrae. Coracoid/pec minor = sliding pulley (cords, axillary a./v.). Colliders: head sphere, humeral shaft (r 8.0), clavicle (6.3), coracoid (6.1), thorax ellipsoid. Solve starts from the tissue path each pose (same pose → same result), 300 passes over 10 frames (30/frame).
- Headless D2 test: muscle vertices >2 mm in bone, corrected vs plain: abd90 2/994, full 21/2687, ER 0/1422, IR 1/1267, ABER 5/2090, cross-body 4/2020.
- Stretch at abd90 / full / ER / IR (whole nerve %): axillary 9/6/11/11, radial 4/5/0/0, ulnar 2/3/1/0, posterior cord 8/9/5/3, suprascapular ~0. Path length vs neutral, approx.
- Kit: loaded from the same site with importmap "shoulder/": "/Shoul3er-vr/kit/v1/js/", three 0.170.0. File coords = Z-Anatomy metres (+X patient left, +Y up, +Z anterior); kit.root origin = GH (−0.1675, 1.3809, −0.0268). Custom meshes attach to a bone at rest pose (bone inverse bind). kit/v1 also holds the full viewer (index.html). js/tissues.js takes a base path; anatomy.js tolerates materials without emissive.
- Kit test (other-repo page, kit/v1): 344 structures, screw follows humerus 0.000 mm, GH at root origin, abd90 OK, axillary n. stretch 10.8%, rope NaN 0, realistic view OK, no errors; fetched only kit/v1 files.
## Known problems
- Full elevation in plane 30°: humerus bone overlaps the scapula 1–4.6 mm above 150° (no GH translation) → 20 supraspinatus vertices ≤4 mm in acromion. 1 trapezius vertex "26 mm" is a test artifact.
- In-between poses only partly corrected (abd45: 306 vs 402; flex120: 1562 vs 2868 vertices in bone).
- Rope CPU ~3.6 ms/frame on desktop while settling; Quest fps not yet measured. Repo now ~33 MB of assets (assets/ 16 + kit/v1 16.4).
- Manual scapula: correctives assume the rhythm. Z-Anatomy nerves are thin (axillary r 0.56 mm).
## Next step
- You: headset test of the viewer and https://hakak01.github.io/Shoul3er-vr/kit/v1/demo.html?elev=90 ; send numbered corrections (Phase F). Fixes go to the live files; kit/v1 stays frozen (kit/v2 if the kit must change).
## Key files
- docs/KIT.md, js/kit.js, demo.html, kit/v1/, tools/freeze_kit.py, check_kit.mjs · tools/build_wrap.py, check_wrap.py/.mjs · assets/wrap.json, rhythm.json, rig.json · js/rig.js, wrap.js, ropes.js
