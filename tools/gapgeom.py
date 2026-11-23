"""Geometry helpers for build_gaps.py: surface sampling, finger frames, polar envelopes,
strips (closed thin slabs) and tubes. Units: metres in, mm used for the shape rules (MM)."""
import numpy as np
from scipy.spatial import cKDTree

MM = 0.001
D2R = np.pi / 180


def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def sample_surface(v, f, spacing=0.6 * MM, seed=1):
    """Vertices + area-weighted random points on triangles (about 1 per spacing^2)."""
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    n = np.random.default_rng(seed).poisson(area / spacing ** 2)
    idx = np.repeat(np.arange(len(f)), n)
    r = np.random.default_rng(seed + 1).random((len(idx), 2))
    m = r.sum(1) > 1
    r[m] = 1 - r[m]
    pts = a[idx] + r[:, :1] * (b[idx] - a[idx]) + r[:, 1:] * (c[idx] - a[idx])
    return np.vstack([v, pts])


def smooth1d(x, sigma, axis=0, wrap=False):
    if sigma <= 0:
        return x
    k = int(np.ceil(3 * sigma)); w = np.exp(-0.5 * (np.arange(-k, k + 1) / sigma) ** 2); w /= w.sum()
    x = np.moveaxis(x, axis, 0)
    pad = np.concatenate([x[-k:], x, x[:k]]) if wrap else \
        np.concatenate([np.repeat(x[:1], k, 0), x, np.repeat(x[-1:], k, 0)])
    out = sum(w[i] * pad[i:i + len(x)] for i in range(2 * k + 1))
    return np.moveaxis(out, 0, axis)


def pca_axis(p):
    c = p.mean(0)
    w, V = np.linalg.eigh(np.cov((p - c).T))
    return c, V[:, -1]


class Ray:
    """A finger or thumb: centreline through joint centres, arc length s (m, 0 at MCP joint),
    frame t (distal), p (palmar), r (radial). bones: list of vertex arrays, proximal->distal."""
    def __init__(self, bones, flex_pts, radial_hint, step=0.4 * MM):
        cs, axes, ends = [], [], []
        for i, b in enumerate(bones):
            c, a = pca_axis(b)
            ref = (bones[i + 1].mean(0) - c) if i + 1 < len(bones) else (c - bones[i - 1].mean(0))
            a = a if a @ ref > 0 else -a
            pr = (b - c) @ a
            cs.append(c); axes.append(a); ends.append((c + a * pr.min(), c + a * pr.max()))
        joints = [(ends[i][1] + ends[i + 1][0]) / 2 for i in range(len(bones) - 1)]
        nodes = [cs[0] - axes[0] * 0.0] + joints + [ends[-1][1]]
        seg = np.linalg.norm(np.diff(nodes, axis=0), axis=1)
        cum = np.concatenate([[0], np.cumsum(seg)])
        s = np.arange(cum[0] - 6 * MM, cum[-1] + 2 * MM, step)
        P = np.array([np.interp(s, cum, [n[k] for n in nodes]) for k in range(3)]).T
        # extrapolate linearly beyond the ends
        for sel, i0, i1 in ((s < cum[0], 0, 1), (s > cum[-1], -2, -1)):
            d = unit(nodes[i1] - nodes[i0]); base = cum[0] if i0 == 0 else cum[-1]
            P[sel] = nodes[0 if i0 == 0 else -1] + np.outer(s[sel] - base, d)
        self.c = smooth1d(P, 2.5 * MM / step)
        self.t = unit(smooth1d(np.gradient(self.c, axis=0), 3 * MM / step))
        self.s = s - cum[1]                     # 0 at MCP joint
        self.joint_s = cum[1:-1] - cum[1]       # MCP, PIP(, DIP)
        self.tip_s = cum[-1] - cum[1]
        self.step = step
        # palmar direction: from axis towards the flexor tendons near each sample
        p = np.zeros_like(self.c)
        tree = cKDTree(flex_pts)
        for i in range(len(s)):
            idx = tree.query_ball_point(self.c[i], 11 * MM)
            if len(idx) > 5:
                d = flex_pts[idx] - self.c[i]
                d -= np.outer(d @ self.t[i], self.t[i])
                p[i] = unit(d.mean(0))
        ok = np.linalg.norm(p, axis=1) > 0.5
        for k in range(3):
            p[:, k] = np.interp(np.arange(len(s)), np.nonzero(ok)[0], p[ok, k])
        p = smooth1d(p, 4 * MM / step)
        p = unit(p - (p * self.t).sum(1, keepdims=True) * self.t)
        r = np.cross(self.t, p)
        if (r.mean(0) @ radial_hint) < 0:
            r = -r
        self.p, self.r = p, r

    def idx(self, s):
        return np.clip((np.asarray(s) - self.s[0]) / self.step, 0, len(self.s) - 1.001)

    def frame(self, s):
        i = self.idx(s); i0 = np.floor(i).astype(int); w = (i - i0)[..., None]
        lerp = lambda A: A[i0] * (1 - w) + A[i0 + 1] * w
        return lerp(self.c), unit(lerp(self.t)), unit(lerp(self.p)), unit(lerp(self.r))

    def assign(self, pts):
        """distance from each point to this centreline (for splitting shared meshes)."""
        return cKDTree(self.c).query(pts)[0]

    def envelope(self, pts, nb=48, half=0.8 * MM, rmax=14 * MM, hull=1.5 * MM):
        """R[i, bin]: outermost radius of pts around the centreline, per sample and angle bin."""
        R = np.full((len(self.s), nb), np.nan)
        tree = cKDTree(pts)
        for i in range(len(self.s)):
            idx = tree.query_ball_point(self.c[i], rmax)
            if not idx:
                continue
            d = pts[idx] - self.c[i]
            ax = d @ self.t[i]
            m = np.abs(ax) < half
            if m.sum() < 3:
                continue
            x, y = d[m] @ self.r[i], d[m] @ self.p[i]
            b = (np.round(np.arctan2(y, x) / (2 * np.pi) * nb) % nb).astype(int)
            rho = np.hypot(x, y)
            for bb in range(nb):
                sel = rho[b == bb]
                if len(sel):
                    R[i, bb] = sel.max()
        for i in range(len(R)):                          # fill empty angle bins
            ok = ~np.isnan(R[i])
            if ok.sum() >= 3:
                xs = np.nonzero(ok)[0]
                R[i] = np.interp(np.arange(nb), xs, R[i, ok], period=nb)
        for bb in range(nb):                             # fill empty samples
            ok = ~np.isnan(R[:, bb])
            R[:, bb] = np.interp(np.arange(len(R)), np.nonzero(ok)[0], R[ok, bb]) if ok.any() else 3 * MM
        k = max(1, int(hull / self.step))                # bridge joint gaps / grooves
        R = np.max([np.roll(np.pad(R, ((k, k), (0, 0)), mode='edge'), j, 0)[k:-k] for j in range(-k, k + 1)], 0)
        R = np.max([np.roll(R, j, 1) for j in (-1, 0, 1)], 0)
        R = smooth1d(smooth1d(R, 1.0 * MM / self.step, 0), 1.0, 1, wrap=True)
        return R

    def radius(self, R, s, phi):
        nb = R.shape[1]
        i = self.idx(s); i0 = np.floor(i).astype(int); wi = i - i0
        b = (np.asarray(phi) / (2 * np.pi) * nb) % nb; b0 = np.floor(b).astype(int); wb = b - b0; b1 = (b0 + 1) % nb
        return ((R[i0, b0] * (1 - wb) + R[i0, b1] * wb) * (1 - wi) +
                (R[i0 + 1, b0] * (1 - wb) + R[i0 + 1, b1] * wb) * wi)

    def point(self, s, phi, rad):
        c, t, p, r = self.frame(s)
        return c + rad[..., None] * (np.cos(phi)[..., None] * r + np.sin(phi)[..., None] * p)

    def strip(self, R, s_of_u, phi_of_u, width, offset=0.3 * MM, thick=0.6 * MM, nu=40, nv=7):
        """Thin closed band lying on envelope R. Path (s(u), phi(u)) for u in [0,1];
        width (m, may be a function of u) across the path; thick may be a function of (u, v)."""
        u = np.linspace(0, 1, nu); v = np.linspace(-0.5, 0.5, nv)
        S, PH = np.asarray(s_of_u(u), float) * np.ones(nu), np.asarray(phi_of_u(u), float) * np.ones(nu)
        R0 = self.radius(R, S, PH)
        dS, dA = np.gradient(S), np.gradient(PH) * R0
        n = np.hypot(dS, dA) + 1e-12
        ns, na = -dA / n, dS / n
        W = np.asarray(width(u) if callable(width) else width * np.ones(nu))
        SS = S[:, None] + v[None] * (W * ns)[:, None]
        PP = PH[:, None] + v[None] * (W * na / R0)[:, None]
        TH = thick(u[:, None], v[None]) if callable(thick) else thick * np.ones((nu, nv))
        rin = self.radius(R, SS, PP) + offset
        rin = smooth1d(smooth1d(rin, 1.0, 0), 0.7, 1)
        return slab(self.point(SS, PP, rin), self.point(SS, PP, rin + TH))


def slab(A, B):
    """Closed mesh between two (nu, nv, 3) grids A (inner) and B (outer)."""
    nu, nv = A.shape[:2]
    V = np.vstack([A.reshape(-1, 3), B.reshape(-1, 3)])
    g = lambda layer, i, j: layer * nu * nv + i * nv + j
    F = []
    for i in range(nu - 1):
        for j in range(nv - 1):
            for L, flip in ((0, True), (1, False)):
                q = [g(L, i, j), g(L, i + 1, j), g(L, i + 1, j + 1), g(L, i, j + 1)]
                F += [[q[0], q[1], q[2]], [q[0], q[2], q[3]]] if not flip else [[q[0], q[2], q[1]], [q[0], q[3], q[2]]]
    ring = [(i, 0) for i in range(nu)] + [(nu - 1, j) for j in range(1, nv)] + \
           [(i, nv - 1) for i in range(nu - 2, -1, -1)] + [(0, j) for j in range(nv - 2, 0, -1)]
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        F += [[g(0, *a), g(0, *b), g(1, *b)], [g(0, *a), g(1, *b), g(1, *a)]]
    F = np.array(F)
    return orient(V, F)


def orient(V, F):
    """Make a closed mesh's normals point outwards (signed volume > 0)."""
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    vol = np.einsum('ij,ij->i', a, np.cross(b, c)).sum()
    return V, (F if vol > 0 else F[:, ::-1])


def catmull(P, n=60):
    P = np.asarray(P, float)
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(1, len(P) - 2):
        for t in np.linspace(0, 1, n, endpoint=False):
            p0, p1, p2, p3 = P[i - 1:i + 3]
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return np.array(out)


def tube(path, rad, nseg=10):
    """Capped tube along a polyline (rad may be an array per point)."""
    path = np.asarray(path); n = len(path)
    rad = np.broadcast_to(np.asarray(rad, float), (n,))
    T = unit(np.gradient(path, axis=0))
    ref = np.array([0, 0, 1.0]) if abs(T[0, 2]) < 0.9 else np.array([1.0, 0, 0])
    N = unit(np.cross(T[0], ref)); rings = []
    for i in range(n):
        N = unit(N - (N @ T[i]) * T[i]); B = np.cross(T[i], N)
        a = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
        rings.append(path[i] + rad[i] * (np.outer(np.cos(a), N) + np.outer(np.sin(a), B)))
    V = np.vstack(rings + [path[:1], path[-1:]])
    F = []
    for i in range(n - 1):
        for j in range(nseg):
            a, b = i * nseg + j, i * nseg + (j + 1) % nseg
            F += [[a, b, b + nseg], [a, b + nseg, a + nseg]]
    c0, c1 = n * nseg, n * nseg + 1
    for j in range(nseg):
        F += [[c0, (j + 1) % nseg, j], [c1, (n - 1) * nseg + j, (n - 1) * nseg + (j + 1) % nseg]]
    return orient(V, np.array(F))


def merge(parts):
    V, F, o = [], [], 0
    for v, f in parts:
        V.append(v); F.append(f + o); o += len(v)
    return np.vstack(V), np.vstack(F)
