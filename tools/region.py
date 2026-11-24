"""Region settings: which Z-Anatomy objects belong to this model.
Change ACTIVE (or edit a dict) to build another region. Z-Anatomy world, metres;
right side is x < 0, +z is up, +y is posterior."""
import re

SHOULDER = dict(
    name='shoulder',
    # neck root (top of C4 = 1.506) down to the proximal third of the forearm
    # (radius 0.856-1.093 -> 1.093 - 0.237/3 = 1.014)
    z_lo=1.014, z_hi=1.51,
    x_max=-0.03,              # centre must be right of this (midline is 0)
    bones=r'^(Clavicle|Scapula|Humerus|Radius|Ulna)$',
    context_bones=r'^(Manubrium of sternum|Body of sternum|Xiphoid process|'
                  r'Vertebra (C[4-7]|T[1-8])|(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth) rib|'
                  r'Costal cartilage of (first|second|third|fourth|fifth|sixth|seventh|eighth) rib)$',
    # whole muscles that move the shoulder girdle, kept even outside the box
    whole_muscles=r'trapezius|latissimus|serratus anterior|pectoralis (major|minor)|'
                  r'levator scapulae|rhomboid|scalen|omohyoid|subclavius',
    # lymph node groups wanted from system 6
    nodes=r'axillary|infraclavicular|interpectoral|brachial|cubital|deltopectoral',
    # trunk, neck and visceral structures that fall inside the box but are not wanted
    exclude=r'intercostal|costal|sternocleid|platysma|thyro|laryn|pharyn|trache|oesoph|'
            r'thoracic duct|vertebral|carotid|jugular|vag|phrenic|sympath|cardiac|pulmon|'
            r'aort|abdomin|oblique|rectus|spinal (cord|nerve)|spinalis|spinous|erector|longissimus|iliocostal|'
            r'semispinal|multifid|rotatores|splenius|serratus posterior|levatores|transversus|'
            r'subcostal|diaphragm|mamm|breast|thyroid|cervical plexus|ansa|hypoglos|'
            r'internal thoracic|pericardiacophrenic|brachiocephalic|azygos|intervertebral|'
            r'longus|rib|sternum|sternal|interspinal|intertransvers|nuchal|supraspinous lig|'
            r'cervical (vein|artery|nerve)|occipital|auricular|facial|lingual|lumbar|iliac|'
            r'scalene tubercle|hand|digit|finger|thumb|palm|carp|metacarp|wrist|renal|iliohypogas|'
            r'quadratus lumborum|epigastric|hypochondri|umbilical|of abdomen|submandibular|'
            r'costocervical|investing cervical|femoral|gluteal|inguinal',
    exclude_keep=r'transverse humeral|transverse scapular|serratus anterior|'
                 r'superficial cervical artery|transverse cervical|dorsal scapular|'
                 r'suprascapular|subclavian|(?<!femoral )cutaneous|thyrocervical',   # not the lateral femoral cutaneous n. (thigh)
    # always kept (right SC joint sits near the midline; subclavian vessels are named 'Right ...')
    always=r'^(Right subclavian (artery|vein)|.*sternoclavicular.*\.r|Interclavicular ligament\.r)$',
    # nerves/vessels with these names are kept whole if they reach into the box
    limb_names=r'antebrachial|cutaneous|radial|ulnar|median|interosseous|cephalic|basilic|cubital|recurrent',
    # forearm muscles arising at the elbow (top above elbow_top, centre lateral to limb_x) kept whole
    limb_x=-0.17, elbow_top=1.05,
    sides=r'\.[a-z0-9]*r$',   # right-side suffixes: .r .or .er .e2r
    systems=(1, 2, 3, 4, 5, 6, 7, 9),
    budget=600000,
    # only the ghosted context bones may be decimated to meet the budget
    reduce_dev=0.0003,
    # coarse in the source: one Loop subdivision level, shape change <= 0.3 mm
    smooth=r'^(Supraspinatus muscle|Infraspinatus muscle|Subscapularis muscle|Teres minor muscle|'
           r'Articular capsule of glenohumeral joint|(Superior|Middle|Inferior) glenohumeral ligament|'
           r'Glenoid labrum|Coracohumeral ligament|Coraco-acromial ligament|Long head of biceps brachii)$',
    centre='glenohumeral',    # viewer recentres here (Phase B)
)

ACTIVE = SHOULDER
R = {k: re.compile(v, re.I) for k, v in ACTIVE.items() if isinstance(v, str) and k not in ('name', 'centre')}
