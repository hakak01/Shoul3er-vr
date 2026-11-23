"""Phase D2 ropes: centrelines of the main nerves and vessels (from the tube meshes' rings), resampled to particles
every ~5 mm, with skin weights, junction links, bone pins and collider allowances. js/ropes.js simulates them."""
import numpy as np
from scipy.spatial import cKDTree
from gapgeom import MM
import wrap_fit as WF

ROPES = ['Roots of brachial plexus', 'Superior trunk of brachial plexus', 'Middle trunk of brachial plexus',
         'Inferior trunk of brachial plexus'] + \
        ['%s division of %s trunk of brachial plexus' % (a, t) for a in ('Anterior', 'Posterior') for t in ('superior', 'middle', 'inferior')] + \
        ['Lateral cord of brachial plexus', 'Medial cord of brachial plexus', 'Posterior cord of brachial plexus',
         'Lateral root of median nerve', 'Medial root of median nerve', 'Musculocutaneous nerve (proximal part)',
         'Axillary nerve', 'Suprascapular nerve', 'Musculocutaneous nerve', 'Radial nerve', 'Ulnar nerve', 'Median nerve',
         'Axillary artery', 'Axillary vein', 'Cephalic vein']
UNDER_CORACOID = ('Lateral cord', 'Medial cord', 'Posterior cord', 'Axillary artery', 'Axillary vein')
STEP, PIN_GAP, LINK_D = 5 * MM, 2.5 * MM, 8 * MM
NEAR_PIN = {'Axillary nerve': (3, 8 * MM)}          # structure: (bone, distance) pinned beyond the general rule


def rings(V):
    """split a tube mesh's vertex list into rings (8 = Z-Anatomy curves, 10 = gapgeom tubes) -> splines of
    (centre, radius) lists; vertices that are not in a ring (end caps) are skipped"""
    best = None
    for r in (8, 10):
        out, i = [], 0
        while i + r <= len(V):
            g = V[i:i + r]; c = g.mean(0); d = np.linalg.norm(g - c, axis=1)
            if d.mean() > 0.05 * MM and d.std() < 0.2 * d.mean(): out.append((c, d.mean())); i += r
            else: i += 1
        if best is None or len(out) * r > len(best) * best_r: best, best_r = out, r
    C = np.array([c for c, _ in best]); R = np.array([d for _, d in best])
    gap = np.linalg.norm(np.diff(C, axis=0), axis=1); cut = gap > max(3 * np.median(gap), 4 * MM)
    idx = np.split(np.arange(len(C)), np.where(cut)[0] + 1)
    return [(C[k], R[k]) for k in idx if len(k) >= 2]


def resample(C, R):
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))]; n = max(2, int(round(s[-1] / STEP)) + 1)
    t = np.linspace(0, s[-1], n)
    return np.column_stack([np.interp(t, s, C[:, k]) for k in range(3)]), np.interp(t, s, R)


def build(S, Bones, bone_names, colliders, thorax, tip, qs, log):
    """S: {structure: prims dict(v, f, W)} for the rope structures; Bones: {bone index: wrap_fit.Bone} (rest)"""
    P, R, Wt, own, seg, ends = [], [], [], [], [], []
    names = [n for n in ROPES if n in S]
    for si, n in enumerate(names):
        V = np.vstack([p['v'] for p in S[n]]); W = np.vstack([p['W'] for p in S[n]]); tv = cKDTree(V)
        for C, Rr in rings(V):
            pts, rad = resample(C, Rr); o = len(P)
            near = tv.query(pts, k=12)[1]
            for k in range(len(pts)):
                P.append(pts[k]); R.append(rad[k]); Wt.append(W[near[k]].mean(0)); own.append(si)
                if k: seg.append([o + k - 1, o + k])
            ends += [(o, o + len(pts) - 1, si)]
    P, R, Wt, own = np.array(P), np.array(R), np.array(Wt), np.array(own)
    spl = np.zeros(len(P), int)
    for k, (a, b, _) in enumerate(ends): spl[a:b + 1] = k
    tree, link = cKDTree(P), []
    for k, (a, b, si) in enumerate(ends):                   # spline ends join the nearest particle of another spline
        for e in (a, b):
            d, j = tree.query(P[e], k=16)
            j = [jj for dd, jj in zip(d, j) if spl[jj] != k and dd < LINK_D]
            if j: link.append([e, int(j[0])])
    pin = {}
    for b, B in Bones.items():                              # on (or within PIN_GAP of) a bone: fixed to it
        if b == 1: continue                                 # (not the clavicle: vessels and plexus only pass under it)
        sd = B.signed(P)[0]
        for i in np.where(sd < R + PIN_GAP)[0]:
            if i not in pin or sd[i] < pin[i][1]: pin[i] = (b, sd[i])
    pin = {i: b for i, (b, _) in pin.items()}
    for n, (b, gap) in NEAR_PIN.items():                     # e.g. axillary nerve around the surgical neck
        if n in names:
            m = np.where(own == names.index(n))[0]; sd = Bones[b].signed(P[m])[0]
            for i in m[sd < gap]: pin[int(i)] = b
    pulley = []                                             # under the coracoid / pectoralis minor: a pulley on the scapula
    for si, n in enumerate(names):                          # (the rope slides through it)
        if n.startswith(UNDER_CORACOID):
            m = np.where(own == si)[0]; d = np.linalg.norm(P[m] - tip, axis=1); k = int(m[d.argmin()])
            if d.min() < 45 * MM: pulley.append([si, P[k].round(5).tolist(), 2]); pin.pop(k, None)
    if 'Axillary nerve' in names and qs is not None:        # quadrangular space: lateral border = surgical neck (NEAR_PIN)
        m = np.where(own == names.index('Axillary nerve'))[0]; k = m[np.linalg.norm(P[m] - qs, axis=1).argmin()]
        log('  axillary nerve: nearest particle to the quadrangular space %.0f mm from its centre, %s' %
            (np.linalg.norm(P[k] - qs) * 1000, 'pinned (humerus)' if pin.get(int(k)) == 3 else 'free'))
    allc = colliders + [dict(type='ellipsoid', bone='thorax', c=thorax['c'], axes=thorax['axes'], r=thorax['r'])]
    need = np.column_stack([np.minimum(WF.clearance(C, P), R + 0.5 * MM) for C in allc])
    for si, n in enumerate(names):
        m = own == si; pins = [i for i in pin if own[i] == si]
        log('  rope %-48s %3d particles, %4.0f mm, pins %s' % (n, m.sum(), sum(np.linalg.norm(P[a] - P[b]) for a, b in seg if own[a] == si) * 1000,
            ','.join(sorted({bone_names[pin[i]] if pin[i] >= 0 else 'tissue' for i in pins})) + (' + coracoid pulley' if any(q[0] == si for q in pulley) else '') or '-'))
    log('ropes: %d particles, %d links, %d pinned' % (len(P), len(link), len(pin)))
    return dict(names=names, p=P.round(5).tolist(), r=R.round(5).tolist(), w=Wt.round(3).tolist(), s=own.tolist(),
                seg=seg, link=link, pin=[[int(i), int(b)] for i, b in sorted(pin.items())], pulley=pulley,
                need=need.round(5).tolist(), colliders=allc)
