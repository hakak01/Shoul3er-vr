"""Phase D2 corrective shapes. At each key pose: skin (LBS) the muscles/skin/fat/fascia/bursae, push them out of
the humeral-head sphere, the thorax ellipsoid and the real bones (never deeper than at rest), relax (spatial
smoothing of the push + volume restore for closed muscles), and store the change in rest space (morph target).
Runtime weights: piecewise-linear in the arm sliders (weights(); same as js/wrap.js)."""
import numpy as np
import scipy.sparse as sp
from scipy.spatial import cKDTree
from gapgeom import MM, unit
import rig_pose as RP

POSES = [('abd90', dict(plane=0, elev=90, rot=0)), ('fullElev', dict(plane=30, elev=170, rot=0)),
         ('erSide', dict(elev=0, rot=90)), ('irSide', dict(elev=0, rot=-80)),
         ('aber', dict(plane=0, elev=90, rot=90)), ('crossBody', dict(plane=135, elev=90, rot=0))]
HEAD_PAD, BONE_PAD, SMOOTH_R = 1.5 * MM, 0.5 * MM, 5 * MM


def angle(Ra, Rb):
    return np.degrees(np.arccos(np.clip((np.trace(Ra.T @ Rb) - 1) / 2, -1, 1)))


def blend_params(P):
    d0 = P.default(); return dict(elev0=d0['elev'], rot0=d0['rot'], elevMid=90.0, elevFull=170.0, rotER=90.0, rotIR=-80.0,
                                  planeCross=135.0, rotABER=90.0)


def weights(B, p):
    """weights of [abd90, fullElev, erSide, irSide, aber, crossBody] from the sliders (same as js/wrap.js):
    elevation: side -> 90 -> full; at the side rotation picks ER/IR; at 90 plane picks abduction/cross-body and
    rotation picks ABER. Exact at the 6 poses, 0 at rest."""
    c = lambda x: min(max(x, 0.0), 1.0); e, pl, r = p['elev'], p['plane'], p['rot']
    hi = c((e - B['elevMid']) / (B['elevFull'] - B['elevMid']))
    mid = c((e - B['elev0']) / (B['elevMid'] - B['elev0'])) - hi; lo = 1 - mid - hi
    er = c((r - B['rot0']) / (B['rotER'] - B['rot0'])); ir = c((r - B['rot0']) / (B['rotIR'] - B['rot0']))
    x = c(pl / B['planeCross']); ab = c(r / B['rotABER'])
    return np.array([mid * (1 - x) * (1 - ab), hi, lo * er, lo * ir, mid * (1 - x) * ab, mid * x])


class Group:
    """all vertices to correct, welded per structure"""
    def __init__(self, items):          # items: [(key, prims [dict v f W], is_muscle)]
        U, W, F, own, self.maps, self.closed, o = [], [], [], [], [], [], 0
        for si, (key, prims, mus) in enumerate(items):
            allv = np.vstack([p['v'] for p in prims]); k = np.round(allv / (0.01 * MM)).astype(np.int64)
            _, first, inv = np.unique(k, axis=0, return_index=True, return_inverse=True); inv = inv.ravel()
            Ws = np.vstack([p['W'] for p in prims]); s, maps = 0, []
            for p in prims: maps.append(inv[s:s + len(p['v'])] + o); F.append(inv[s:s + len(p['v'])][p['f']] + o); s += len(p['v'])
            U.append(allv[first]); W.append(Ws[first]); own.append(np.full(len(first), si)); self.maps.append(maps)
            self.closed.append(mus); o += len(first)
        self.U, self.W, self.F, self.own = np.vstack(U), np.vstack(W), np.vstack(F), np.concatenate(own)
        self.items = items
        e = np.sort(np.vstack([self.F[:, [0, 1]], self.F[:, [1, 2]], self.F[:, [2, 0]]]), 1)
        open_v = np.zeros(len(self.U), bool); ee, c2 = np.unique(e, axis=0, return_counts=True); open_v[ee[c2 == 1].ravel()] = True
        for si in range(len(items)):                      # volume restore only for (nearly) closed muscles
            m = self.own == si; self.closed[si] = self.closed[si] and open_v[m].mean() < 0.02
        self.mix = np.clip(2 * (1 - self.W.max(1)), 0, 1)  # 0 = one bone, 1 = 50/50 blend (where LBS loses volume)


def volume(X, F, sel):
    a, b, c = X[F[sel, 0]], X[F[sel, 1]], X[F[sel, 2]]; return np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6


def normals_area(X, F):
    fn = np.cross(X[F[:, 1]] - X[F[:, 0]], X[F[:, 2]] - X[F[:, 0]]); N = np.zeros_like(X); ar = np.zeros(len(X))
    for k in range(3): np.add.at(N, F[:, k], fn); np.add.at(ar, F[:, k], np.linalg.norm(fn, axis=1) / 6)
    return unit(N), ar


class Corrector:
    def __init__(self, P, G, thorax, region, bones, log):
        """bones: {bone index: wrap_fit.Bone}; region: rib points the ellipsoid was fitted to (it is valid only near them)"""
        self.region = cKDTree(region)
        self.P, self.G, self.T, self.B, self.log = P, G, thorax, bones, log
        J = P.J; self.gh = J['humerus']; self.Rs = P.rig['ghRadius'] + HEAD_PAD
        self.d0 = np.minimum(np.linalg.norm(G.U - self.gh, axis=1), self.Rs)
        self.lev0 = np.minimum(self.level(G.U), 1.0); self.girdle = G.W[:, 3:].sum(1) < 0.5
        self.sd0 = {b: np.minimum(B.signed(G.U)[0], BONE_PAD) for b, B in bones.items()}
        self.fsel = [G.own[G.F[:, 0]] == si for si in range(len(G.items))]
        self.V0 = [volume(G.U, G.F, s) if G.closed[si] else 0 for si, s in enumerate(self.fsel)]

    def level(self, X):
        T = self.T; return np.linalg.norm(((X - np.array(T['c'])) @ np.array(T['axes'])) / np.array(T['r']), axis=1)

    def project(self, Y, D, cand):
        c = D[3, :3, :3] @ self.gh + D[3, :3, 3]; v = Y - c; d = np.linalg.norm(v, axis=1); m = d < self.d0
        Y[m] = c + v[m] / d[m, None] * self.d0[m, None]
        T = self.T; E, r, cc = np.array(T['axes']), np.array(T['r']), np.array(T['c'])
        lv = self.level(Y); m = np.where((lv < self.lev0) & self.girdle)[0]           # scapulothoracic gliding plane
        m = m[self.region.query(Y[m], distance_upper_bound=0.03)[0] < 1]
        if len(m):
            y = ((Y[m] - cc) @ E) / r; g = (y / r) @ E.T / lv[m, None]; gn = np.linalg.norm(g, axis=1)
            Y[m] += g / gn[:, None] * np.minimum((self.lev0[m] - lv[m]) / gn, 10 * MM)[:, None]
        for b, B in self.B.items():
            idx = cand[b]
            if not len(idx): continue
            Di = np.linalg.inv(D[b]); xb = Y[idx] @ Di[:3, :3].T + Di[:3, 3]
            sd, q, n = B.signed(xb); need = self.sd0[b][idx]; m = sd < need - 1e-5
            if m.any(): Y[idx[m]] += (n[m] * (need[m] - sd[m])[:, None]) @ D[b, :3, :3].T
        return Y

    def pose(self, p):
        G, P = self.G, self.P; D = P.deltas(p); X, A = RP.lbs(D, G.U, G.W)
        cand = {}
        for b, B in self.B.items():
            Di = np.linalg.inv(D[b]); cand[b] = np.where(B.t.query(X @ Di[:3, :3].T + Di[:3, 3], distance_upper_bound=0.02)[0] < 1)[0]
        Y = self.project(X.copy(), D, cand); push = np.linalg.norm(Y - X, axis=1) > 0.05 * MM
        act = np.where(np.isin(G.own, np.unique(G.own[push])))[0]          # structures with any push
        K = None
        if len(act):
            pr = cKDTree(X[act]).query_pairs(SMOOTH_R, output_type='ndarray')
            pr = pr[G.own[act[pr[:, 0]]] == G.own[act[pr[:, 1]]]]
            n = len(act); i = np.r_[pr[:, 0], pr[:, 1], np.arange(n)]; j = np.r_[pr[:, 1], pr[:, 0], np.arange(n)]
            K = sp.csr_matrix((np.ones(len(i)), (i, j)), shape=(n, n)); K = sp.diags(1 / np.asarray(K.sum(1)).ravel()) @ K
        for it in range(10):
            if K is None: break
            Dsp = Y - X; Dsp[act] = K @ Dsp[act]; Y = self.project(X + Dsp, D, cand)
            if it == 6: Y = self.inflate(Y, act); Y = self.project(Y, D, cand)
        e = Y - X; AtA = np.einsum('nki,nkj->nij', A, A) + 1e-2 * np.eye(3)
        delta = np.linalg.solve(AtA, np.einsum('nki,nk->ni', A, e)[..., None])[..., 0]
        self.Y = Y
        return delta, dict(pushed=int(push.sum()), max_mm=float(np.linalg.norm(e, axis=1).max() * 1000))

    def inflate(self, Y, act):
        G = self.G; N, ar = normals_area(Y, G.F)
        for si in np.unique(G.own[act]):
            if not G.closed[si] or self.V0[si] <= 0: continue
            V1 = volume(Y, G.F, self.fsel[si])
            if V1 >= 0.995 * self.V0[si] or V1 < 0.6 * self.V0[si]: continue
            m = G.own == si; w = G.mix[m]; den = (w * ar[m]).sum()
            if den <= 0: continue
            Y[m] += N[m] * np.minimum((self.V0[si] - V1) / den * w, 3 * MM)[:, None]
        return Y
