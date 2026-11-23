"""Phase B landmarks: faint outlined patches for surgical spaces/notches/grooves (approx:true).
Openings: the bounding bone/muscle are projected along a viewing direction (posterior view for the spaces,
along the nerve for the notches, from outside the capsule for the rotator interval); the enclosed hole nearest
to the passing nerve/vessel becomes the patch, and its depth is interpolated from the surrounding surfaces.
Also writes the glenohumeral centre (sphere fit to the humeral head cartilage) into assets/model.json.
Run: python3 -I tools/build_landmarks.py   (reads data/raw/shoulder_raw.glb; glTF frame: x- lateral, y up, z anterior)
"""
import os, sys, json, subprocess
import numpy as np
from scipy.spatial import cKDTree, ConvexHull, Delaunay
import scipy.ndimage as ndi
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import glbio, gapgeom as G
from gapgeom import MM, unit

RAW = os.path.join(ROOT, 'data/raw/shoulder_raw.glb')
RAW_OUT = os.path.join(ROOT, 'data/raw/landmarks_raw.glb')
OUT = os.path.join(ROOT, 'assets')
D = glbio.read(RAW)
POST, ANT, UP = np.array([0, 0, -1.]), np.array([0, 0, 1.]), np.array([0, 1., 0])

TS, TMJ, LHT = 'Teres minor muscle', 'Teres major muscle', 'Long head of triceps brachii'
LHD = 'Lateral head of triceps brachii'


def get(name, mat=None):
    ps = [(v, f) for v, f, m in D[name] if mat is None or m == mat]
    return G.merge(ps)


def pts(names, spacing=0.7 * MM):
    return np.vstack([G.sample_surface(*get(n), spacing=spacing) for n in names])


def gh_centre():
    V = get('Humerus', 'Cartilage')[0]
    V = V[V[:, 1] > V[:, 1].max() - 0.06]                       # proximal (head) cartilage only
    A = np.c_[2 * V, np.ones(len(V))]; b = (V ** 2).sum(1)
    s = np.linalg.lstsq(A, b, rcond=None)[0]; c = s[:3]; r = np.sqrt(s[3] + c @ c)
    res = np.linalg.norm(V - c, axis=1) - r
    return c, r, np.abs(res).mean()


def centreline(names):
    P = np.vstack([get(n)[0] for n in names]); t = cKDTree(P)
    return np.array([P[i].mean(0) for i in t.query_ball_point(P, 3 * MM)])


def seed_on(through, bounds, rmax):
    """Point of the passing structure that is surrounded best by the bounding structures."""
    trees = [cKDTree(pts([b])) for b in bounds]
    P = centreline(through)
    d = np.stack([t.query(P)[0] for t in trees], 1)
    score = np.where(d.max(1) < rmax * MM, d.min(1), -d.max(1))
    i = score.argmax(); near = P[np.linalg.norm(P - P[i], axis=1) < 8 * MM]
    return P[i], G.pca_axis(near)[1]


class Plane:
    def __init__(s, C, n):
        s.C, s.n = C, unit(n); s.u = unit(np.cross(s.n, [0.3, 1, 0.2])); s.v = np.cross(s.n, s.u)
    def to2(s, P):
        q = P - s.C; return np.c_[q @ s.u, q @ s.v], q @ s.n
    def to3(s, uv, d):
        return s.C + np.outer(uv[:, 0], s.u) + np.outer(uv[:, 1], s.v) + np.outer(d, s.n)


class Shell(Plane):           # gnomonic map of a sphere around the GH centre (for the capsule)
    def __init__(s, O, C, R):
        super().__init__(C, C - O); s.O, s.R = O, R
    def to2(s, P):
        q = P - s.O; t = np.maximum(q @ s.n, 1e-6)
        return s.R * np.c_[q @ s.u, q @ s.v] / t[:, None], np.linalg.norm(q, axis=1) - s.R
    def to3(s, uv, d):
        di = unit(s.n * s.R + np.outer(uv[:, 0], s.u) + np.outer(uv[:, 1], s.v)); return s.O + di * (s.R + d)[:, None]


def opening(fr, bounds, slab, win, amin=15, hull=False, nang=60, px=0.5 * MM):
    """Hole enclosed by the bounding structures as seen along fr.n (only samples within the depth slab)."""
    S = [pts([b], 0.5 * MM) for b in bounds]; lab = np.repeat(np.arange(len(S)), [len(x) for x in S])
    uv, dep = fr.to2(np.vstack(S)); keep = (dep > slab[0] * MM) & (dep < slab[1] * MM) & (np.abs(uv).max(1) < win * MM)
    uv, dep, lab = uv[keep], dep[keep], lab[keep]
    N = int(2 * win * MM / px) + 1; ij = np.clip(((uv + win * MM) / px).astype(int), 0, N - 1)
    occ = np.zeros((N, N), bool); own = np.full((N, N), -1)
    for j in range(len(S)):                   # each wall's own section is solid (fill its inside)
        o1 = np.zeros((N, N), bool); o1[ij[lab == j, 0], ij[lab == j, 1]] = True
        o1 = ndi.binary_fill_holes(ndi.binary_closing(o1, iterations=2)); occ |= o1; own[o1] = j
    if hull:                  # close wide gaps: everything outside the convex hull of the walls counts as wall
        O = np.argwhere(occ); hv = O[ConvexHull(O).vertices]
        occ |= (Delaunay(hv).find_simplex(np.argwhere(np.ones_like(occ))) < 0).reshape(N, N)
    o = np.argsort(-np.abs(dep)); dmap = np.full((N, N), np.nan); dmap[ij[o, 0], ij[o, 1]] = dep[o]
    c0, best = N // 2, None
    for kd in range(1, 12):                   # close gaps up to kd pixels; score every enclosed hole
        lbl, nl = ndi.label(~ndi.binary_dilation(occ, iterations=kd))
        edge = set(np.unique(np.r_[lbl[0], lbl[-1], lbl[:, 0], lbl[:, -1]]))
        area = np.bincount(lbl.ravel()) * px * px / MM ** 2
        for h in [h for h in range(1, nl + 1) if h not in edge and area[h] >= amin]:
            Hh = ndi.binary_dilation(lbl == h, iterations=kd) & ~occ
            ow = own[ndi.binary_dilation(Hh, iterations=2) & occ]; ow = ow[ow >= 0]
            sh = np.bincount(ow, minlength=len(S)) / max(len(ow), 1)
            dc = np.hypot(*(np.argwhere(Hh).mean(0) - c0))
            sc = ((sh >= 0.08).sum(), -kd, -dc)
            if dc < 0.7 * N / 2 and (best is None or sc > best[0]):
                best = (sc, Hh, kd, sh)
    if best is None:
        return None
    score, H, kd, share = best
    ring = ndi.binary_dilation(H, iterations=2) & occ
    fix = ring & ~np.isnan(dmap); d = np.where(fix, dmap, np.nanmean(dmap[fix])); M = H | ring
    for _ in range(600):
        avg = (np.roll(d, 1, 0) + np.roll(d, -1, 0) + np.roll(d, 1, 1) + np.roll(d, -1, 1)) / 4
        d = np.where(M & ~fix, avg, d)
    I = np.argwhere(H); cc = I.mean(0); rel = (I - cc) * px
    ang = np.linspace(-np.pi, np.pi, nang, endpoint=False); bins = ((np.arctan2(rel[:, 1], rel[:, 0]) + np.pi) / (2 * np.pi) * nang).astype(int) % nang
    r = np.zeros(nang); np.maximum.at(r, bins, np.linalg.norm(rel, axis=1) + px / 2)
    r = G.smooth1d(np.array([np.median(np.take(r, range(k - 2, k + 3), mode='wrap')) for k in range(nang)]), 1.2, wrap=True)
    rings = np.linspace(0, 1, 7)
    U = np.vstack([cc * px - win * MM + t * r[:, None] * np.c_[np.cos(ang), np.sin(ang)] for t in rings[1:]])
    U = np.vstack([cc * px - win * MM, U])
    pij = np.clip(np.rint((U + win * MM) / px).astype(int), 0, N - 1)
    V = fr.to3(U, ndi.gaussian_filter(d, 2)[pij[:, 0], pij[:, 1]])
    F = [[0, 1 + k, 1 + (k + 1) % nang] for k in range(nang)]
    for q in range(len(rings) - 2):
        a0, b0 = 1 + q * nang, 1 + (q + 1) * nang
        for k in range(nang):
            k1 = (k + 1) % nang; F += [[a0 + k, b0 + k, b0 + k1], [a0 + k, b0 + k1, a0 + k1]]
    F = np.array(F)
    if np.cross(V[F[0, 1]] - V[0], V[F[0, 2]] - V[0]) @ fr.n < 0:
        F = F[:, ::-1]
    edge = V[-nang:]
    info = 'area %.0f mm2, gap closed %.1f mm, edge on: %s' % (H.sum() * px * px / MM ** 2, kd * px / MM, ', '.join(
        '%s %d%%' % (bounds[j].split(' muscle')[0], 100 * share[j]) for j in range(len(bounds)) if share[j] > 0))
    return V, F, np.vstack([edge, edge[:1]]), info, V[0], fr.n, score


def scan(make, bounds, offs, half, win, amin=15, hull=False):
    """Try sections at several depths; keep the one whose edge touches most bounding structures."""
    sl = half if isinstance(half, tuple) else (-half, half)
    res = [opening(make(o * MM if np.isscalar(o) else (o[0], o[1] * MM)), bounds, sl, win, amin, hull) for o in offs]
    res = [r for r in res if r is not None]
    best = max(res, key=lambda r: r[-1])
    return best[:-1]


def groove():
    """Deltopectoral groove: strip along the cephalic vein between the deltoid and pectoralis major rims."""
    vein = centreline(['Cephalic vein'])
    dl = pts(['Clavicular part of deltoid muscle']); pm = pts(['Clavicular head of pectoralis major muscle',
                                                               'Sternocostal head of pectoralis major muscle'])
    td, tp = cKDTree(dl), cKDTree(pm)
    ys = np.arange(vein[:, 1].max(), vein[:, 1].min(), -3 * MM)
    rows = []
    for y in ys:
        s = vein[np.abs(vein[:, 1] - y) < 1.5 * MM]
        if not len(s):
            rows.append(None); continue
        c = s.mean(0); a, b = td.query(c)[0], tp.query(c)[0]
        if a > 15 * MM or b > 15 * MM:
            rows.append(None); continue
        rim = []
        for t, Q, d0 in ((td, dl, a), (tp, pm, b)):
            idx = t.query_ball_point(c, d0 + 4 * MM); q = Q[idx]
            rim.append(q[(q[:, 2]).argmax()])                       # most anterior (superficial) point = rim
        rows.append((c, rim[0], rim[1]))
    best, cur = [], []
    for r in rows + [None]:
        if r is None:
            best = cur if len(cur) > len(best) else best; cur = []
        else:
            cur.append(r)
    A = G.smooth1d(np.array([r[1] for r in best]), 1.0); B = G.smooth1d(np.array([r[2] for r in best]), 1.0)
    ncol = 5; t = np.linspace(0, 1, ncol)
    V = np.vstack([a + np.outer(t, b - a) for a, b in zip(A, B)]) + ANT * 0.5 * MM
    F = []
    for i in range(len(A) - 1):
        for j in range(ncol - 1):
            p = i * ncol + j
            F += [[p, p + ncol, p + ncol + 1], [p, p + ncol + 1, p + 1]]
    F = np.array(F)
    n = G.unit(np.cross(V[F[0, 1]] - V[F[0, 0]], V[F[0, 2]] - V[F[0, 0]]))
    if n @ ANT < 0:
        F = F[:, ::-1]
    edge = np.vstack([A, B[::-1], A[:1]])
    w = np.linalg.norm(A - B, axis=1) / MM
    info = 'length %.0f mm, width %.1f-%.1f mm' % (np.linalg.norm(np.diff(A, axis=0), axis=1).sum() / MM, w.min(), w.max())
    return V, F, edge, info, V.mean(0), ANT


def main():
    c, r, res = gh_centre()
    log = ['GH centre (glTF m) %s, head radius %.1f mm, fit residual %.2f mm' % (np.round(c, 4).tolist(), r / MM, res / MM)]
    items = []
    B = [TS, TMJ, LHT, 'Humerus']
    ax = centreline(['Axillary nerve']); q = ax[ax[:, 2].argmin()] + POST * 6 * MM   # its posterior end
    items.append(('Quadrangular space', scan(lambda o: Plane(q + POST * o, POST), B, range(-6, 25, 3), 6, 30), POST,
                  'teres minor, teres major, long head of triceps, surgical neck; coronal sections'))
    items.append(('Triangular space', scan(lambda o: Plane(q + [0.025, -0.035, 0], POST), B[:3], [0], 60, 45), POST,
                  'teres minor, teres major, long head of triceps; posterior view'))
    B = [TMJ, LHT, LHD, 'Humerus']
    q, _ = seed_on(['Radial nerve', 'Deep brachial artery'], B, 25)
    items.append(('Triangular interval', scan(lambda o: Plane(q + POST * o, POST), B, range(-12, 13, 4), 8, 30), POST,
                  'teres major, long head of triceps, lateral head of triceps/humerus; posterior view'))
    for nm, lig, out in (('Suprascapular notch', 'Superior', UP), ('Spinoglenoid notch', 'Inferior', POST)):
        B = ['Scapula', lig + ' transverse scapular ligament']
        q, t = seed_on(['Suprascapular nerve'], B, 10)
        L = get(B[1])[0]; w, E = np.linalg.eigh(np.cov((L - L.mean(0)).T))
        ns = [t, unit(t - (t @ E[:, 2]) * E[:, 2]), E[:, 0], E[:, 1]]          # across the nerve / the ligament
        items.append((nm, scan(lambda o: Plane(q + ns[o[0]] * o[1], ns[o[0]]), B,
                               [(i, o) for i in range(4) for o in (-4, -2, 0, 2, 4)], 7, 15, amin=3), out,
                      'scapula and %s transverse scapular ligament, across the suprascapular nerve' % lig.lower()))
    B = ['Supraspinatus muscle', 'Subscapularis muscle', 'Scapula', 'Transverse humeral ligament', 'Humerus']
    q, _ = seed_on(['Coracohumeral ligament'], B[:2], 30)
    items.append(('Rotator interval', scan(lambda o: Shell(c, q, np.linalg.norm(q - c)), B, [0], (-6, 25), 30, hull=True), q - c,
                  'supraspinatus and subscapularis tendons, coracoid base; on the capsule'))
    items.append(('Deltopectoral groove', groove(), ANT, 'deltoid and pectoralis major rims along the cephalic vein'))
    objs, man = [], []
    for name, (V, F, edge, info, C, n), out, ref in items:
        Vt, Ft = G.tube(G.catmull(edge[:-1].tolist() + [edge[0]], 2), 0.35 * MM, 5)
        objs.append((name, [(V, F, 'Landmark'), (V, F[:, ::-1], 'Landmark'), (Vt, Ft, 'Landmark-outline')]))
        lab = V.mean(0) + (n if n @ out > 0 else -n) * 14 * MM
        man.append(dict(name=name, layer='landmark', source='Approximate landmark, build_landmarks.py (%s)' % ref,
                        approx=True, triangles=int(2 * len(F) + len(Ft)), label=np.round(lab, 4).tolist()))
        log.append('%-22s %s' % (name, info))
    glbio.write(RAW_OUT, objs)
    json.dump(man, open(os.path.join(OUT, 'landmarks.json'), 'w'), indent=1)
    subprocess.run('npx -y -q @gltf-transform/cli meshopt "%s" "%s" --level medium' % (
        RAW_OUT, os.path.join(OUT, 'landmarks.glb')), shell=True, check=True, stdout=subprocess.DEVNULL)
    mp = os.path.join(OUT, 'model.json')
    M = json.load(open(mp)) if os.path.exists(mp) else {}
    M.update(glb='shoulder.glb', gaps='gaps.glb', landmarks='landmarks.glb', title='Shoulder & arm',
             center=np.round(c, 4).tolist())
    json.dump(M, open(mp, 'w'), indent=1)
    log.append('landmarks.glb %.0f kB' % (os.path.getsize(os.path.join(OUT, 'landmarks.glb')) / 1e3))
    print('\n'.join(log))


if __name__ == '__main__':
    main()
