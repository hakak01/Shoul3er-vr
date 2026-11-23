"""Phase A anatomy checks at rest (arm at side). Measures only; prints mm.
Run: python3 -I tools/measure.py   (reads the uncompressed data/raw/shoulder_raw.glb)
Frame below = Z-Anatomy world: X (- = right/lateral), Y (+ = posterior), Z (+ = up)."""
import os, sys
import numpy as np
from scipy.spatial import cKDTree
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import glbio

G = glbio.read(os.path.join(ROOT, 'data/raw/shoulder_raw.glb'))


def za(v):                      # glTF y-up -> Z-Anatomy z-up
    return np.c_[v[:, 0], -v[:, 2], v[:, 1]]


def get(name, mat=None):
    P = [(za(v), f) for v, f, m in G[name] if mat is None or mat in m]
    V = np.vstack([p[0] for p in P]); off = np.cumsum([0] + [len(p[0]) for p in P])
    return V, np.vstack([p[1] + o for p, o in zip(P, off)])


def verts(*names):
    return np.vstack([get(n)[0] for n in names if n in G])


def inside(P, V, F):            # generalised winding number > 0.5
    A, B, C = (V[F[:, i]][None] - P[:, None] for i in range(3))
    a, b, c = (np.linalg.norm(x, axis=2) for x in (A, B, C))
    det = np.einsum('ijk,ijk->ij', A, np.cross(B, C))
    den = a * b * c + np.einsum('ijk,ijk->ij', A, B) * c + np.einsum('ijk,ijk->ij', B, C) * a \
        + np.einsum('ijk,ijk->ij', C, A) * b
    return np.abs(np.arctan2(det, den).sum(1)) / (2 * np.pi) > 0.5


mm = lambda x: x * 1000
S = verts('Scapula'); H = verts('Humerus')
gl = get('Scapula', 'Cartilage')[0]; g = gl.mean(0)
up = S[S[:, 2] > g[2] + 0.01]; acro = up[up[:, 0].argmin()]
cor = S[S[:, 1].argmin()]
hc = get('Humerus', 'Cartilage')[0]; head = hc[hc[:, 2] > H[:, 2].mean()].mean(0)
dist = H[H[:, 2] < H[:, 2].min() + 0.06]
lat_ep, med_ep = dist[dist[:, 0].argmin()], dist[dist[:, 0].argmax()]
ax = head - (lat_ep + med_ep) / 2; ax /= np.linalg.norm(ax)
print('humerus length (head centre to epicondyle midpoint) %.0f mm' % mm(np.linalg.norm(head - (lat_ep + med_ep) / 2)))

# 1 axillary nerve vs lateral acromion edge
N = verts('Axillary nerve', 'Muscular branches of axillary nerve')
lat = N[N[:, 0] < head[0]]
print('1 axillary: min 3D %.0f mm; vertical drop to highest nerve point lateral to head centre %.0f mm' % (
    mm(np.linalg.norm(N - acro, axis=1).min()), mm(acro[2] - lat[:, 2].max()) if len(lat) else -1))

# 2 musculocutaneous entry into coracobrachialis
M = verts('Musculocutaneous nerve'); M = M[np.argsort(-M[:, 2])]
cbV, cbF = get('Coracobrachialis muscle')
ins = inside(M, cbV, cbF)
if ins.any():
    e = M[ins.argmax()]
    print('2 MCN enters coracobrachialis %.0f mm below coracoid tip (3D %.0f mm)' % (
        mm(cor[2] - e[2]), mm(np.linalg.norm(e - cor))))
else:
    d, _ = cKDTree(cbV).query(M)
    print('2 MCN never inside coracobrachialis; closest %.1f mm at %.0f mm below coracoid tip' % (
        mm(d.min()), mm(cor[2] - M[d.argmin()][2])))

# 3 radial nerve on posterior humerus
R = verts('Radial nerve'); d, _ = cKDTree(H).query(R)
post = []
for p, di in zip(R, d):
    sl = H[np.abs(H[:, 2] - p[2]) < 0.004]
    if di < 0.008 and len(sl) and p[1] > sl[:, 1].mean():
        post.append(p)
post = np.array(post)
if len(post):
    top, bot = post[post[:, 2].argmax()], post[post[:, 2].argmin()]
    print('3 radial nerve on posterior humerus (within 8 mm): from %.0f mm above medial epicondyle '
          'to %.0f mm above lateral epicondyle' % (mm((top - med_ep) @ ax), mm((bot - lat_ep) @ ax)))

# 4 suprascapular nerve vs posterior glenoid rim (mid-height)
mid = gl[np.abs(gl[:, 2] - g[2]) < 0.004]; prim = mid[mid[:, 1].argmax()]
Q = verts('Suprascapular nerve')
print('4 suprascapular nerve to posterior glenoid rim: min %.0f mm' % mm(np.linalg.norm(Q - prim, axis=1).min()))

# 5 footprints
for n in ('Supraspinatus muscle (insertion)', 'Infraspinatus muscle (insertion)'):
    V, F = get(n)
    c = V - V.mean(0); w, U = np.linalg.eigh(c.T @ c)
    p = c @ U[:, ::-1][:, :2]; L, W = np.ptp(p[:, 0]), np.ptp(p[:, 1])
    tri = V[F]; area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1).sum() / 4
    print('5 %s: long %.1f x short %.1f mm, fill %.2f (0.5 triangle, 1 rectangle), '
          'centroid %.0f mm below head top, %.0f mm %s of head centre' % (
              n.split()[0], mm(L), mm(W), area / (L * W), mm(H[:, 2].max() - V[:, 2].mean()),
              mm(abs(V[:, 1].mean() - head[1])), 'anterior' if V[:, 1].mean() < head[1] else 'posterior'))
