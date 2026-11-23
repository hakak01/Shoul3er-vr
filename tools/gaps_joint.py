"""Phase C joint gaps: IGHL complex (O'Brien 1990), rotator cable (Burkhart 1993), subscapular bursa.
K: context from build_gaps.py (get, pts, C = GH centre, R = head radius). Shapes are fitted to the
existing capsule, labrum, cuff tendons and bones (approx:true). Units: metres; MM for the rules."""
import numpy as np
from scipy.spatial import cKDTree
import gapgeom as G
from gapgeom import MM, unit, D2R

# IGHL complex: clock positions (right shoulder, 3 o'clock = anterior) and thickness
IGHL_PARTS = [('Anterior band of inferior glenohumeral ligament', 2.0, 4.0, 2.8 * MM),
              ('Axillary pouch of inferior glenohumeral ligament', 4.0, 7.0, 1.6 * MM),
              ('Posterior band of inferior glenohumeral ligament', 7.0, 9.0, 2.8 * MM)]
COLLAR = 4 * MM            # humeral attachment: this far below the articular edge
CAP_IN = 0.1 * MM          # bands start just outside the capsule's inner (joint) surface: they thicken the capsule wall
CRESCENT_ML = 14 * MM      # cable centreline: this far (arc) medial to the SSP/ISP footprint's medial edge
CABLE_W = 10 * MM          # cable width
CABLE_X = 2.6              # cable thickness / crescent thickness (Burkhart 1993)
BURSA_T = 3 * MM           # subscapular bursa: max thickness


def glenoid_frame(K):
    gv, gf = K.get('Scapula', 'Cartilage')
    gc = gv.mean(0)
    n = unit(np.cross(gv[gf[:, 1]] - gv[gf[:, 0]], gv[gf[:, 2]] - gv[gf[:, 0]]).sum(0))
    n = n if n @ (K.C - gc) > 0 else -n                     # glenoid -> humeral head
    up = unit(np.array([0, 1., 0]) - n[1] * n)
    ant = np.cross(n, up); ant = ant if ant[2] > 0 else -ant
    return gc, n, up, ant


def cyl(K, F, P):
    """Cylindrical coords about the glenoid axis through the GH centre: s (lateral), rho, clock (0-12)."""
    _, n, up, ant = F
    d = P - K.C; s = d @ n; q = d - s[:, None] * n
    return s, np.linalg.norm(q, axis=1), (np.degrees(np.arctan2(q @ ant, q @ up)) % 360) / 30


def from_cyl(K, F, s, rho, clk):
    _, n, up, ant = F
    a = np.asarray(clk) * 30 * D2R
    return K.C + s[..., None] * n + rho[..., None] * (np.cos(a)[..., None] * up + np.sin(a)[..., None] * ant)


def boundary_verts(v, f):
    e = np.sort(np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), 1)
    u, c = np.unique(e, axis=0, return_counts=True)
    return v[np.unique(u[c == 1])]


def ighl(K, log):
    F = glenoid_frame(K)
    lab = K.get('Glenoid labrum')[0]
    hv = K.get('Humerus', 'Cartilage')[0]; hv = hv[hv[:, 1] > hv[:, 1].max() - 0.06]
    ah = unit((hv - K.C).mean(0))                              # humeral head articular axis
    bone = G.sample_surface(*K.get('Humerus', exclude='Cartilage'), spacing=0.5 * MM)
    bone = bone[bone[:, 1] > hv[:, 1].max() - 0.09]
    cap = K.pts(['Articular capsule of glenohumeral joint'], spacing=0.5 * MM)
    ls, lr, lc = cyl(K, F, lab); cs, cr, cc = cyl(K, F, cap)
    polar = lambda P: np.arccos(np.clip(unit(P - K.C) @ ah, -1, 1))
    perp = lambda P: unit((P - K.C) - ((P - K.C) @ ah)[:, None] * ah)
    hp, hq, bp, bq = polar(hv), perp(hv), polar(bone), perp(bone)
    clocks = np.arange(2.0, 9.0001, 1 / 6)                    # 5 degree steps
    nv = 26
    capt = []
    S = np.zeros((len(clocks), nv)); RIN = np.zeros_like(S); NS = np.zeros_like(S); NR = np.zeros_like(S)
    dc = lambda a, b: np.abs((a - b + 6) % 12 - 6)
    _, _, up, ant = F
    for i, k in enumerate(clocks):
        m = dc(lc, k) < 0.25; j = np.argmax(lr[m]); s0, r0 = ls[m][j], lr[m][j]         # labrum outer rim
        q = np.cos(k * 30 * D2R) * up + np.sin(k * 30 * D2R) * ant
        q = unit(q - (q @ ah) * ah)
        m = hq @ q > np.cos(8 * D2R); e = hv[m][np.argmax(hp[m])]                       # articular margin
        mb = (bq @ q > np.cos(8 * D2R)) & (bp > polar(e[None])[0])
        dist = np.linalg.norm(bone[mb] - e, axis=1)
        h = bone[mb][np.abs(dist - COLLAR) < 1 * MM].mean(0)                               # collar on bone
        s1, r1 = cyl(K, F, h[None])[0][0], cyl(K, F, h[None])[1][0]
        log("    %4.1f oclock rim s %.0f r %.0f -> collar s %.0f r %.0f" % (k, s0 / MM, r0 / MM, s1 / MM, r1 / MM)) if i % 6 == 0 else 0
        mc = dc(cc, k) < 0.2; Q = np.c_[cs[mc], cr[mc]]                                  # capsule section
        g2, h2 = np.array([s0, r0]), np.array([s1, r1])
        win = (Q[:, 0] >= s0) & (Q[:, 0] <= max(s0, s1) + 10 * MM)
        ap = Q[win][np.argmax(Q[win, 1])]                                                  # pouch apex
        t = np.linspace(0, 1, nv)[:, None]; Q1 = 2 * ap - (g2 + h2) / 2
        c2 = (1 - t) ** 2 * g2 + 2 * t * (1 - t) * Q1 + t ** 2 * h2
        tg = np.gradient(c2, axis=0); nr = unit(np.c_[-tg[:, 1], tg[:, 0]])
        nr = nr if nr[nv // 2, 1] > 0 else -nr                                             # outward (away from joint)
        off = np.zeros(nv)
        for j in range(1, nv - 1):
            d = Q - c2[j]; al = d @ nr[j]; ac = np.abs(d @ np.array([nr[j, 1], -nr[j, 0]]))
            sel = (ac < 1.2 * MM) & (np.abs(al) < 6 * MM)
            off[j] = al[sel].min() + CAP_IN if sel.any() else 0
            capt.append(np.ptp(al[sel]) if sel.any() else np.nan)
        w = np.clip(np.minimum(t[:, 0], 1 - t[:, 0]) / 0.15, 0, 1)
        c2 = c2 + (w * np.maximum(off, 0))[:, None] * nr
        S[i], RIN[i], NS[i], NR[i] = c2[:, 0], c2[:, 1], nr[:, 0], nr[:, 1]
    S, RIN = [G.smooth1d(G.smooth1d(x, 1.0, 0), 1.0, 1) for x in (S, RIN)]
    near = [G.Solid([K.get(m)]) for m in ('Subscapularis muscle', 'Teres minor muscle', 'Infraspinatus muscle',
                                           'Short head of biceps brachii')]

    def inward(A, B):
        """where a cuff muscle hugs the capsule, move the band into the capsule instead of into the muscle"""
        nrm = unit(B - A); pen = np.zeros(A.shape[:2])
        for Sm in near:
            d = Sm.signed(B.reshape(-1, 3))[0].reshape(pen.shape)
            pen = np.maximum(pen, np.clip(0.2 * MM - d, 0, 3 * MM))
        pen = G.smooth1d(G.smooth1d(pen, 1.0, 0), 1.0, 1)
        return A - nrm * pen[..., None], B - nrm * pen[..., None]
    out = []
    for name, a, b, th in IGHL_PARTS:
        sel = (clocks >= a - 1e-6) & (clocks <= b + 1e-6)
        k = clocks[sel][:, None] * np.ones(nv)
        A = from_cyl(K, F, S[sel], RIN[sel], k); B = from_cyl(K, F, S[sel] + th * NS[sel], RIN[sel] + th * NR[sel], k)
        V, Fc = G.slab(*K.clear(*inward(A, B)))
        out.append(dict(name=name, layer='ligament_capsule', mat='Ligament', mesh=(V, Fc),
                        ref="O'Brien 1990: %g-%g o'clock, %.1f mm thick" % (a, b, th / MM),
                        replaces='Inferior glenohumeral ligament'))
    log('  IGHL: capsule wall here %.1f mm thick (median); bands start %.1f mm outside its inner surface' % (
        np.nanmedian(capt) / MM, CAP_IN / MM))
    log("  IGHL: glenoid rim -> humeral collar %.0f mm below articular edge; length (mm) at 3/6/9 o'clock %s" % (
        COLLAR / MM, [round(float(np.linalg.norm(np.diff(from_cyl(K, F, S[i], RIN[i], clocks[i] + 0 * S[i]), axis=0), axis=1).sum()) / MM)
                      for i in (6, 24, 42)]))
    return out, F


def rotator_cable(K, log):
    hv = K.get('Humerus', 'Cartilage')[0]; hv = hv[hv[:, 1] > hv[:, 1].max() - 0.06]
    pole = unit((hv - K.C).mean(0))                                    # humeral head axis
    sph = lambda d: (np.arccos(np.clip(d @ pole, -1, 1)), np.arctan2(d @ e2, d @ e1))
    fp = K.pts(['Supraspinatus muscle (insertion)', 'Infraspinatus muscle (insertion)'])
    e1 = unit((fp - K.C).mean(0)); e1 = unit(e1 - (e1 @ pole) * pole); e2 = np.cross(pole, e1)
    th, ps = sph(unit(fp - K.C))
    mus = []
    for nm in ('Supraspinatus muscle', 'Infraspinatus muscle'):
        p = K.pts([nm], spacing=0.4 * MM)
        mus.append((cKDTree(unit(p - K.C)), np.linalg.norm(p - K.C, axis=1)))
    ct = cKDTree(unit(hv - K.C)); cr = np.linalg.norm(hv - K.C, axis=1)

    def radii(d, ang=2.0 * D2R):
        """per direction: tendon thickness (thicker of SSP/ISP), tendon outer radius, cartilage radius"""
        t = np.full(len(d), np.nan); ro = np.full(len(d), np.nan)
        for tree, r in mus:
            for k, i in enumerate(tree.query_ball_point(d, ang)):
                if len(i) > 8:
                    t[k] = np.nanmax([t[k], r[i].max() - r[i].min()]); ro[k] = np.nanmax([ro[k], r[i].max()])
        return t, ro, np.array([cr[i].max() if len(i) else np.nan for i in ct.query_ball_point(d, ang)])
    # footprint medial edge per azimuth
    pb = np.linspace(ps.min(), ps.max(), 40)
    o = np.argsort(ps); edge = np.array([th[o][max(0, j - 30):j + 30].min() for j in np.searchsorted(ps[o], pb)])
    edge = G.smooth1d(edge, 2.0)
    Rt = K.R + 4 * MM
    thc = edge - CRESCENT_ML / Rt
    dirs = lambda t, p: unit(np.cos(t)[..., None] * pole + np.sin(t)[..., None] * (
        np.cos(p)[..., None] * e1 + np.sin(p)[..., None] * e2))
    # crescent thickness: tendon between the cable line and the footprint edge
    tcres = np.nanmedian(np.concatenate([radii(dirs(thc + f * (edge - thc), pb))[0] for f in (0.3, 0.5, 0.7)]))
    T = CABLE_X * tcres
    nu, nv = 40, 9
    x = np.linspace(-1, 1, nv)
    taper = np.clip(np.minimum(np.arange(nu), nu - 1 - np.arange(nu)) / 6, 0.4, 1)[:, None]
    TT, PP = thc[:, None] + x[None] * (CABLE_W / 2 / Rt) * taper, pb[:, None] * np.ones(nv)
    D = dirs(TT, PP)
    _, ro, cart = [a.reshape(nu, nv) for a in radii(D.reshape(-1, 3))]
    ro = np.where(np.isnan(ro), np.nanmedian(ro), ro)
    cart = np.where(np.isnan(cart), np.nanmedian(cart), cart)
    inner = G.smooth1d(G.smooth1d(np.maximum(ro - T * taper, cart + 0.3 * MM), 1.5, 0), 1.0, 1)
    outer = G.smooth1d(G.smooth1d(np.maximum(np.minimum(inner + T * taper, ro - 0.2 * MM), inner + 0.6 * MM), 1.5, 0), 1.0, 1)
    tk = outer - inner                                         # limited by the model's tendon (it lies on the cartilage)
    h = tk * np.sqrt(np.clip(1 - x ** 2, 0.08, 1))[None]
    mid_r = (inner + outer) / 2
    A = K.C + D * (mid_r - h / 2)[..., None]; B = K.C + D * (mid_r + h / 2)[..., None]
    V, F = G.slab(*K.clear(A, B))
    span = np.linalg.norm(np.diff(A[:, nv // 2], axis=0), axis=1).sum()
    log('  rotator cable: model crescent %.1f mm -> target %.1f mm, built %.1f mm (median, centre line; fits '
        'cartilage +0.3 .. tendon surface -0.2 mm), width %.0f, length %.0f mm, %.0f mm medial to footprint edge' % (
            tcres / MM, T / MM, np.median(tk[:, nv // 2]) / MM, CABLE_W / MM, span / MM, CRESCENT_ML / MM))
    return [dict(name='Rotator cable', layer='muscle', mat='Tendon', mesh=(V, F),
                 ref='Burkhart 1993: about %.1fx the crescent; spans SSP and ISP insertions' % CABLE_X)]


def subscap_bursa(K, F, log):
    gc, n, up, ant = F
    lab = K.get('Glenoid labrum')[0]
    s_l, r_l, c_l = cyl(K, F, lab)
    m = np.abs(c_l - 2.0) < 0.3                      # between SGHL (~1) and MGHL (~2.5 o'clock)
    rim = lab[m][np.argmax(r_l[m])]
    sc = K.pts(['Scapula'], spacing=0.5 * MM); ss = K.pts(['Subscapularis muscle'], spacing=0.5 * MM)
    # local plane: e1 medial along the neck, e2 superior; depth along ant
    e1 = unit(-n - (-n @ ant) * ant); e2 = np.cross(ant, e1); e2 = e2 if e2[1] > 0 else -e2
    nu, nv = 18, 22
    U, W = np.meshgrid(np.linspace(-1 * MM, 17 * MM, nu), np.linspace(-9 * MM, 14 * MM, nv), indexing='ij')
    P0 = rim + U[..., None] * e1 + W[..., None] * e2
    def plane_tree(Q):
        q = Q - rim
        return cKDTree(np.c_[q @ e1, q @ e2]), q @ ant
    tb, ab = plane_tree(sc); tm, am = plane_tree(ss)
    flat = np.c_[U.ravel(), W.ravel()]
    lo = np.full(len(flat), np.nan); hi = np.full(len(flat), np.nan)
    for k, (ib, im) in enumerate(zip(tb.query_ball_point(flat, 1.5 * MM), tm.query_ball_point(flat, 1.5 * MM))):
        if ib:
            lo[k] = ab[ib].max()
            front = am[im][am[im] > lo[k]] if im else []
            hi[k] = front.min() if len(front) else lo[k] + BURSA_T + 1 * MM
    ok = ~np.isnan(lo)
    fill = lambda a: np.where(np.isnan(a), np.interp(np.arange(len(a)), np.flatnonzero(~np.isnan(a)), a[~np.isnan(a)]), a)
    lo, hi = fill(lo).reshape(nu, nv), fill(hi).reshape(nu, nv)
    gap = hi - lo
    # elliptical outline: thickness falls to 0.4 mm at the rim of the sac
    rr = np.sqrt(((U - 8 * MM) / (9 * MM)) ** 2 + ((W - 2.5 * MM) / (11.5 * MM)) ** 2)
    t = np.clip(np.minimum(BURSA_T * np.sqrt(np.clip(1 - rr ** 2, 0, 1)), gap - 0.6 * MM), 0.4 * MM, None)
    t = G.smooth1d(G.smooth1d(t, 1.0, 0), 1.0, 1)
    base = G.smooth1d(G.smooth1d(lo, 1.0, 0), 1.0, 1) + 0.3 * MM
    A = P0 + base[..., None] * ant; B = P0 + (base + t)[..., None] * ant
    V, Fc = G.slab(*K.clear(A, B))
    log('  subscapular bursa: %d%% of grid over bone, bone->muscle gap median %.1f mm, bursa max %.1f mm, '
        'size %.0f x %.0f mm' % (ok.mean() * 100, np.median(gap) / MM, t.max() / MM, 18, 23))
    return [dict(name='Subscapular bursa (subscapularis recess)', layer='bursa', mat='Bursa', mesh=(V, Fc),
                 ref='between subscapularis tendon and scapular neck, opening between SGHL and MGHL')]


def build(K, log):
    hard = [G.Solid([K.get(n, exclude='Cartilage')]) for n in ('Humerus', 'Scapula')] + \
           [G.Solid([K.get(n, 'Cartilage')]) for n in ('Humerus', 'Scapula')]

    def clear(A, B, gap=0.2 * MM):
        """push both surfaces of a slab out of bone and cartilage"""
        sh = A.shape; A, B = A.reshape(-1, 3).copy(), B.reshape(-1, 3).copy()
        for S in hard:
            for X in (A, B):
                d, n = S.signed(X); m = d < gap
                X[m] += n[m] * (gap - d[m])[:, None]
        return A.reshape(sh), B.reshape(sh)
    K.clear = clear
    items, F = ighl(K, log)
    items += rotator_cable(K, log)
    items += subscap_bursa(K, F, log)
    return items
