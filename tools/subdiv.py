"""One level of Loop subdivision (x4 triangles). Then original vertices may move at most
MAX_DEV from where they were, and new edge vertices at most MAX_DEV from their edge
midpoint, so the shape changes by <= 0.3 mm (checked both ways)."""
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

MAX_DEV = 0.0003


def loop(V, F):
    E = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), 1)
    ue, inv = np.unique(E, axis=0, return_inverse=True)
    inv = inv.ravel(); nf = len(F)
    opp = np.concatenate([F[:, 2], F[:, 0], F[:, 1]])          # vertex opposite each edge
    cnt = np.bincount(inv, minlength=len(ue))
    osum = np.zeros((len(ue), 3)); np.add.at(osum, inv, V[opp])
    a, b = V[ue[:, 0]], V[ue[:, 1]]
    inner = (cnt == 2)[:, None]
    odd = np.where(inner, 3 / 8 * (a + b) + 1 / 8 * osum, (a + b) / 2)
    # even vertices
    n = len(V); nb = np.zeros((n, 3)); deg = np.zeros(n)
    np.add.at(nb, ue[:, 0], b); np.add.at(nb, ue[:, 1], a)
    np.add.at(deg, ue[:, 0], 1); np.add.at(deg, ue[:, 1], 1)
    bnd = ~inner[:, 0]; bsum = np.zeros((n, 3)); bdeg = np.zeros(n)
    np.add.at(bsum, ue[bnd, 0], b[bnd]); np.add.at(bsum, ue[bnd, 1], a[bnd])
    np.add.at(bdeg, ue[bnd, 0], 1); np.add.at(bdeg, ue[bnd, 1], 1)
    d = np.maximum(deg, 1)
    beta = np.where(d > 3, 3 / (8 * d), 3 / 16)
    even = (1 - d * beta)[:, None] * V + beta[:, None] * nb
    isb = bdeg == 2
    even[isb] = 0.75 * V[isb] + 0.125 * bsum[isb]
    even[(bdeg > 0) & ~isb] = V[(bdeg > 0) & ~isb]               # corners / non-manifold: fixed
    NV = np.vstack([even, odd])
    m = (inv + n).reshape(3, nf).T                               # edge ids: (01, 12, 20)
    ab, bc, ca = m[:, 0], m[:, 1], m[:, 2]
    NF = np.concatenate([np.c_[F[:, 0], ab, ca], np.c_[F[:, 1], bc, ab],
                         np.c_[F[:, 2], ca, bc], np.c_[ab, bc, ca]])
    return NV, NF


def smooth(V, F, mat):
    """Returns new verts, faces, per-face material, max deviation (mm) both ways."""
    tree = BVHTree.FromPolygons([Vector(p) for p in V], F.tolist())
    NV, NF = loop(V, F)
    # linear (flat) subdivision = the original shape; limit each vertex's move to MAX_DEV
    E = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), 1)
    ue = np.unique(E, axis=0)
    base = np.vstack([V, (V[ue[:, 0]] + V[ue[:, 1]]) / 2])
    d = NV - base; L = np.linalg.norm(d, axis=1, keepdims=True)
    NV = base + d * np.minimum(1, MAX_DEV / np.maximum(L, 1e-12))
    smooth.moved = np.linalg.norm(NV - base, axis=1).max() * 1000
    t2 = BVHTree.FromPolygons([Vector(p) for p in NV], NF.tolist())
    samp = np.vstack([V[np.unique(F)], V[F].mean(1), (V[F[:, 0]] + V[F[:, 1]]) / 2,
                      (V[F[:, 1]] + V[F[:, 2]]) / 2, (V[F[:, 2]] + V[F[:, 0]]) / 2])
    back = max(t2.find_nearest(Vector(p))[3] for p in samp)
    fwd = max(tree.find_nearest(Vector(p))[3] for p in NV)
    return NV, NF, np.tile(mat, 4), max(back, fwd) * 1000
