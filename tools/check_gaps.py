"""Numeric check of assets/gaps (no pictures): for each new structure, % of its vertices inside bone /
cartilage / muscle, and the closest bone (mm). Plus a few anatomy relations. Run: python3 -I tools/check_gaps.py"""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import numpy as np
from scipy.spatial import cKDTree
import glbio, gapgeom as G
from gapgeom import MM

H = glbio.read(os.path.join(ROOT, 'data/raw/shoulder_raw.glb'))
N = glbio.read(os.path.join(ROOT, 'data/raw/gaps_raw.glb'))
man = {e['name']: e for e in json.load(open(os.path.join(ROOT, 'assets/manifest.json')))}
C = np.array(json.load(open(os.path.join(ROOT, 'assets/model.json')))['center'])
names = lambda *L: [n for n in H if man.get(n, {}).get('layer') in L and not man[n].get('kind')]
part = lambda n, keep=lambda m: True: G.merge([(v, f) for v, f, m in H[n] if keep(m)])
bone = G.Solid([part(n, lambda m: 'Cartilage' not in m) for n in names('bone', 'context_bone')
                if any('Cartilage' not in m for _, _, m in H[n])])
cart = G.Solid([part(n, lambda m: 'Cartilage' in m) for n in names('bone') if any('Cartilage' in m for _, _, m in H[n])])
musc = {n: G.Solid([part(n)]) for n in names('muscle')}

print('%-50s %6s %6s %6s %7s  %s' % ('structure', 'inBone', 'inCart', 'inMusc', 'dBone', 'muscles entered (>5%)'))
for name, prims in N.items():
    v = prims[0][0]
    if prims[0][2] == 'Fat':
        continue
    sb, sc = bone.signed(v)[0], cart.signed(v)[0]
    inm = {m: (S.signed(v)[0] < -0.3 * MM).mean() for m, S in musc.items()}
    anym = np.any([S.signed(v)[0] < -0.3 * MM for S in musc.values()], axis=0).mean()
    print('%-50s %5.0f%% %5.0f%% %5.0f%% %6.1f  %s' % (name[:50], (sb < -0.2 * MM).mean() * 100, (sc < -0.2 * MM).mean() * 100,
          anym * 100, sb.min() / MM, ', '.join('%s %.0f%%' % (m.replace(' muscle', '')[:24], p * 100)
                                               for m, p in sorted(inm.items(), key=lambda x: -x[1]) if p > 0.05)))


def cen(d, n):
    return np.vstack([v for v, f, m in d[n]]).mean(0)


ax = lambda n: np.vstack([v for v, f, m in H[n]])
ig = np.vstack([N[n][0][0] for n in N if 'inferior glenohumeral' in n])
print('IGHL complex <-> axillary nerve: closest %.1f mm' % (cKDTree(ax('Axillary nerve')).query(ig)[0].min() / MM))
A = ax('Axillary artery'); A = np.array([A[i].mean(0) for i in cKDTree(A).query_ball_point(A, 4 * MM)])
pm = ax('Pectoralis minor muscle')
A2 = A[[((np.linalg.norm(np.cross(pm - p, [0, 0, 1.]), axis=1) < 8 * MM) & (pm[:, 2] > p[2])).any() for p in A]]
for n in ('Lateral cord of brachial plexus', 'Medial cord of brachial plexus', 'Posterior cord of brachial plexus'):
    P = (N if n in N else H)[n][0][0]
    d, i = cKDTree(A2).query(P); P, d = P[d < 12 * MM], (P - A2[i])[d < 12 * MM]
    d = np.median(d, 0) / MM if len(d) else [np.nan] * 3
    print('%-34s vs 2nd part of axillary artery: lateral %+.0f, anterior %+.0f, up %+.0f mm (%d pts)' % (n, -d[0], d[2], d[1], len(P)))
