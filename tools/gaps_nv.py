"""Phase C nerves and vessels (approx:true): lateral and medial cords (+ roots of the median nerve and the
proximal musculocutaneous nerve), superior thoracic artery, deltoid / acromial / clavicular branches of the
thoraco-acromial artery, intercostobrachial nerve. Tubes along waypoints taken from the existing anatomy,
pushed out of bone. Frame (glTF): x- lateral, y up, z anterior. Units: metres."""
import numpy as np
from scipy.spatial import cKDTree
import gapgeom as G
from gapgeom import MM, unit

LAT, UP, ANT = np.array([-1., 0, 0]), np.array([0, 1., 0]), np.array([0, 0, 1.])
R_CORD = 2.5 * MM            # cords (the trunks/divisions here are ~2-3 mm)
FLATOW = 56 * MM             # musculocutaneous entry into coracobrachialis below the coracoid (Flatow 1989 mean)


def centreline(K, name, ylim=None, step=2 * MM):
    P = K.get(name)[0]
    t = cKDTree(P); Q = np.array([P[i].mean(0) for i in t.query_ball_point(P, 4 * MM)])
    if ylim:
        Q = Q[(Q[:, 1] > K.C[1] + ylim[0]) & (Q[:, 1] < K.C[1] + ylim[1])]
    c, a = G.pca_axis(Q); s = (Q - c) @ a
    b = np.arange(s.min(), s.max() + step, step)
    L = np.array([Q[(s >= x) & (s < x + step)].mean(0) for x in b if ((s >= x) & (s < x + step)).any()])
    return G.smooth1d(L, 1.0)


def radius(K, name):
    P = K.get(name)[0]; L = centreline(K, name)
    return float(np.median(cKDTree(L).query(P)[0]))


def end_near(L, target):
    return L[0] if np.linalg.norm(L[0] - target) < np.linalg.norm(L[-1] - target) else L[-1]


def toward(L, target):
    """centreline oriented so that it starts at the end nearest the target"""
    return L if np.linalg.norm(L[0] - target) < np.linalg.norm(L[-1] - target) else L[::-1]


def path_len(P):
    return float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())


class Builder:
    def __init__(self, K, log):
        self.K, self.log, self.items = K, log, []
        bones = [n for n in K.D if K.layer.get(n) in ('bone', 'context_bone') and not K.kind.get(n)]
        self.bone = G.Solid([K.get(n) for n in bones]); self.musc = {}

    def tube(self, name, layer, way, rad, ref, n=24, push=True, avoid=()):
        P = G.catmull(way, n)
        if avoid:                                             # muscles to go round (keep the ends)
            key = tuple(avoid)
            if key not in self.musc:
                self.musc[key] = G.Solid([self.K.get(m) for m in avoid])
            P = self.musc[key].push_out(P, rad + 0.3 * MM, iters=30)
        if push:
            P = self.bone.push_out(P, rad + 0.5 * MM)
        d = self.bone.signed(P)[0]
        rad_arr = np.broadcast_to(rad, (len(P),))
        V, F = G.tube(P, rad_arr, nseg=10)
        self.items.append(dict(name=name, layer=layer, mat={'nerve': 'Nerve', 'artery': 'Artery'}[layer],
                               mesh=(V, F), ref=ref))
        self.log('  %-52s length %4.0f mm, r %.1f mm, min bone clearance %.1f mm' % (
            name, path_len(P) / MM, np.max(rad_arr) / MM, (d.min() - np.max(rad_arr)) / MM))
        return P


def cords(B):
    K, log = B.K, B.log
    art = centreline(K, 'Axillary artery')
    art = art if art[0, 1] > art[-1, 1] else art[::-1]                     # proximal (high, medial) first
    ra = radius(K, 'Axillary artery')
    pm = K.pts(['Pectoralis minor muscle'], spacing=1 * MM)
    # 2nd part: pectoralis minor lies in front of the artery
    cover = np.array([((np.linalg.norm(np.cross(pm - p, ANT), axis=1) < 8 * MM) & ((pm - p) @ ANT > 0)).any() for p in art])
    i1, i2 = np.flatnonzero(cover)[[0, -1]]
    off = ra + R_CORD + 1 * MM
    T = unit(np.gradient(art, axis=0))
    post = unit(-ANT - (-ANT @ T.T)[:, None] * T)
    lat = unit(LAT - (LAT @ T.T)[:, None] * T - (LAT @ post.T)[:, None] * post)
    med = unit(-lat + 0.35 * post)
    idx = np.linspace(i1, i2, 4).round().astype(int)
    log('  axillary artery r %.1f mm; 2nd part (behind pectoralis minor) %.0f mm long' % (ra / MM, path_len(art[i1:i2 + 1]) / MM))
    divs = lambda names: np.mean([end_near(centreline(K, n), art[i1]) for n in names], axis=0)
    dl = divs(['Anterior division of superior trunk of brachial plexus', 'Anterior division of middle trunk of brachial plexus'])
    dm = divs(['Anterior division of inferior trunk of brachial plexus'])
    pl = B.tube('Lateral cord of brachial plexus', 'nerve', [dl] + [art[i] + lat[i] * off for i in idx], R_CORD,
                'anterior divisions of superior + middle trunks; lateral to the 2nd part of the axillary artery',
                avoid=['Pectoralis minor muscle'])
    pmd = B.tube('Medial cord of brachial plexus', 'nerve', [dm] + [art[i] + med[i] * off for i in idx], R_CORD,
                 'anterior division of inferior trunk; medial to the 2nd part of the axillary artery',
                 avoid=['Pectoralis minor muscle', 'Serratus anterior muscle'])
    pc = centreline(K, 'Posterior cord of brachial plexus')
    d = cKDTree(art[i1:i2 + 1]).query(pc)[0]
    log('  existing posterior cord: %.0f-%.0f mm from the artery axis (kept)' % (d.min() / MM, d.max() / MM))
    # median nerve: the two roots meet in front of the 3rd part of the artery
    med_n = centreline(K, 'Median nerve', ylim=(-150 * MM, 40 * MM))
    a3 = art[min(len(art) - 1, i2 + 6)]
    M = med_n[np.argmin(np.linalg.norm(med_n - (a3 + ANT * off), axis=1))]
    B.tube('Lateral root of median nerve', 'nerve', [pl[-1], (pl[-1] + M) / 2 + ANT * 2 * MM, M], 1.8 * MM,
           'lateral cord -> median nerve')
    B.tube('Medial root of median nerve', 'nerve', [pmd[-1], (pmd[-1] + M) / 2 + ANT * (off + 1 * MM), M], 1.8 * MM,
           'medial cord -> median nerve, crossing in front of the artery')
    # musculocutaneous: lateral cord -> pierces coracobrachialis -> existing nerve
    sc = K.get('Scapula')[0]; tip = sc[np.argmax(sc[:, 2])]
    mc = centreline(K, 'Musculocutaneous nerve'); mc0 = end_near(mc, pl[-1])
    cb = K.get('Coracobrachialis muscle')[0]
    lev = cb[np.abs(cb[:, 1] - (tip[1] - FLATOW)) < 2 * MM]
    entry = lev[np.argmax(lev @ -LAT)]                                          # medial surface of the muscle
    inside = lev.mean(0)
    B.tube('Musculocutaneous nerve (proximal part)', 'nerve', [pl[-1], entry + (-LAT) * 2 * MM, inside, mc0], 1.8 * MM,
           'lateral cord -> enters coracobrachialis %.0f mm below the coracoid tip (Flatow 1989 mean) -> existing nerve' % (
               (tip[1] - entry[1]) / MM))
    # other branches: join if their start is far from the cords
    for nm, P in (('Ulnar nerve', pmd), ('Medial brachial cutaneous nerve', pmd), ('Medial antebrachial cutaneous nerve', pmd),
                  ('Lateral pectoral nerve', pl), ('Medial pectoral nerve', pmd)):
        L = centreline(K, nm); s = end_near(L, P[len(P) // 2])
        dd, j = cKDTree(P).query(s)
        if 4 * MM < dd < 25 * MM:
            B.tube(nm + ' (proximal part)', 'nerve', [P[j], (P[j] + s) / 2, s], 1.2 * MM, 'joins the cord')
        else:
            log('  %-52s start %.0f mm from the cord%s' % (nm, dd / MM, '' if dd <= 4 * MM else ' (not joined: too far)'))
    return art, i1, ra


def arteries(B, art, i1, ra):
    K = B.K
    # superior thoracic: 1st part of the axillary artery -> 1st and 2nd intercostal spaces (anterior)
    o = art[max(0, i1 - 5)]
    def space(r1, r2, x):
        a, b = K.pts([r1]), K.pts([r2])
        a = a[np.abs(a[:, 0] - x) < 3 * MM]; b = b[np.abs(b[:, 0] - x) < 3 * MM]
        a, b = a[np.argmax(a[:, 2])], b[np.argmax(b[:, 2])]                    # anterior surfaces
        return (a + b) / 2 + ANT * 3 * MM
    x1 = o[0] + 45 * MM                                                         # ~45 mm medial of the origin
    s1, s2 = space('First rib', 'Second rib', x1), space('Second rib', 'Third rib', x1 - 5 * MM)
    p = B.tube('Superior thoracic artery', 'artery', [o, o + (s1 - o) * 0.4 + ANT * 6 * MM, s1], 1.0 * MM,
               'from the 1st part of the axillary artery to the 1st intercostal space')
    B.tube('Superior thoracic artery (branch to 2nd intercostal space)', 'artery',
           [p[len(p) // 2], (p[len(p) // 2] + s2) / 2 + ANT * 3 * MM, s2], 0.7 * MM, 'to the 2nd intercostal space')
    # thoraco-acromial trunk end
    ta = centreline(K, 'Thoraco-acromial artery')
    t0 = ta[np.argmax(np.linalg.norm(ta - art[np.argmin(np.linalg.norm(art - ta.mean(0), axis=1))], axis=1))]
    sc = K.get('Scapula')[0]; tip = sc[np.argmax(sc[:, 2])]
    hi = sc[sc[:, 1] > K.C[1]]; acr = hi[np.argmax(hi @ (LAT + ANT))]           # anterolateral acromion
    cal = K.get('Coraco-acromial ligament')[0].mean(0)
    B.tube('Acromial branch of thoraco-acromial artery', 'artery',
           [t0, tip + UP * 5 * MM, cal + UP * 3 * MM, acr + ANT * 3 * MM - UP * 2 * MM],
           1.0 * MM, 'over the coracoid and coraco-acromial ligament, deep to the deltoid, to the acromion',
           avoid=['Clavicular part of deltoid muscle', 'Acromial part of deltoid muscle'])
    sub = K.get('Subclavius muscle')[0]
    sx = lambda x: sub[np.abs(sub[:, 0] - x) < 3 * MM]
    a1, a2 = sx(t0[0] + 15 * MM), sx(t0[0] + 40 * MM)
    c1, c2 = a1[np.argmin(a1[:, 1])], a2[np.argmin(a2[:, 1])]                  # lower border of subclavius
    B.tube('Clavicular branch of thoraco-acromial artery', 'artery', [t0, c1 + ANT * 2 * MM - UP * 2 * MM, c2 - UP * 4 * MM],
           0.8 * MM, 'superomedially to the subclavius and the clavicle')
    ce = centreline(K, 'Cephalic vein', ylim=(-80 * MM, 25 * MM))
    ce = ce if ce[0, 1] > ce[-1, 1] else ce[::-1]
    rv = radius(K, 'Cephalic vein')
    side = unit(-ANT + LAT * 0.3)                                                # deep to the vein
    g = [c + side * (rv + 1.5 * MM) for c in ce[::4]]
    B.tube('Deltoid branch of thoraco-acromial artery', 'artery', [t0] + g, 1.0 * MM,
           'in the deltopectoral groove with the cephalic vein',
           avoid=['Clavicular part of deltoid muscle', 'Clavicular head of pectoralis major muscle'])


def icbn(B):
    K = B.K
    r2, r3 = K.get('Second rib')[0], K.get('Third rib')[0]
    a, b = r2[np.argmin(r2[:, 0])], r3[np.argmin(r3[:, 0])]                     # mid-axillary line (most lateral)
    p0 = (a + b) / 2
    sa = K.pts(['Serratus anterior muscle'], spacing=1 * MM)
    near = sa[np.linalg.norm(sa - p0, axis=1) < 12 * MM]
    p1 = near[np.argmax(near @ LAT)] + LAT * 2 * MM if len(near) else p0 + LAT * 8 * MM
    nodes = K.get('Central axillary nodes')[0].mean(0)
    sk = np.vstack([K.get(n, 'Skin-in')[0] for n in ('Medial bicipital groove', 'Posterior region of arm')])
    sub = lambda y: (lambda q: q[np.argmax(q @ -LAT - 0.3 * (q @ ANT))])(sk[np.abs(sk[:, 1] - (K.C[1] + y)) < 3 * MM])
    p3, p4 = sub(-80 * MM) + LAT * 5 * MM, sub(-125 * MM) + LAT * 4 * MM          # under the skin, posteromedial arm
    B.tube('Intercostobrachial nerve', 'nerve', [p0, p1, nodes + UP * 8 * MM + LAT * 4 * MM, p3, p4], 1.0 * MM,
           'lateral cutaneous branch of T2: 2nd intercostal space (mid-axillary line) across the axilla to the medial arm',
           avoid=['Coracobrachialis muscle', 'Short head of biceps brachii', 'Long head of triceps brachii'])


def build(K, log):
    B = Builder(K, log)
    art, i1, ra = cords(B)
    arteries(B, art, i1, ra)
    icbn(B)
    return B.items
