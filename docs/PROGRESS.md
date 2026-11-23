# PROGRESS (updated 2026-11-23, Phase C)
Repo: github.com/hakak01/Shoul3er-vr (user calls it "should3r-vr"); site https://hakak01.github.io/Shoul3er-vr/ (SPEC's "shoulder-vr" URLs mean this repo).

## Done
- A: assets/shoulder.glb (315 objects, 707k tris). B: viewer (model.json, GH-centred, Realistic start), landmarks.glb (7 patches).
- C: tools/build_gaps.py (+ gaps_joint.py, gaps_nv.py, gaps_fat.py; ~5 s) → assets/gaps.glb 0.29 MB, 24 objects, 40k tris, all approx:true. Removed hand-only gaps_finger/gaps_wrist.
- IGHL anterior band / axillary pouch / posterior band, rotator cable, subscapular bursa; lateral + medial cords, roots of median, proximal MCN, MACN join; superior thoracic a. (+2nd space branch); deltoid, acromial, clavicular branches of thoraco-acromial a.; intercostobrachial n.; subcutaneous fat (7 regions).
- Viewer: a gaps.json entry with "replaces" removes that original object (single Z-Anatomy IGHL now hidden). tools/check_gaps.py = numeric check.

## Decisions
- IGHL: bands 2–4 and 7–9 o'clock 2.8 mm thick, pouch 4–7 o'clock 1.6 mm; glenoid labrum rim → humeral collar 4 mm below the articular edge; follows the sagging capsule (length 28/29/37 mm at 3/6/9 o'clock); merged into the capsule wall (2.3 mm).
- Rotator cable: 10 mm wide, 35 mm long, centre 14 mm medial to the SSP/ISP footprint edge, tapered ends.
- Cords: r 2.5 mm, 6 mm from the artery axis (artery r 2.5); 2nd part = where pectoralis minor is in front (28 mm). Roots of median meet 3rd part. MCN enters coracobrachialis 56 mm below coracoid (Flatow mean).
- Arteries r 0.7–1.0 mm; deltoid branch deep to the cephalic vein in the groove. ICBN: 2nd space at mid-axillary line → axilla → posteromedial arm, 188 mm.
- Fat max thickness: axilla 25 mm (got median 7.6, max 21), deltoid 15 (median 5.3, max 13), others 6. Fat = skin-to-muscle gap, so it cannot be thicker than the gap.

## Known problems
- Rotator cable: Z-Anatomy SSP/ISP "crescent" is 5.9 mm thick (real ~2 mm) and lies on the cartilage, so 2.6× (15 mm) cannot fit; cable built 5.5 mm, inside the tendon (see it with SSP/ISP hidden).
- Overlaps inherited from Z-Anatomy: IGHL bands enter subscapularis 28% / teres minor 42% of vertices (old IGHL was 43% in subscapularis); acromial branch 18% in deltoid (CA ligament is 65% inside deltoid); deltoid branch 17% in pec major (muscles touch at the groove).
- Posterior cord (original) is 18–26 mm behind the artery, not rebuilt. Medial pectoral n. not joined. Subscapular bursa is a closed sac touching the capsule (no real hole).
- Earlier: CHECKS.md items; Quest fps not measured.

## Next step
- You: headset review of Phase C parts (approx). Then Phase D1 (movement).

## Key files
- tools/build_gaps.py, gaps_joint.py, gaps_nv.py, gaps_fat.py, gapgeom.py, check_gaps.py · assets/gaps.glb, gaps.json · js/anatomy.js (replaces) · data/raw/gaps_log.txt
