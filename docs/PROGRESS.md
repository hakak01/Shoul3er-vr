# PROGRESS (updated 2026-11-23, Phase D1 done and pushed; waiting for headset review)
Repo: github.com/hakak01/Shoul3er-vr ("should3r-vr"); site https://hakak01.github.io/Shoul3er-vr/ (SPEC's "shoulder-vr" URLs mean this repo).

## Done
- A: shoulder.glb (315 objects, 707k tris). B: viewer, landmarks.glb. C: gaps.glb (IGHL bands, rotator cable, cords, branches, fat).
- D1: tools/build_rig.py (+ rig_frames.py, rig_weights.py, glbskin.py; ~20 s) → 6-bone skin in all 3 GLBs + assets/rig.json. js/rig.js (pose, rhythm, bulge, tension), js/movemenu.js ("Move" tab), VR forearm grab (xr.js). assets/rhythm.json (you edit), look.json "tension".

## Decisions
- Bones thorax→clavicle (SC)→scapula (AC)→humerus (GH)→ulna (elbow)→radius (forearm axis). ISB frames (Wu 2005) from IJ/PX/C7/T8, SC/AC, AA/TS/AI, GH/EL/EM, US/RS.
- GH = sphere fit to head cartilage, r 22.4 mm (fit error 0.31 mm). Elbow axis = capitellum (r 12.6) + trochlea (r 12.7) sphere centres, 7.8° from humeral Z. Forearm axis = radial head centre → ulnar head. SC/AC = centroids of the clavicle's articular ends.
- Rest pose of the model: clavicle retraction 27°, elevation 8.6°; scapula IR 43°, upward rot 23°, anterior tilt 8.5°; humerus plane −34°, elevation 13°; elbow 14°; supination 78°.
- Arm sliders = humerothoracic plane / elevation / rotation as swing then twist (ER +), so the plane slider does nothing at 0° elevation (avoids the ISB Y-X-Y gimbal). Scapula/clavicle ISB Y-X-Z.
- Rhythm (approx): upward rotation 0 to 30°, then 0.4°/° (60° at 180°); posterior tilt 19°, clavicle posterior rotation 31°, retraction 15°, elevation 12°, scapular ER 5° at 180°. Limits in rhythm.json (elbow 0–145, sup −80/+85, rotation ±90, extension plane max 60°).
- Weights: muscles blend origin→insertion along their length, switching at the crossed joint (width ±0.2); footprints split by bone level because Z-Anatomy origin/insertion labels are inconsistent; biceps (both heads) and long head of triceps get 3 bones. Ligaments/capsule/bursae: between the 2 bones they touch (labrum counts as scapula); skin/fat/fascia: nearest bones (σ 10 mm), each layer weighted as one piece (no seams).
- Bulge: belly scale √(rest/length), clamped 0.85–1.3. Tension: 22 ligaments, GH and elbow capsules split in 8 sectors; strain = chord now / rest length along the tissue; yellow 4%, red 8%.
- meshopt uses one quantization volume; js prepareSkins() undoes it at load (rest-pose error 0.001 mm).
- Axillary nerve ↔ lateral acromion: 54 mm at side → 42 mm at 90° abduction (22% shorter; Burkhead ~30%).

## Known problems
- Seth 2016 download blocked (403): rhythm = defaults. Quest fps not measured (GPU skinning of 363k vertices added).
- Tension values are large (capsule 60–130% in ABER/full elevation): straight chords, no wrapping or GH translation. Read them as "which part tightens", not real strain.
- Linear-blend skinning: axillary skin stretches as a flat sheet; muscles/skin can pass through bone at big angles; nerves/vessels just follow nearest bones (D2 fixes these). Scapula can enter the ribs.
- First click after moving can be slow (skinned picking is on the CPU). Short head of biceps forced to the radius (its distal end merges into the long head object).

## Next step
- You: headset test of Move tab (see report). Then Phase D2 (wrapping, nerves).

## Key files
- tools/build_rig.py, rig_frames.py, rig_weights.py, glbskin.py · assets/rig.json, rhythm.json · js/rig.js, movemenu.js · data/raw/rig_log.txt. Rebuild order: build_assets → build_landmarks → build_gaps → build_rig.
