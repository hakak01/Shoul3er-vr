"""Geometry helpers for build_gaps.py: surface sampling, oriented point clouds, closed slabs,
tubes, pushing paths out of solids. Units: metres in, mm used for the shape rules (MM)."""
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


class Solid:
    """Oriented surface samples of closed meshes: signed distance (negative inside, reliable near the surface)."""
    def __init__(self, parts, spacing=0.8 * MM):
        P, N = [], []
        for v, f in parts:
            a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
            fn = unit(np.cross(b - a, c - a))
            for w in ((1 / 3, 1 / 3), (0.6, 0.2), (0.2, 0.6), (0.2, 0.2)):
                P.append(a + w[0] * (b - a) + w[1] * (c - a)); N.append(fn)
        self.tree, self.n = cKDTree(np.vstack(P)), np.vstack(N)

    def signed(self, x):
        d, i = self.tree.query(x, k=4)
        s = np.einsum('ikj,ikj->ik', x[:, None] - self.tree.data[i], self.n[i]).mean(1)
        return np.where((s < 0) & (d[:, 0] < 6 * MM), -d[:, 0], d[:, 0]), self.n[i[:, 0]]

    def push_out(self, path, clear, iters=12, keep_ends=True):
        """Move path points to at least `clear` outside the surface (ends fixed if keep_ends)."""
        path = path.copy()
        for _ in range(iters):
            d, n = self.signed(path)
            m = d < clear
            if keep_ends:
                m[[0, -1]] = False
            if not m.any():
                break
            path[m] += n[m] * (clear - d[m])[:, None]
            path = np.vstack([path[:1], smooth1d(path, 1.5)[1:-1], path[-1:]])
        d, n = self.signed(path)                              # last pass without smoothing
        m = d < clear
        if keep_ends:
            m[[0, -1]] = False
        path[m] += n[m] * (clear - d[m])[:, None]
        return path


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
