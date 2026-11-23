I want a realistic 3D model of the NORMAL RIGHT shoulder and arm for Meta Quest 3 (browser WebXR). Later it will be the base for shoulder surgery and shoulder fracture simulators. I am an orthopaedic surgeon with no programming experience: explain anything you need from me in simple English. Keep token use minimal.

STEP 0: Copy CLAUDE.md from Han-vr (see REUSE) and follow it. Save this whole message unchanged as docs/SPEC.md. Create docs/PROGRESS.md (max 30 lines). Then do ONLY Phase A, stop, and report in 10 lines or fewer.

REUSE (copy, do not rewrite)
- My public repo github.com/hakak01/Han-vr is the same Z-Anatomy body with a working pipeline and viewer. Run `git clone -q --depth 1 https://github.com/hakak01/Han-vr /tmp/hanvr`, then copy: CLAUDE.md, .gitignore, .nojekyll, ATTRIBUTION.md, index.html, js/, tools/, assets/look.json, assets/tissues.json, assets/tex/, assets/env/. Do NOT copy hand.glb, gaps.glb, manifest.json, gaps.json or docs/.
- Read only /tmp/hanvr/docs/PROGRESS.md and `grep -n '^def' tools/*.py`, not whole files, unless a step fails.
- Keep its Present / Realistic / Cadaver views unchanged (the cadaver colours were measured from photos).
- Known: cdn.jsdelivr.net is blocked in the cloud session; the headless test serves three@0.170.0 from a local npm copy.
- Han-vr's tools/zsel.py EXCLUDES names matching pectoral|thorac|scapul. The shoulder needs them: move the region rules into tools/region.py as a setting.

SOURCES: same as Han-vr (Z-Anatomy Startup.blend read with bpy; BodyParts3D STL mirror for more detailed bones). Never run `git ls-tree -l` on the BodyParts3D mirror. Licence CC BY-SA 4.0; keep ATTRIBUTION.md.

FACTS ALREADY CHECKED (Z-Anatomy object names; right side ends in ".r")
- Present: Scapula, Clavicle, Humerus; Articular capsule of glenohumeral joint; Superior/Middle/Inferior glenohumeral ligament (the IGHL is ONE object); Coracohumeral ligament; Coraco-acromial ligament; Glenoid labrum; Transverse humeral ligament; Superior and Inferior transverse scapular ligament; AC capsule, ligament and disc; Conoid and Trapezoid ligaments; SC capsule, ligaments and disc; Costoclavicular ligament; Subacromial, Subdeltoid, Subcutaneous acromial and Coracobrachial bursae; supraspinatus, infraspinatus, subscapularis, teres minor and major; deltoid (clavicular, acromial and scapular spinal parts); pectoralis major (3 heads); pectoralis minor; subclavius; serratus anterior; trapezius (3 parts); rhomboids; levator scapulae; latissimus dorsi; biceps (long and short head); coracobrachialis; triceps (3 heads); brachialis; omohyoid; scalenes; deltoid, pectoral and clavipectoral fascia.
- Nerves: Roots, Superior/Middle/Inferior trunks and all six divisions of the brachial plexus; Posterior cord; axillary, suprascapular, musculocutaneous, radial, median, ulnar, long thoracic, thoracodorsal, dorsal scapular, superior and inferior subscapular, lateral and medial pectoral, subclavian and accessory nerves; medial brachial, medial antebrachial, lateral antebrachial, superior and inferior lateral brachial, and posterior antebrachial cutaneous nerves. The lateral and medial cords exist only as groups ("Branches of lateral/medial cord of brachial plexus"), not as cord objects.
- Vessels: Right subclavian artery and vein; axillary artery and vein; thoraco-acromial artery with "Pectoral branches" only; lateral thoracic, subscapular, circumflex scapular, thoracodorsal, anterior and posterior circumflex humeral, suprascapular, brachial and deep brachial arteries; radial and middle collateral arteries; superior and inferior ulnar collateral arteries; cephalic, basilic and brachial veins. Axillary lymph node groups exist.
- Not found: superior thoracic artery; deltoid, acromial and clavicular branches of the thoraco-acromial artery; intercostobrachial nerve; subtendinous bursa of subscapularis; rotator cable; separate IGHL bands; lateral and medial cord objects.

PHASE A: assets
1. Region (right side): from the neck root (C4) to the proximal third of the forearm, including the elbow. Include whole muscles that move the shoulder girdle even where they extend outside the region (trapezius, latissimus, serratus anterior, pectoralis major and minor, levator scapulae, rhomboids, scalenes). Context bones (layer "context_bone", ghosted by default): sternum, right ribs 1–8, C4–T8 vertebrae. Include the whole radius and ulna (needed for the elbow and forearm axes).
2. As in Han-vr Phase A: swap the bones for BodyParts3D bones (ICP; keep the Z-Anatomy bone if the mean error is >1.5 mm), repair, convert curves to lighter meshes, keep the Bone/Cartilage/Tendon material slots and the origin/insertion footprints.
3. Keep the Z-Anatomy world coordinates in the file (no recentring), so this model and the Han-vr hand line up later. Recentre only in the viewer.
4. Budget: ≤600k triangles; assets/ ≤25 MB; meshopt GLB. If over, decimate only large flat muscles (≤0.3 mm change).
5. Export assets/shoulder.glb + assets/manifest.json (same fields as Han-vr). Layers: as in Han-vr plus bursa, context_bone, landmark.
6. Write docs/GAPS.md against REQUIRED STRUCTURES and docs/CHECKS.md against ANATOMY CHECKS (measure and report only; change nothing).

PHASE B: viewer
- Han-vr viewer with only these changes: file names come from assets/model.json {"glb":"shoulder.glb","gaps":"gaps.glb","title":"Shoulder & arm"}; recentre on the glenohumeral joint; start in Realistic view.
- Landmark labels (toggle), each a faint outlined patch fitted to the surrounding bone and muscle (approx:true): rotator interval, quadrangular space, triangular space, triangular interval, suprascapular notch, spinoglenoid notch, deltopectoral groove.

PHASE C: gaps (tools/build_gaps.py → assets/gaps.glb, approx:true; reuse Han-vr's gapgeom.py and gaps_fat.py)
- IGHL complex (O'Brien 1990, AJSM): split the IGHL into anterior band, axillary pouch and posterior band, with the bands thicker than the pouch; humeral attachment as a collar just below the articular edge.
- Rotator cable (Burkhart 1993, Arthroscopy): a thick fibre bundle along the proximal margin of the thin crescent of the supraspinatus–infraspinatus insertion, spanning both tendons, about 2.6× the crescent's thickness.
- Lateral cord from the anterior divisions of the superior and middle trunks; medial cord from the anterior division of the inferior trunk. Place all three cords around the 2nd part of the axillary artery, behind pectoralis minor, named for their relation to the artery, and join them to the existing branches.
- Superior thoracic artery: from the 1st part of the axillary artery to the 1st–2nd intercostal spaces. Deltoid, acromial and clavicular branches of the thoraco-acromial artery (the deltoid branch runs in the deltopectoral groove with the cephalic vein).
- Intercostobrachial nerve: lateral cutaneous branch of the 2nd intercostal nerve, across the axilla to the medial arm.
- Subscapular bursa (subscapularis recess): between the subscapularis tendon and the scapular neck, opening into the joint between the SGHL and MGHL.
- Subcutaneous fat (gaps_fat.py): thicker over the deltoid and in the axilla.

PHASE D1: movement
- Bone frames and angle orders: ISB recommendations (Wu 2005, J Biomech). Joint centres from the geometry: glenohumeral = sphere fit to the humeral head cartilage; SC and AC from their joint surfaces; elbow axis = fit to trochlea + capitellum; forearm axis = radial head centre → ulnar head.
- Controls (wrist-menu sliders, plus grabbing the forearm with a controller): humeral plane of elevation, elevation, axial rotation; elbow flexion; pronation–supination; realistic joint limits.
- The scapula and clavicle follow assets/rhythm.json (I will edit it), with keyframes against humerothoracic elevation. Defaults (approx:true): scapular upward rotation 0 until 30°, then 0.4° per degree (about 2:1 GH:ST overall); scapular posterior tilt rising to about 19° and clavicle posterior axial rotation to about 31° by full elevation (averages from the bone-pin study of Ludewig 2009, JBJS Am); clavicle elevation and retraction about 10–15° each; scapular internal/external rotation under 10°. A "manual scapula" mode lets sliders override the rhythm.
- Try at most 3 commands to download the Seth 2016 bone-pin data from https://purl.stanford.edu/br087nj9017. If it works and is small, fit rhythm.json to its mean; otherwise keep the defaults and tell me.
- Skinning in the Python pipeline: muscles/tendons weighted between origin and insertion bone along their own length (using the footprints); two-joint muscles (long head of biceps, long head of triceps) get 3 bones. Ligaments/capsule between their two bones; skin/fat from the nearest bones with smooth weights.
- Volume: as a muscle shortens, widen its cross-section (scale ∝ √(rest length / length)).
- Ligament tension: colour each ligament/capsule part by its length versus neutral (grey = slack → yellow → red at ≥8%; thresholds in look.json); add a "Show tension" toggle.
- Must hold 72 fps on Quest 3 with WebGL2.

PHASE D2: wrapping and nerves
- Corrective shapes, made offline at ≤6 poses (90° abduction, full elevation, 90° ER at the side, IR, abduction-ER, cross-body flexion), for the muscles and skin around the humeral head and thorax: push them outside a sphere fitted to the humeral head and an ellipsoid fitted to the ribs, relax to keep volume, store the result as morph targets, and blend them at runtime. Morph-target GPU memory ≤60 MB.
- Nerves and vessels (plexus and cords; axillary, suprascapular, musculocutaneous, radial, ulnar and median nerves; axillary artery and vein; cephalic vein): pin the centrelines to bone at fixed points (e.g. the axillary nerve at the quadrangular space and around the surgical neck; the plexus at the transverse processes and under the coracoid/pectoralis minor). Simulate the free parts as a light rope that collides with simple bone shapes, and rebuild the tube every frame. Show the stretch % when one is selected.
- Headless test at 0°, 90° abduction, full elevation, ER and IR: no exploding meshes; no muscle inside bone by >2 mm.

PHASE E: base kit for future simulators
- Freeze kit/v1/ (glb files, manifests, rhythm.json, rig data, the JS modules). Never edit kit/v1 afterwards; changes go to kit/v2.
- docs/KIT.md (≤40 lines): how another repo of mine loads the kit from https://hakak01.github.io/shoulder-vr/kit/v1/ (same site, no copying; for headless tests, clone this repo beside it), the importmap it needs, the functions to call (load, show/hide by name, set pose, get a structure, add a custom mesh in the same coordinates), and the coordinate system. Future sessions will read only KIT.md.

PHASE F: I test in the headset and send numbered corrections. Fix only those.

REQUIRED STRUCTURES (for GAPS.md)
- Bones with cartilage: clavicle, scapula, humerus, radius, ulna. Context: sternum, ribs 1–8, C4–T8.
- Joints: glenohumeral capsule, SGHL, MGHL, IGHL complex, CHL, labrum with the biceps anchor, transverse humeral ligament; coracoacromial, AC, conoid, trapezoid, SC and costoclavicular ligaments; superior and inferior transverse scapular ligaments; elbow capsule and collateral ligaments.
- Muscles and tendons: all those listed above, plus the rotator cable.
- Bursae: subacromial, subdeltoid, subcoracoid, subscapular, subcutaneous acromial.
- Nerves: brachial plexus roots → trunks → divisions → cords → branches; all the named nerves above; intercostobrachial nerve.
- Arteries: subclavian; axillary artery (3 parts) with superior thoracic, thoraco-acromial (pectoral, deltoid, acromial, clavicular branches), lateral thoracic, subscapular (circumflex scapular, thoracodorsal), anterior and posterior circumflex humeral; suprascapular; brachial; deep brachial; collateral arteries.
- Veins: subclavian, axillary, cephalic, basilic, brachial, circumflex.
- Other: deltoid, pectoral and clavipectoral fascia; axillary nodes; skin; subcutaneous fat.

ANATOMY CHECKS (for CHECKS.md; this is one adult male, so flag only big differences)
- Axillary nerve to the lateral acromion edge, at the side and at 90° abduction (Burkhead 1992, JSES: <5 cm in ~20% of shoulders, as close as 3.1 cm; 90° abduction shortens the distance by nearly 30%).
- Musculocutaneous nerve entry into coracobrachialis below the coracoid (Flatow 1989, CORR: mean 56 mm, range 31–82 mm; proximal twigs as close as 17 mm).
- Radial nerve crossing the posterior humerus (Gerwin 1996, JBJS Am: from 20.7 cm above the medial epicondyle to 14.2 cm above the lateral epicondyle).
- Suprascapular nerve at the base of the scapular spine versus the posterior glenoid neck (Bigliani 1990, Arthroscopy: inferiorly directed pins averaged 16 mm from the nerve).
- Footprints (Mochizuki 2008, JBJS Am): supraspinatus triangular, about 6.9 mm medial-lateral × 12.6 mm AP, at the anteriormost part of the highest impression of the greater tuberosity; infraspinatus trapezoidal, about 10.2 × 32.7 mm. Report the differences; don't change them silently.
