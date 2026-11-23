"""Wrist gaps: long and short radiolunate ligaments, recurrent motor branch of the median nerve,
roof of Guyon's canal. Built in a wrist frame: a (distal), r (radial), p (palmar), origin capitate."""
import numpy as np
from scipy.spatial import cKDTree
import gapgeom as G
from gapgeom import MM


class Frame:
    def __init__(self, c, a=None):
        self.O = c('Capitate bone')
        a = G.unit(c('Third metacarpal bone') - c('Lunate bone')) if a is None else a
        r = c('Scaphoid bone') - c('Triquetrum bone'); r = G.unit(r - (r @ a) * a)
        p = np.cross(a, r)
        if p @ (c('Flexor retinaculum of wrist') - self.O) < 0:
            p = -p
        self.M = np.array([a, r, p])

    def loc(self, X):
        return (np.asarray(X) - self.O) @ self.M.T

    def world(self, L):
        return self.O + np.asarray(L) @ self.M


def heightfield(P, rad=1.2 * MM, low=False):
    """P: local points. h(a, r) = highest palmar point within rad (nan if none);
    low=True: the lowest point instead (a ceiling, e.g. the underside of tendons)."""
    tree = cKDTree(P[:, :2])
    def h(A, R):
        out = np.full(A.shape, np.nan)
        for i, q in enumerate(tree.query_ball_point(np.c_[A.ravel(), R.ravel()], rad)):
            if q:
                out.flat[i] = P[q, 2].min() if low else P[q, 2].max()
        return out
    return h


def fill_rows(H):
    for row in H:
        ok = ~np.isnan(row)
        row[:] = np.interp(np.arange(len(row)), np.nonzero(ok)[0], row[ok]) if ok.any() else np.nan
    ok = ~np.isnan(H[:, 0])
    for j in range(H.shape[1]):
        H[:, j] = np.interp(np.arange(len(H)), np.nonzero(ok)[0], H[ok, j])
    return H


def upper(H, k):
    """Running max (bridges gaps), then smoothing."""
    Hm = np.max([np.roll(np.pad(H, ((k, k), (k, k)), mode='edge'), (i, j), (0, 1))[k:-k, k:-k]
                 for i in range(-k, k + 1) for j in range(-k, k + 1)], 0)
    return G.smooth1d(G.smooth1d(Hm, k, 0), k, 1)


def sheet(W, Agrid, Rgrid, H, thick):
    """Closed slab from a palmar heightfield (local mm grids -> world metres)."""
    inner = W.world(np.stack([Agrid, Rgrid, H], -1))
    outer = W.world(np.stack([Agrid, Rgrid, H + thick], -1))
    return G.slab(inner, outer)


def ribbon(W, h, A, B, width, thick, clear=0.3 * MM, nu=30, nv=7, ceil=None):
    d = B[:2] - A[:2]; L = np.linalg.norm(d); t = d / L; n = np.array([-t[1], t[0]])
    u = np.linspace(0, 1, nu)[:, None]; v = np.linspace(-0.5, 0.5, nv)[None]
    fan = 0.75 + 0.45 * np.abs(2 * u - 1) ** 2          # fibres fan out at both attachments
    Ag = A[0] + u * d[0] + v * width * fan * n[0]
    Rg = A[1] + u * d[1] + v * width * fan * n[1]
    H = h(Ag, Rg)
    H = upper(fill_rows(H), 2) + clear
    th = thick * (1 - 0.5 * (2 * np.abs(v)) ** 4) * (1 - 0.3 * (2 * np.abs(u - 0.5)) ** 6)
    if ceil is not None:            # stay under the tendons: thinner, never < 0.4 mm
        C = ceil(Ag, Rg) - 0.25 * MM
        th = np.where(np.isnan(C), th, np.clip(C - H, 0.4 * MM, th))
    return sheet(W, Ag, Rg, H, th)


def build(get, pts, c):
    W = Frame(c)
    out = []
    def add(name, layer, mat, mesh, ref):
        out.append(dict(name=name, layer=layer, mat=mat, mesh=mesh, ref=ref))
    loc = lambda names, mat=None: W.loc(pts(names, mat))

    # --- long and short radiolunate ligaments (Berger 2001), in a forearm-aligned frame
    rv = get('Radius')[0]; ax = G.pca_axis(rv)[1]
    WF = Frame(c, ax if ax @ (c('Lunate bone') - rv.mean(0)) > 0 else -ax)
    rad, lun = WF.loc(rv), WF.loc(get('Lunate bone')[0])
    r_l = WF.loc(c('Lunate bone'))[1]
    def best(P, r0, r1, extra=None, rim=None):
        m = (P[:, 1] >= min(r0, r1)) & (P[:, 1] <= max(r0, r1))
        if extra is not None:
            m &= extra
        if rim:
            m &= P[:, 0] > P[m, 0].max() - rim
        return P[m][np.argmax(P[m, 2])]
    h = heightfield(WF.loc(pts(['Radius', 'Lunate bone', 'Scaphoid bone'])))        # capsular: lie on bone
    TEND = ['Flexor digitorum profundus', 'Humero-ulnar head of flexor digitorum superficialis',
            'Radial head of flexor digitorum superficialis', 'Flexor pollicis longus', 'Flexor carpi radialis']
    ceil = heightfield(WF.loc(pts(TEND, 'Tendon')), 1.5 * MM, low=True)
    rmin = np.percentile(rad[rad[:, 0] > rad[:, 0].max() - 25 * MM, 1], 2)   # ulnar edge of distal radius
    o_l = best(rad, rmin + 8 * MM, rmin + 11 * MM, rim=4 * MM); i_l = best(lun, r_l + 4.5 * MM, r_l + 7.5 * MM)
    o_s = best(rad, rmin + 1 * MM, rmin + 4.5 * MM, rim=4 * MM); i_s = best(lun, r_l - 4.5 * MM, r_l - 1 * MM, lun[:, 0] < np.median(lun[:, 0]))
    ref = 'Berger RA, Hand Clin 2001'
    add('Long radiolunate ligament', 'ligament_capsule', 'Ligament',
        ribbon(WF, h, o_l - [2 * MM, 0, 0], i_l + [1 * MM, 0, 0], 4 * MM, 1.3 * MM, 0.2 * MM, ceil=ceil), ref)
    add('Short radiolunate ligament', 'ligament_capsule', 'Ligament',
        ribbon(WF, h, o_s - [2 * MM, 0, 0], i_s + [1 * MM, 0, 0], 5 * MM, 1.3 * MM, 0.2 * MM, ceil=ceil), ref)

    # --- recurrent motor branch of the median nerve (extraligamentous; Lanz 1977)
    fr = loc(['Flexor retinaculum of wrist'])
    a_fr = fr[np.abs(fr[:, 1]) < 8 * MM, 0].max()
    med = loc(['Median nerve'])
    sl = med[np.abs(med[:, 0] - a_fr) < 1.0 * MM]
    P0 = sl[np.argmax(sl[:, 1])] - [0, 0.3 * MM, 0]
    then = ['Abductor pollicis brevis', 'Superficial head of flexor pollicis brevis', 'Opponens pollicis muscle']
    TH = loc(then)
    q = P0 + np.array([0, 13, 5]) * MM
    T = TH[np.argmin(np.linalg.norm(TH - q, axis=1))]
    ctrl = [P0, P0 + np.array([3.5, 3, 1.5]) * MM, P0 + np.array([4.2, 7, 3]) * MM,
            P0 + np.array([2.2, 10.5, 4]) * MM, T]
    hp = heightfield(np.vstack([TH, fr, loc(TEND, 'Tendon')]), 1.5 * MM)
    ctrl = np.array(ctrl)
    for i in range(1, 4):
        hh = hp(ctrl[i:i + 1, 0], ctrl[i:i + 1, 1])[0]
        if not np.isnan(hh):
            ctrl[i, 2] = max(ctrl[i, 2], hh + 0.6 * MM)
    path = W.world(G.catmull(ctrl, 14))
    rmb = [G.tube(path, np.linspace(0.45, 0.38, len(path)) * MM)]
    Tw = W.world(T)
    for n in then:
        d = G.unit(c(n) - Tw)
        tw = W.world(G.catmull([T, T + W.M @ d * 2.5 * MM, T + W.M @ d * 5 * MM], 6))
        rmb.append(G.tube(tw, np.linspace(0.3, 0.2, len(tw)) * MM, 8))
    add('Recurrent motor branch of median nerve', 'nerve', 'Nerve', G.merge(rmb), 'Lanz U, J Hand Surg Am 1977')

    # --- roof of Guyon's canal (volar carpal ligament)
    pis, ham = W.loc(get('Pisiform bone')[0]), W.loc(get('Hamate bone')[0])
    hook = ham[ham[:, 2] > np.percentile(ham[:, 2], 90)].mean(0)
    art = loc(['Ulnar artery', 'Superficial palmar arch'])
    art = art[(art[:, 0] > pis[:, 0].min() - 6 * MM) & (art[:, 0] < hook[0]) & (art[:, 1] < hook[1] + 6 * MM)]
    r0 = pis[:, 1].mean()
    r1 = max(hook[1] + 1.5 * MM, (art[:, 1].max() + 1.2 * MM) if len(art) else -1)
    a0, a1 = pis[:, 0].min() - 5 * MM, hook[0]
    hg = heightfield(np.vstack([
        loc(['Ulnar nerve', 'Superficial branch of ulnar nerve', 'Deep branch of ulnar nerve', 'Ulnar artery',
             'Superficial palmar arch', 'Pisiform bone', 'Hamate bone', 'Pisohamate ligament',
             'Abductor digiti minimi of hand']),
        loc(TEND[:3] + ['Humeral head of flexor carpi ulnaris', 'Ulnar head of flexor carpi ulnaris'], 'Tendon')]), 1.5 * MM)
    uu = np.linspace(-1, 1, 28)[:, None]; vv = np.linspace(-1, 1, 16)[None]
    half = (r1 - r0) / 2 * np.maximum(1 - np.abs(uu) ** 4, 0.25) ** 0.25   # rounded outline
    Ag = a0 + (uu + 1) / 2 * (a1 - a0) + 0 * vv
    Rg = (r0 + r1) / 2 + vv * half
    H = upper(fill_rows(hg(Ag, Rg)), 2) + 0.8 * MM
    v = np.linspace(-1, 1, 16)[None]; u = np.linspace(-1, 1, 28)[:, None]
    th = 0.8 * MM * (1 - 0.6 * v ** 6) * (1 - 0.6 * u ** 8)
    add("Volar carpal ligament (roof of Guyon's canal)", 'fascia_retinacula', 'Ligament',
        sheet(W, Ag, Rg, H, th), "Guyon's canal roof")
    return out, W
