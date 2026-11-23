"""Numeric check of assets/gaps (no pictures): for each new structure, % of its vertices
inside bone / inside tendon, and median clearance to them (mm). Run: python3 -I tools/check_gaps.py"""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import numpy as np
from scipy.spatial import cKDTree
import glbio, gapgeom as G
from gapgeom import MM

H = glbio.read(os.path.join(ROOT, 'data/raw/hand_raw.glb'))
N = glbio.read(os.path.join(ROOT, 'data/raw/gaps_raw.glb'))
man = {e['name']: e['layer'] for e in json.load(open(os.path.join(ROOT, 'assets/manifest.json')))}


def oriented(names, mat=None):
    P, Nn = [], []
    for n in names:
        for v, f, m in H[n]:
            if mat and m != mat:
                continue
            a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
            fn = G.unit(np.cross(b - a, c - a))
            for w in ((1 / 3, 1 / 3), (0.6, 0.2), (0.2, 0.6), (0.2, 0.2)):
                P.append(a + w[0] * (b - a) + w[1] * (c - a)); Nn.append(fn)
    return cKDTree(np.vstack(P)), np.vstack(Nn)


def signed(tn, x):
    tree, nrm = tn
    d, i = tree.query(x)
    s = np.einsum('ij,ij->i', x - tree.data[i], nrm[i])
    return np.where((s < 0) & (d < 4 * MM), -d, d)     # sign is only reliable near the surface


bone = oriented([n for n in H if man.get(n) == 'bone'])
tend = oriented([n for n in H if man.get(n) == 'muscle'], 'Tendon')
print('%-58s %6s %6s %7s %7s' % ('structure', 'inBone', 'inTend', 'dBone', 'dTend'))
rows = []
for name, prims in N.items():
    v = prims[0][0]
    if prims[0][2] == 'Fat':
        continue
    sb, st = signed(bone, v), signed(tend, v)
    rows.append((name, (sb < -0.2 * MM).mean() * 100, (st < -0.2 * MM).mean() * 100,
                 np.median(np.abs(sb)) / MM, np.median(np.abs(st)) / MM))
for r in rows:
    if len(sys.argv) > 1 or r[1] > 5 or r[2] > 5:
        print('%-58s %5.0f%% %5.0f%% %6.1f %6.1f' % r)
a = np.array([r[1:] for r in rows])
print('all %d: mean %% in bone %.1f, in tendon %.1f; worst bone %.0f%% (%s)' % (
    len(rows), a[:, 0].mean(), a[:, 1].mean(), a[:, 0].max(), rows[int(a[:, 0].argmax())][0]))
