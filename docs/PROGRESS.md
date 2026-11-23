# PROGRESS (updated 2026-11-23)

## Done
- Step 0: copied from Han-vr (CLAUDE.md, .gitignore, .nojekyll, ATTRIBUTION.md, index.html, js/, tools/, assets look/tissues/tex/env). docs/SPEC.md saved.
- Phase A: assets/shoulder.glb (4.5 MB, meshopt) + assets/manifest.json: 315 objects, 599,088 triangles. assets/ 14 MB.
- docs/GAPS.md (missing: IGHL bands, rotator cable, subscapular bursa, lateral/medial cords, intercostobrachial n., superior thoracic a., 3 thoraco-acromial branches, fat). docs/CHECKS.md.

## Decisions
- Region rules in tools/region.py (zsel.py reads them): z 1.014 (proximal third of forearm) to 1.51 (top of C4), centre x < -0.03; whole girdle muscles kept; forearm muscles arising at the elbow kept whole; nerves/vessels with limb names kept whole.
- Layers: Han-vr + bursa, context_bone, lymph_node (new, for axillary nodes); landmark comes in Phase B.
- Bones: all 5 swapped to BodyParts3D (ICP mean 0.37–0.68 mm, max 2.8 mm). Swap only if BP3D has more triangles.
- Coordinates: Z-Anatomy world, no recentring. GLB is glTF y-up: glTF (x, y, z) = Z-Anatomy (x, z, -y). Same as Han-vr hand.glb.
- Budget: 763k → 599k by tools/decimate.py (Blender collapse, max 2-way deviation ≤0.30 mm): pass 1 flat girdle muscles + cuff origin footprints; pass 2 other footprints. Muscle bodies themselves could not be reduced within 0.3 mm. Context bones untouched (141k).

## Known problems
- MCN does not pierce coracobrachialis; SSP/ISP footprints differ from Mochizuki; radial nerve leaves the humerus 42 mm low (see CHECKS.md).
- Scapula alone is 113k triangles (BP3D detail). Skin = 20 region patches, not one surface.
- Viewer still points at hand.glb (Phase B).

## Next step
- Phase B: viewer reads assets/model.json, recentres on GH joint, starts Realistic; landmark patches.

## Key files
- tools/region.py, zsel.py, build_assets.py, decimate.py, measure.py · data/raw/build_log.txt (git-ignored)
