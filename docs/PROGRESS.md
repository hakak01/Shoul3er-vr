# PROGRESS (updated 2026-11-23)

## Done
- Phase A: assets/shoulder.glb (5.1 MB, 315 objects, 707k triangles) + manifest.json; GAPS.md, CHECKS.md.
- Phase B (viewer): reads assets/model.json {glb, gaps, landmarks, title, center}; recentred on the GH joint; starts in Realistic; Present/Realistic/Cadaver unchanged.
- Landmarks: tools/build_landmarks.py → assets/landmarks.glb (116 kB, 7 patches, 15.6k triangles) + landmarks.json (approx:true, label point). Faint cyan patch + cyan outline; layer "Landmarks"; Tools → "Landmark labels" toggle (off at start).
- New layers in look.json: Bursae, Lymph nodes, "Ribs, sternum, spine" (context_bone, 30% opacity = ghosted), Landmarks.

## Decisions
- GH centre = sphere fit to humeral head cartilage: glTF (-0.1675, 1.3809, -0.0268) m, radius 22.4 mm, residual 0.31 mm. Viewer puts it at 0,0,0; labrum centre then sits 18 mm medial.
- Openings found by projecting the bounding structures and taking the enclosed hole; depth interpolated from the walls. Quadrangular space and triangular interval: coronal sections (±6 / ±8 mm) scanned posteriorly from the axillary/radial nerve. Triangular space: full posterior view. Notches: sections across the suprascapular nerve/ligament. Rotator interval: on a sphere round the GH centre through the CHL. Deltopectoral groove: strip between deltoid and pectoralis major rims along the cephalic vein.
- tissues.json: "brachial plexus" names now use the nerve material (Posterior cord was getting ligament).
- Start camera: target 15 cm below the GH joint, anterolateral (model is 1 m tall: latissimus reaches the pelvis).

## Known problems
- Fixed in viewer: 17 midline objects (sternum, C4–T8, R subclavian a./v.) carry a ".001" name suffix in shoulder.glb; they were dropped before.
- Edges touch (% of outline): QS = humerus 50, LHT 32, teres major 16 (teres minor misses); triangular space = teres minor 47, teres major 47, LHT 5; triangular interval = lateral head 67, humerus 32 only (LHT and lateral head touch in this model, so no true gap); rotator interval large (1424 mm²).
- Deltopectoral groove patch only 52 mm long (where both muscles are within 15 mm of the vein).
- Phase A problems remain (CHECKS.md); 707k triangles, Quest fps not yet measured. gaps.glb does not exist yet (Phase C), a 404 in the console is expected.

## Next step
- You: Quest fps check + landmark review. Then Phase C (gaps).

## Key files
- js/main.js, anatomy.js, labels.js, menu.js, looks.js · assets/model.json, look.json, tissues.json · tools/build_landmarks.py (python3 -I, ~3 s)
