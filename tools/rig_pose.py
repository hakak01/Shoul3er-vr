"""Phase D2: Python copy of js/rig.js forward kinematics (pose -> bone delta matrices) and linear-blend skinning.
Keep in step with Rig.deltas() / Rig.ht() in js/rig.js. All coordinates are glTF metres."""
import json, struct
import numpy as np

KEYS = [('clavicle', 'retraction'), ('clavicle', 'elevation'), ('clavicle', 'posteriorRotation'),
        ('scapula', 'upwardRotation'), ('scapula', 'posteriorTilt'), ('scapula', 'externalRotation')]


def rx(a):
    c, s = np.cos(np.radians(a)), np.sin(np.radians(a)); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):
    c, s = np.cos(np.radians(a)), np.sin(np.radians(a)); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rz(a):
    c, s = np.cos(np.radians(a)), np.sin(np.radians(a)); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def axis_rot(ax, a):
    ax = np.asarray(ax, float); ax = ax / np.linalg.norm(ax); K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    t = np.radians(a); return np.eye(3) + np.sin(t) * K + (1 - np.cos(t)) * K @ K


def interp(k, x):
    k = np.asarray(k, float); return float(np.interp(x, k[:, 0], k[:, 1]))


def curve(c, e, pl):
    """rhythm curve: keyframe list, or {plane: list} interpolated over the plane (clamped)"""
    if isinstance(c, list): return interp(c, e)
    ks = sorted(c, key=float); return interp([[float(p), interp(c[p], e)] for p in ks], pl)


def ht(plane, elev, rot):
    """humerothoracic rotation (thorax axes): swing in the plane of elevation, then twist (ER +)"""
    return ry(plane) @ rx(-elev) @ ry(-plane) @ ry(-rot)


def contact(T, X0, piv):
    """Scapulothoracic contact (Seth 2016 idea: the scapula glides on a thorax ellipsoid). Extra rotation of the
    scapula about the AC joint (piv) so that its costal sample points X0 stay at ellipsoid level >= T['target'].
    Same steps as scapContact() in js/wrap.js."""
    c, E, r, tgt = np.array(T['c']), np.array(T['axes']), np.array(T['r']), np.array(T['target'])
    Rx = np.eye(3)
    for _ in range(8):
        X = (X0 - piv) @ Rx.T + piv
        y = ((X - c) @ E) / r; lv = np.linalg.norm(y, axis=1); v = tgt - lv; k = int(v.argmax())
        if v[k] <= 1e-4: break
        g = E @ (y[k] / r) / lv[k]; gn = np.linalg.norm(g); n = g / gn
        ax = np.cross(X[k] - piv, n); s = np.linalg.norm(ax)
        if s < 1e-6: break
        Rx = axis_rot(ax / s, np.degrees(min(v[k] / gn / s, np.radians(10)))) @ Rx
    return Rx


class Pose:
    def __init__(self, rig, rhythm, wrap=None):
        self.rig, self.rh, self.wrap = rig, rhythm, wrap
        self.F = {k: np.array(v) for k, v in rig['frames'].items()}
        self.J = {k: np.array(v) for k, v in rig['joints'].items()}
        self.rest = rig['rest']; self.names, self.parents = rig['bones'], rig['parents']

    def default(self):
        r = self.rest; return dict(plane=r['humerus'][0], elev=r['humerus'][1], rot=r['humerus'][2],
                                   elbow=r['elbowFlexion'], sup=r['supination'])

    def rhythm_at(self, e, pl):
        e0 = self.rest['humerus'][1]
        return {s + '.' + k: curve(self.rh[s][k], e, pl) - curve(self.rh[s][k], e0, pl) for s, k in KEYS}

    def rotations(self, p):
        r, d, F = self.rest, self.rhythm_at(p['elev'], p['plane']), self.F
        seg = lambda rel, Fs: F['thorax'] @ rel @ Fs.T
        yxz = lambda a, b, c: ry(a) @ rx(b) @ rz(c)
        Q = {'thorax': np.eye(3)}
        Q['clavicle'] = seg(yxz(r['clavicle'][0] - d['clavicle.retraction'], r['clavicle'][1] - d['clavicle.elevation'],
                                r['clavicle'][2] + d['clavicle.posteriorRotation']), F['clavicle'])
        Q['scapula'] = seg(yxz(r['scapula'][0] - d['scapula.externalRotation'], r['scapula'][1] - d['scapula.upwardRotation'],
                               r['scapula'][2] + d['scapula.posteriorTilt']), F['scapula'])
        Q['humerus'] = seg(ht(p['plane'], p['elev'], p['rot']), F['humerus'])
        Q['ulna'] = Q['humerus'] @ axis_rot(self.rig['axes']['elbow'], p['elbow'] - r['elbowFlexion'])
        Q['radius'] = Q['ulna'] @ axis_rot(self.rig['axes']['forearm'], p['sup'] - r['supination'])
        return Q

    def deltas(self, p):
        """-> array (nbones, 4, 4): x_posed = D[b] @ [x_rest, 1]"""
        Q, D = self.rotations({**self.default(), **p}), np.zeros((len(self.names), 4, 4))
        for i, n in enumerate(self.names):
            h = self.J[n]; par = self.parents[i]
            ph = D[par, :3, :3] @ h + D[par, :3, 3] if par >= 0 else h
            if n == 'scapula' and self.wrap:
                T = self.wrap['thorax']; X0 = (np.array(T['samples']) - h) @ Q[n].T + ph
                Rx = contact(T, X0, ph); self.extra = Rx; Q[n] = Rx @ Q[n]
            D[i, :3, :3] = Q[n]; D[i, :3, 3] = ph - Q[n] @ h; D[i, 3, 3] = 1
        return D


def lbs(D, V, W):
    """V (n,3) rest, W (n, nbones) weights -> posed (n,3), blended linear parts A (n,3,3)"""
    A = np.einsum('nb,bij->nij', W, D[:, :3, :3]); t = W @ D[:, :3, 3]
    return np.einsum('nij,nj->ni', A, V) + t, A


def read_skinned(path):
    """-> (json, blob, {node name: [dict(v, f, W, prim) per primitive]}) from an uncompressed skinned GLB"""
    b = open(path, 'rb').read(); n = struct.unpack('<I', b[12:16])[0]
    j = json.loads(b[20:20 + n]); blob = b[20 + n + 8:]
    CT = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}; NC = {'SCALAR': 1, 'VEC3': 3, 'VEC4': 4}
    def acc(i):
        a = j['accessors'][i]; bv = j['bufferViews'][a['bufferView']]; k = NC[a['type']]
        x = np.frombuffer(blob, CT[a['componentType']], a['count'] * k, bv.get('byteOffset', 0) + a.get('byteOffset', 0))
        return x.reshape(-1, k) if k > 1 else x
    nb = len(j['skins'][0]['joints']); out = {}
    for nd in j['nodes']:
        if 'mesh' not in nd: continue
        ps = []
        for p in j['meshes'][nd['mesh']]['primitives']:
            at = p['attributes']; idx = acc(at['JOINTS_0']).astype(int); w = acc(at['WEIGHTS_0']).astype(float)
            W = np.zeros((len(idx), nb)); np.add.at(W, (np.repeat(np.arange(len(idx)), 4), idx.ravel()), w.ravel())
            ps.append(dict(v=acc(at['POSITION']).astype(float), f=acc(p['indices']).astype(int).reshape(-1, 3), W=W, prim=p))
        out[nd['name']] = ps
    return j, bytearray(blob), out
