"""Phase D2 headless geometry test (Python side): muscles after skinning + corrective shapes at the test poses.
python3 -I tools/check_wrap.py [js_dump.json]
- new muscle vertices inside a bone by > 2 mm (compared with the rest pose), per pose
- 'exploding': largest corrective displacement, NaN check, also at in-between poses
- with a dump from the browser (posed vertices of some structures): JS vs Python distance"""
import os, sys, json
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_wrap as BW, rig_pose as RP, wrap_fit as WF, wrap_morph as WM

TEST = [('rest', {}), ('abd90', dict(plane=0, elev=90, rot=0)), ('fullElev', dict(plane=30, elev=170, rot=0)),
        ('ER', dict(elev=0, rot=90)), ('IR', dict(elev=0, rot=-80)), ('ABER', dict(plane=0, elev=90, rot=90)),
        ('crossBody', dict(plane=135, elev=90, rot=0)), ('abd45', dict(plane=0, elev=45, rot=0)),
        ('flex120 ER30', dict(plane=90, elev=120, rot=30)), ('plane60 elev135', dict(plane=60, elev=135, rot=-20))]


def setup():
    rig, rh, man, data = BW.load(); wrap = json.load(open(os.path.join(BW.OUT, 'wrap.json')))
    parts, _ = BW.bones_of(data, man); Bones = {b: WF.Bone(ps) for b, ps in parts.items()}
    items = []
    for f, _ in BW.FILES:
        for node, ps in data[f].items():
            n = BW.strip(node)
            if man.get(n, {}).get('layer') in BW.MORPH_LAYERS and n not in set(BW.WR.ROPES): items.append(((f, node), ps, man[n]['layer'] == 'muscle'))
    G = WM.Group(items); z = np.load(os.path.join(BW.RAW, 'wrap_deltas.npz')); dl = [z['d%d' % i] for i in range(len(z.files))]
    return rig, rh, wrap, G, dl, Bones, items


def posed(P, wrap, G, dl, p):
    q = {**P.default(), **p}; w = WM.weights(wrap['blend'], q); D = P.deltas(q)
    X0, _ = RP.lbs(D, G.U, G.W); X, _ = RP.lbs(D, G.U + sum(wk * d for wk, d in zip(w, dl)), G.W)
    return D, X0, X, w


def main():
    rig, rh, wrap, G, dl, Bones, items = setup(); P = RP.Pose(rig, rh, wrap)
    mus = np.array([items[s][2] for s in G.own]); names = [BW.strip(k[1]) for k, _, _ in items]
    base = None; ok = True
    for nm, p in TEST:
        D, X0, X, w = posed(P, wrap, G, dl, p)
        dep = np.zeros((len(X), 6))
        for b, B in Bones.items():
            Di = np.linalg.inv(D[b]); xb = X @ Di[:3, :3].T + Di[:3, 3]
            dep[:, b] = np.where(np.linalg.norm(xb - G.U, axis=1) > 1e-3, B.signed(xb)[0], 1)   # moved vs that bone
        dep0 = np.zeros((len(X), 6))
        for b, B in Bones.items():
            Di = np.linalg.inv(D[b]); xb = X0 @ Di[:3, :3].T + Di[:3, 3]
            dep0[:, b] = np.where(np.linalg.norm(xb - G.U, axis=1) > 1e-3, B.signed(xb)[0], 1)
        bad = (dep < -0.002) & mus[:, None]
        if base is None: base = np.column_stack([B.signed(G.U)[0] < -0.002 for b, B in sorted(Bones.items())])
        new = bad & ~base; mv = np.linalg.norm(X - X0, axis=1); lbs = (((dep0 < -0.002) & mus[:, None]) & ~base).any(1).sum()
        top = np.bincount(G.own[new.any(1)], minlength=len(items)); o = [i for i in np.argsort(-top)[:3] if top[i]]
        print('%-16s w=%s new>2mm %4d (LBS only %4d; worst %.1f mm) %s | correction max %.1f mm (%s) %s' % (nm, np.round(w, 2), new.any(1).sum(), lbs,
              -(dep * new).min() * 1000, [(names[i][:24], int(top[i])) for i in o], mv.max() * 1000, names[G.own[mv.argmax()]][:20], 'NaN!' if np.isnan(X).any() else ''))
        ok &= not np.isnan(X).any() and mv.max() < 0.06
    if len(sys.argv) > 1:                                   # browser dump: {pose: {structure: [[x,y,z]...]}}
        js = json.load(open(sys.argv[1]))
        for nm, st in js.items():
            p = dict(TEST)[nm]; _, _, X, _ = posed(P, wrap, G, dl, p)
            for s, pts in st.items():
                m = np.array([names[i] == s for i in G.own]); d = cKDTree(X[m]).query(np.array(pts))[0]
                print('JS vs Python %-10s %-28s max %.2f mm, mean %.2f mm' % (nm, s[:28], d.max() * 1000, d.mean() * 1000))
    print('PASS (no NaN, corrections < 60 mm)' if ok else 'CHECK FAILED')


if __name__ == '__main__':
    main()
