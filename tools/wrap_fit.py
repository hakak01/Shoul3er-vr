"""Phase D2 simple shapes: thorax ellipsoid (scapular gliding surface, Seth 2016), scapula contact samples,
humeral head sphere and capsules for the rope colliders, and a signed distance to the real bones."""
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from gapgeom import MM, unit
import rig_pose as RP

CONTACT_LEVEL = 0.98          # scapula samples stay at ellipsoid level >= min(rest level, this)


class Bone:
    """Signed distance to a closed bone mesh from oriented surface samples; sign by a vote of 8 neighbours
    (works deep inside thick bone; thin blades read as 'outside', which is fine for a >2 mm test)."""
    def __init__(self, parts):
        P, N = [], []
        for v, f in parts:
            a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]; fn = unit(np.cross(b - a, c - a))
            for w in ((1 / 3, 1 / 3), (0.6, 0.2), (0.2, 0.6), (0.2, 0.2)):
                P.append(a + w[0] * (b - a) + w[1] * (c - a)); N.append(fn)
        self.t, self.n = cKDTree(np.vstack(P)), np.vstack(N)

    def signed(self, x, far=0.05):
        """-> signed distance (negative inside), nearest surface point, its normal; points > far away read +far"""
        d, i = self.t.query(x, k=8, distance_upper_bound=far); ok = np.isfinite(d[:, 0])
        ii = np.where(np.isfinite(d), i, 0)
        s = np.where(np.isfinite(d), np.sign(np.einsum('ikj,ikj->ik', x[:, None] - self.t.data[ii], self.n[ii])), 0).sum(1)
        inside = (s < 0) & ((d[:, 0] < 6 * MM) | (s <= -8))        # far from the surface: all 8 must agree
        sd = np.full(len(x), far); sd[ok] = np.where(inside[ok], -d[ok, 0], d[ok, 0])
        return sd, self.t.data[ii[:, 0]], self.n[ii[:, 0]]


def thorax(P, ribs, scap, rib_bone, log):
    """Ellipsoid fitted to the ribs the scapula sweeps over, scaled to enclose 99% of them; scapula costal samples."""
    rig = P.rig; Ft = P.F['thorax']; O = np.array(rig['landmarks']['IJ'])
    sweep = []
    for e in range(0, 181, 15):
        for pl in (0, 40, 90):
            D = P.deltas(dict(elev=e, plane=pl)); sweep.append(scap[::7] @ D[2, :3, :3].T + D[2, :3, 3])
    reg = cKDTree(np.vstack(sweep)).query(ribs)[0] < 0.04; Rt = (ribs[reg] - O) @ Ft
    res = lambda q: (np.linalg.norm((Rt - q[:3]) / q[3:], axis=1) - 1) * q[3:].mean()
    q = least_squares(res, [-0.06, -0.15, 0.0, 0.10, 0.2, 0.14],
                      bounds=([-0.2, -0.4, -0.1, 0.05, 0.05, 0.05], [0.05, 0.1, 0.15, 0.25, 0.4, 0.25])).x
    lv = np.linalg.norm((Rt - q[:3]) / q[3:], axis=1); r = q[3:] * np.percentile(lv, 99)
    c = O + Ft @ q[:3]; level = lambda x: np.linalg.norm(((x - c) @ Ft) / r, axis=1)
    near = np.where(rib_bone.signed(scap)[0] < 0.015)[0]
    samp = near[np.random.default_rng(0).choice(len(near), min(80, len(near)), replace=False)]
    tgt = np.minimum(level(scap[samp]), CONTACT_LEVEL)
    log('thorax ellipsoid (thorax frame, mm): centre', (q[:3] * 1000).round(1), 'radii', (r * 1000).round(1),
        '| %d rib vertices under the scapula path, %d scapula samples' % (reg.sum(), len(samp)))
    return dict(c=c.round(5).tolist(), axes=Ft.round(5).tolist(), r=r.round(5).tolist(),
                samples=scap[samp].round(5).tolist(), target=tgt.round(4).tolist()), ribs[reg]


def capsule(V, a, b, pct=20):
    """capsule a->b with radius = pct-th percentile of the bone's distance from the segment (within its length)"""
    ab = b - a; t = (V - a) @ ab / (ab @ ab); m = (t > 0.1) & (t < 0.9)
    d = np.linalg.norm(V[m] - (a + np.outer(t[m], ab)), axis=1)
    return float(np.percentile(d, pct))


def colliders(rig, bones, log):
    """bones: {name: vertices}. Shapes the ropes may not enter (deeper than they were at rest)."""
    J = {k: np.array(v) for k, v in rig['joints'].items()}; Ft = np.array(rig['frames']['thorax'])
    gh, el = J['humerus'], J['ulna']; ax = unit(el - gh)
    a, b = gh + ax * 35 * MM, el - ax * 30 * MM
    C = [dict(type='sphere', bone='humerus', c=gh, r=rig['ghRadius']),
         dict(type='capsule', bone='humerus', a=a, b=b, r=capsule(bones['Humerus'], a, b))]
    sc, ac = J['clavicle'], J['scapula']
    C.append(dict(type='capsule', bone='clavicle', a=sc + (ac - sc) * 0.08, b=ac - (ac - sc) * 0.08,
                  r=capsule(bones['Clavicle'], sc, ac)))
    S = bones['Scapula']; tip = S[((S - J['thorax']) @ Ft[:, 0]).argmax()]          # most anterior point = coracoid tip
    near = S[np.linalg.norm(S - tip, axis=1) < 30 * MM]; base = near[np.linalg.norm(near - tip, axis=1).argmax()]
    C.append(dict(type='capsule', bone='scapula', a=tip, b=base, r=0.5 * capsule(S, tip, base, 50)))
    for c in C:
        for k in ('c', 'a', 'b'):
            if k in c: c[k] = np.round(c[k], 5).tolist()
        c['r'] = round(float(c['r']), 5)
    log('rope colliders: ' + ', '.join('%s %s r %.1f mm' % (c['bone'], c['type'], c['r'] * 1000) for c in C) + ' + thorax ellipsoid')
    return C, tip


def clearance(C, x):
    """signed clearance (m) of points x (n,3) from one collider in rest coordinates"""
    if C['type'] == 'sphere': return np.linalg.norm(x - C['c'], axis=1) - C['r']
    if C['type'] == 'capsule':
        a, b = np.array(C['a']), np.array(C['b']); ab = b - a; t = np.clip((x - a) @ ab / (ab @ ab), 0, 1)
        return np.linalg.norm(x - (a + np.outer(t, ab)), axis=1) - C['r']
    c, E, r = np.array(C['c']), np.array(C['axes']), np.array(C['r'])     # ellipsoid: approx metres from the level
    lv = np.linalg.norm(((x - c) @ E) / r, axis=1); return (lv - 1) * r.min()
