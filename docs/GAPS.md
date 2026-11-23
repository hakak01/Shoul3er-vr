# GAPS (Phase A, against REQUIRED STRUCTURES in SPEC.md)
Source: assets/manifest.json (315 objects). ✓ = present as a Z-Anatomy object. ✗ = missing (planned fix in brackets).

## Bones
- ✓ Clavicle, scapula, humerus, radius, ulna — all BodyParts3D, with Cartilage slot (cartilage share of faces: clavicle 16%, scapula 3% (glenoid), humerus 25%, radius 34%, ulna 29%).
- ✓ Context (layer context_bone): manubrium, body of sternum, xiphoid; right ribs 1–8 + costal cartilages 1–8; C4–T8.

## Joints
- ✓ GH capsule, SGHL, MGHL, IGHL (one object), CHL, glenoid labrum, transverse humeral ligament.
- ✗ IGHL complex bands (anterior band, axillary pouch, posterior band) [Phase C].
- ~ Biceps anchor: no separate object; the "Long head of biceps brachii (origin)" footprint marks it [check in Phase C].
- ✓ Coraco-acromial; AC ligament, capsule and disc; conoid; trapezoid; SC capsule, anterior/posterior SC ligaments, SC disc, interclavicular; costoclavicular; superior and inferior transverse scapular.
- ✓ Elbow: capsule, radial and ulnar collateral, annular, quadrate ligaments.

## Muscles and tendons
- ✓ All muscles listed in SPEC (cuff, teres major, deltoid 3 parts, pec major 3 heads, pec minor, subclavius, serratus anterior, trapezius 3 parts, rhomboids, levator scapulae, latissimus, biceps 2 heads, coracobrachialis, triceps 3 heads, brachialis, omohyoid, scalenes 3) + elbow/forearm muscles arising at the elbow.
- ✗ Rotator cable [Phase C].

## Bursae (layer bursa)
- ✓ Subacromial, subdeltoid, subcutaneous acromial; coracobrachial bursa (= subcoracoid bursa); subtendinous bursae of infraspinatus, teres major, trapezius, triceps; bicipitoradial.
- ✗ Subscapular bursa / subscapularis recess [Phase C].

## Nerves
- ✓ Roots (one object), superior/middle/inferior trunks, all six divisions, posterior cord.
- ✗ Lateral and medial cords [Phase C].
- ✓ Axillary (+ muscular branches), suprascapular, musculocutaneous, radial, median, ulnar, long thoracic, thoracodorsal, dorsal scapular, superior and inferior subscapular, lateral and medial pectoral, subclavian, accessory; medial brachial, medial antebrachial (+ anterior/posterior branches), lateral antebrachial, superior and inferior lateral brachial, posterior antebrachial cutaneous.
- ✗ Intercostobrachial nerve [Phase C].

## Arteries
- ✓ Right subclavian, thyrocervical trunk, suprascapular, transverse cervical; axillary (one object; its 3 parts are not separate — can be labelled by pectoralis minor later); thoraco-acromial + pectoral branches; lateral thoracic; subscapular, circumflex scapular, thoracodorsal; anterior and posterior circumflex humeral; brachial; deep brachial; radial and middle collateral; superior and inferior ulnar collateral; radial, ulnar, interosseous and recurrent arteries.
- ✗ Superior thoracic artery; deltoid, acromial and clavicular branches of thoraco-acromial [Phase C].

## Veins
- ✓ Right subclavian, axillary, cephalic, basilic, brachial, median cubital; anterior and posterior circumflex humeral, circumflex scapular, subscapular, thoracodorsal, lateral thoracic, suprascapular.

## Other
- ✓ Deltoid, pectoral, clavipectoral fascia (+ brachial, antebrachial). Axillary nodes (anterior, apical, central, lateral, posterior) + infraclavicular, interpectoral, brachial, cubital (layer lymph_node). Skin = 20 Z-Anatomy region patches (layer skin).
- ✗ Subcutaneous fat [Phase C, gaps_fat.py].
