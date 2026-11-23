"""Swap Z-Anatomy bones for BodyParts3D bones: global similarity fit + rigid ICP."""
import re
import numpy as np
from scipy.spatial import cKDTree

ORD = {'first': 'thumb', 'second': 'index finger', 'third': 'middle finger',
       'fourth': 'ring finger', 'fifth': 'little finger'}
CARPAL = {'Triquetrum bone': 'right triquetral'}


def bp_name(zname):
    """Z-Anatomy bone name (without '.r') -> BodyParts3D English name."""
    if zname in CARPAL:
        return CARPAL[zname]
    m = re.match(r'(Proximal|Middle|Distal) phalanx of (\w+) finger of hand', zname)
    if m:
        f = ORD[m.group(2)]
        return '%s phalanx of right %s' % (m.group(1).lower(), f)
    m = re.match(r'(\w+) metacarpal bone', zname)
    if m:
        return 'right %s metacarpal bone' % m.group(1).lower()
    return 'right ' + zname.replace(' bone', '').lower()


def load_stl(path):
    d = np.fromfile(path, dtype=np.uint8)
    n = int(np.frombuffer(d[80:84].tobytes(), np.uint32)[0])
    rec = np.frombuffer(d[84:84 + 50 * n].tobytes(),
                        dtype=np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]))
    v = rec['v'].reshape(-1, 3).astype(np.float64)
    uq, inv = np.unique(np.round(v, 5), axis=0, return_inverse=True)
    f = inv.reshape(-1, 3)
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    return uq, f


def volume(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return abs(np.einsum('ij,ij->i', a, np.cross(b, c)).sum()) / 6.0


def surface_samples(v, f, n=20000, seed=0):
    """Area-weighted random points on the surface + the face id of each point."""
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
    rng = np.random.default_rng(seed)
    fid = rng.choice(len(f), n, p=area / area.sum())
    r1, r2 = rng.random(n), rng.random(n)
    s = np.sqrt(r1)
    p = (1 - s)[:, None] * a[fid] + (s * (1 - r2))[:, None] * b[fid] + (s * r2)[:, None] * c[fid]
    p = np.vstack([p, v])
    fid = np.concatenate([fid, -np.ones(len(v), int)])
    return p, fid


def umeyama(src, dst, scale=True):
    """Find s, R, t minimising |s R src + t - dst|."""
    ms, md = src.mean(0), dst.mean(0)
    xs, xd = src - ms, dst - md
    u, d, vt = np.linalg.svd(xd.T @ xs / len(src))
    e = np.eye(3)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        e[2, 2] = -1
    r = u @ e @ vt
    s = (d * np.diag(e)).sum() / (xs ** 2).sum() * len(src) if scale else 1.0
    return s, r, md - s * r @ ms


def icp(src, tgt_tree, tgt_pts, iters=40):
    """Rigid ICP of src points onto target; returns (R, t) to apply after."""
    R, t = np.eye(3), np.zeros(3)
    cur = src.copy()
    for _ in range(iters):
        _, idx = tgt_tree.query(cur)
        _, r, tt = umeyama(cur, tgt_pts[idx], scale=False)
        cur = cur @ r.T + tt
        R, t = r @ R, r @ t + tt
    return R, t


def swap_bone(zv, zf, zmat, bv, bf):
    """zv,zf: Z bone (m, world). bv,bf: BP3D bone already globally fitted (m).
    Returns new verts, faces, per-face material index, mean/max error (mm)."""
    zp, zfid = surface_samples(zv, zf)
    tree = cKDTree(zp)
    R, t = icp(bv, tree, zp)
    nv = bv @ R.T + t
    d1, _ = tree.query(nv)                                  # BP3D -> Z
    bp_s, _ = surface_samples(nv, bf, 20000, 1)
    d2, _ = cKDTree(bp_s).query(zv)                         # Z -> BP3D
    mean = (d1.mean() + d2.mean()) / 2 * 1000
    mx = max(d1.max(), d2.max()) * 1000
    # cartilage / bone material by nearest Z surface sample (sampled points carry face ids)
    keep = zfid >= 0
    ftree = cKDTree(zp[keep])
    cen = nv[bf].mean(1)
    _, j = ftree.query(cen)
    mat = np.asarray(zmat)[zfid[keep][j]]
    return nv, bf, mat, mean, mx
