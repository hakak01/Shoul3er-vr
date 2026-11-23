"""Phase D1 skin weights. Bones: thorax (ribs, sternum, spine), clavicle, scapula, humerus, ulna, radius.
- bones/context bones: rigid; footprints: rigid to their nearest bone
- muscles: blended along their own length from origin to insertion footprints (missing footprint -> the
  far end of the muscle's long axis); the switch happens where the crossed joint lies; muscles from the
  girdle to the forearm (long heads of biceps and triceps, short head of biceps) get 3 bones
- ligaments, capsule, bursae, sheaths: between the two bones they touch
- skin, fat, fascia, nerves, vessels, nodes, landmarks: smooth weights from the nearest bones"""
import re
import numpy as np
import scipy.sparse as sp
from scipy.spatial import cKDTree
from gapgeom import MM, unit, sample_surface

BONES = ['thorax', 'clavicle', 'scapula', 'humerus', 'ulna', 'radius']
PARENT = [-1, 0, 1, 2, 3, 4]
MAIN = {'Clavicle': 1, 'Scapula': 2, 'Humerus': 3, 'Ulna': 4, 'Radius': 5}
GIRDLE, FORE = {0, 1, 2}, {4, 5}
RIGID = {'Glenoid labrum': 2, 'Annular ligament of radius': 4}
PAIRS = {'Ulnar collateral ligament': [3, 4], 'Radial collateral ligament': [3, 4], 'Quadrate ligament': [4, 5]}
SOFT_SIGMA, CONTACT = 10 * MM, 2.5 * MM


def smoothstep(a, b, x):
    t = np.clip((x - a) / max(b - a, 1e-9), 0, 1); return t * t * (3 - 2 * t)


class Field:
    """Distance from points to each bone surface."""
    def __init__(self, bone_meshes):                        # {bone index: [(V, F), ...]}
        self.trees = {b: cKDTree(np.vstack([sample_surface(v, f, 1.5 * MM) for v, f in ms])) for b, ms in bone_meshes.items()}

    def dists(self, P):
        D = np.full((len(P), len(BONES)), 1e3)
        for b, t in self.trees.items():
            D[:, b] = t.query(P, distance_upper_bound=0.3)[0]
        return np.minimum(D, 1e3)

    def nearest(self, P):
        D = self.dists(P); return D.argmin(1), D.min(1)


def weld(prims):
    """Unique positions over all primitives of one object -> U, per-primitive index maps, sparse adjacency."""
    allv = np.vstack([v for v, f in prims]); key = np.round(allv / (0.01 * MM)).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel(); U = allv[first]; maps, faces, o = [], [], 0
    for v, f in prims:
        m = inv[o:o + len(v)]; maps.append(m); faces.append(m[f]); o += len(v)
    F = np.vstack(faces); i = np.r_[F[:, 0], F[:, 1], F[:, 2]]; j = np.r_[F[:, 1], F[:, 2], F[:, 0]]
    A = sp.coo_matrix((np.ones(len(i)), (i, j)), shape=(len(U), len(U))).tocsr()
    A = ((A + A.T) > 0).astype(float)
    return U, maps, A


def smooth(W, A, iters):
    deg = np.asarray(A.sum(1)).ravel(); deg[deg == 0] = 1
    for _ in range(iters):
        W = 0.5 * W + 0.5 * (A @ W) / deg[:, None]
    return W / W.sum(1, keepdims=True)


def soft(field, U):
    D = field.dists(U); W = np.exp(-(D - D.min(1, keepdims=True)) / SOFT_SIGMA)
    W[W < np.sort(W, 1)[:, -4:-3]] = 0                       # keep 4 bones
    return W / W.sum(1, keepdims=True)


def rigid(n, b):
    W = np.zeros((n, len(BONES))); W[:, b] = 1; return W


def contact(field, U, name=''):
    """Ligament / capsule / bursa: blend between the two bones it touches (or soft if it touches none)."""
    D = field.dists(U); cnt = (D < CONTACT).sum(0)
    bs = PAIRS.get(name) or [b for b in np.argsort(-cnt) if cnt[b] >= max(min(8, 0.05 * len(U)), 0.05 * cnt.max(), 1)][:2]
    if not bs: return soft(field, U), None
    if len(bs) == 1: return rigid(len(U), bs[0]), None
    b1, b2 = bs; t = D[:, b1] / np.maximum(D[:, b1] + D[:, b2], 1e-9)
    W = np.zeros((len(U), len(BONES))); W[:, b2] = smoothstep(0, 1, t); W[:, b1] = 1 - W[:, b2]
    return W, (int(b1), int(b2))


def chain(bo, bi):
    if bo == bi: return [bo]
    if bo in GIRDLE and bi in FORE: return [bo, 3, bi]
    if bo in FORE and bi in GIRDLE: return [bo, 3, bi]
    return [bo, bi]


def joint_between(a, b, J):
    s = {a, b}
    if 3 in s and s & GIRDLE: return J['humerus']
    if 3 in s and s & FORE: return J['ulna']
    if s == {0, 1}: return J['clavicle']
    if s == {1, 2}: return J['scapula']
    return None


LEVEL = np.array([0, 1, 1, 2, 3, 3])          # trunk, girdle, arm, forearm
FORCE_INS = {'Short head of biceps brachii': 5}  # its distal end merges into the long-head object


def muscle(field, U, P, J, A, name=''):
    """P: footprint points of this muscle (any kind). The attachments are the footprints plus the muscle's own
    end caps that touch bone; origin = lowest bone level, insertion = highest. Returns W, line or None."""
    ax = unit(np.linalg.eigh(np.cov((U - U.mean(0)).T))[1][:, 2]); s = U @ ax
    caps = [U[s < np.quantile(s, 0.03)], U[s > np.quantile(s, 0.97)]]
    pb, pd = field.nearest(P) if len(P) else (np.zeros(0, int), np.zeros(0))
    pb = np.where(pd > 15 * MM, 0, pb)                                     # footprint on an absent bone = trunk
    pts, lab = [P], [pb]
    for c in caps:
        cb, cd = field.nearest(c); ok = cd < 6 * MM
        pts.append(c[ok]); lab.append(cb[ok])
    pts, lab = np.vstack(pts), np.concatenate(lab); lv = LEVEL[lab] if len(lab) else lab
    if len(lab) and lv.min() < lv.max():
        O, lo_b, I, li_b = pts[lv == lv.min()], lab[lv == lv.min()], pts[lv == lv.max()], lab[lv == lv.max()]
    else:                                                                   # one level only: far cap = other end
        O = pts if len(pts) >= 5 else caps[0]
        I = max(caps, key=lambda c: np.linalg.norm(c.mean(0) - O.mean(0)))
        lo_b, li_b = field.nearest(O)[0], field.nearest(I)[0]
        if len(pts) >= 5: lo_b = lab
    if name in FORCE_INS: li_b = np.full(len(I), FORCE_INS[name])
    to, ti = cKDTree(O), cKDTree(I)
    do, io = to.query(U); di, ii = ti.query(U)
    t = do / np.maximum(do + di, 1e-9); bo, bi = lo_b[io], li_b[ii]
    W = np.zeros((len(U), len(BONES)))
    for pair in set(zip(bo.tolist(), bi.tolist())):
        m = (bo == pair[0]) & (bi == pair[1]); ch = chain(*pair)
        tj = []
        for a, b in zip(ch[:-1], ch[1:]):
            P = joint_between(a, b, J)
            if P is None: tj.append(0.5); continue
            dj, dk = to.query(P)[0], ti.query(P)[0]; tj.append(float(np.clip(dj / (dj + dk), 0.12, 0.88)))
        if len(tj) == 2: tj[1] = max(tj[1], tj[0] + 0.15)
        prev = np.ones(m.sum())
        for k, b in enumerate(ch):
            nxt = smoothstep(tj[k] - 0.2, tj[k] + 0.2, t[m]) if k < len(tj) else np.zeros(m.sum())
            W[m, b] += prev - nxt; prev = nxt
    W = smooth(np.clip(W, 0, 1) + 1e-9, A, 4)
    mode = lambda x: int(np.bincount(x, minlength=len(BONES)).argmax())
    line = (O.mean(0), mode(lo_b), I.mean(0), mode(li_b))
    return W, (line if line[1] != line[3] else None)


def fibres(U, W, pair, ant, n):
    """Tension sectors around the ligament's own axis: centre, axis, reference, [(p1, p2)] per sector."""
    b1, b2 = pair; m1, m2 = W[:, b1] > 0.8, W[:, b2] > 0.8
    if m1.sum() < 1 or m2.sum() < 1: return None
    c1, c2 = U[m1].mean(0), U[m2].mean(0); u = unit(c2 - c1); c = (c1 + c2) / 2
    r = unit(ant - u * (ant @ u)); q = np.cross(u, r)
    d = U - c; k = np.floor((np.arctan2(d @ q, d @ r) + np.pi) / (2 * np.pi) * n).astype(int) % n
    out, t = [], W[:, b2]
    for s in range(n):
        a, b = U[m1 & (k == s)], U[m2 & (k == s)]
        p1, p2 = (a.mean(0) if len(a) > 2 else c1), (b.mean(0) if len(b) > 2 else c2)
        mids = [U[(k == s) & (t >= lo) & (t < lo + 0.1)] for lo in np.arange(0.2, 0.8, 0.1)]
        path = np.vstack([p1] + [x.mean(0) for x in mids if len(x) > 2] + [p2])
        L = max(np.linalg.norm(np.diff(path, axis=0), axis=1).sum(), np.linalg.norm(p2 - p1))   # rest length along the tissue
        out.append([p1.round(5).tolist(), p2.round(5).tolist(), round(float(L), 5)])
    return dict(bones=[BONES[b1], BONES[b2]], c=c.round(5).tolist(), u=u.round(5).tolist(), r=r.round(5).tolist(), n=n, fib=out)


def footprint_key(name):
    m = re.match(r'(.*) \((origin|insertion)( \d+)?\)$', name)
    return (m.group(1), m.group(2)) if m else (None, None)


def group_match(base, muscle_name):
    if base == muscle_name or base.startswith('Common '): return True
    k = re.sub(r' (muscle|brachii)', '', base).lower()
    return k in muscle_name.lower()
