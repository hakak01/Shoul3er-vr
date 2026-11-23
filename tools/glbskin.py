"""Add one skin (joint hierarchy + JOINTS_0/WEIGHTS_0) to an existing uncompressed GLB, keeping everything else."""
import json, struct
import numpy as np


def add_skin(src, dst, names, parents, heads, weights):
    """names/parents/heads: joints (heads in glTF metres, rest rotation = identity).
    weights: {node name: [W (n_verts x n_joints) per primitive]}; nodes without an entry get the root joint."""
    b = open(src, 'rb').read(); n = struct.unpack('<I', b[12:16])[0]
    j = json.loads(b[20:20 + n]); blob = bytearray(b[20 + n + 8:])
    def add(arr, ctype, typ, target=34962):
        while len(blob) % 4: blob.append(0)
        v = dict(buffer=0, byteOffset=len(blob), byteLength=arr.nbytes)
        if target: v['target'] = target
        j['bufferViews'].append(v); blob.extend(np.ascontiguousarray(arr).tobytes())
        j['accessors'].append(dict(bufferView=len(j['bufferViews']) - 1, componentType=ctype,
                                   count=len(arr), type=typ))
        return len(j['accessors']) - 1
    heads = np.asarray(heads, float); base = len(j['nodes'])
    for i, (nm, p) in enumerate(zip(names, parents)):
        t = heads[i] - (heads[p] if p >= 0 else 0)
        j['nodes'].append(dict(name='rig:' + nm, translation=t.tolist()))
    for i, p in enumerate(parents):
        if p >= 0: j['nodes'][base + p].setdefault('children', []).append(base + i)
    j['scenes'][j.get('scene', 0)]['nodes'].append(base)
    ibm = np.tile(np.eye(4, dtype=np.float32), (len(names), 1, 1))
    ibm[:, 3, :3] = -heads                                    # column-major translation
    j['skins'] = [dict(name='rig', joints=list(range(base, base + len(names))), skeleton=base,
                       inverseBindMatrices=add(ibm.reshape(-1, 16), 5126, 'MAT4', None))]
    for nd in j['nodes'][:base]:
        if 'mesh' not in nd: continue
        nd['skin'] = 0; Ws = weights.get(nd['name'])
        for k, p in enumerate(j['meshes'][nd['mesh']]['primitives']):
            cnt = j['accessors'][p['attributes']['POSITION']]['count']
            W = Ws[k] if Ws else np.eye(len(names))[np.zeros(cnt, int)]
            idx = np.argsort(-W, 1)[:, :4]; w = np.take_along_axis(W, idx, 1)
            w = (w / w.sum(1, keepdims=True)).astype(np.float32); idx[w == 0] = 0
            p['attributes']['JOINTS_0'] = add(idx.astype(np.uint8), 5121, 'VEC4')
            p['attributes']['WEIGHTS_0'] = add(w, 5126, 'VEC4')
    while len(blob) % 4: blob.append(0)
    j['buffers'] = [dict(byteLength=len(blob))]
    js = json.dumps(j, separators=(',', ':')).encode(); js += b' ' * (-len(js) % 4)
    with open(dst, 'wb') as fh:
        fh.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        fh.write(struct.pack('<II', len(js), 0x4E4F534A)); fh.write(js)
        fh.write(struct.pack('<II', len(blob), 0x004E4942)); fh.write(bytes(blob))


def add_targets(src, dst, names, targets):
    """Add relative POSITION morph targets. targets: {node name: [per primitive: list of (n,3) arrays, one per name]}"""
    b = open(src, 'rb').read(); n = struct.unpack('<I', b[12:16])[0]
    j = json.loads(b[20:20 + n]); blob = bytearray(b[20 + n + 8:])
    for nd in j['nodes']:
        T = targets.get(nd.get('name'))
        if 'mesh' not in nd or T is None: continue
        mesh = j['meshes'][nd['mesh']]
        for p, per in zip(mesh['primitives'], T):
            p['targets'] = []
            for arr in per:
                arr = np.ascontiguousarray(arr, np.float32)
                while len(blob) % 4: blob.append(0)
                j['bufferViews'].append(dict(buffer=0, byteOffset=len(blob), byteLength=arr.nbytes, target=34962))
                blob.extend(arr.tobytes())
                j['accessors'].append(dict(bufferView=len(j['bufferViews']) - 1, componentType=5126, count=len(arr), type='VEC3',
                                           min=arr.min(0).tolist(), max=arr.max(0).tolist()))
                p['targets'].append({'POSITION': len(j['accessors']) - 1})
        mesh['weights'] = [0.0] * len(names); mesh.setdefault('extras', {})['targetNames'] = list(names)
    while len(blob) % 4: blob.append(0)
    j['buffers'] = [dict(byteLength=len(blob))]
    js = json.dumps(j, separators=(',', ':')).encode(); js += b' ' * (-len(js) % 4)
    with open(dst, 'wb') as fh:
        fh.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        fh.write(struct.pack('<II', len(js), 0x4E4F534A)); fh.write(js)
        fh.write(struct.pack('<II', len(blob), 0x004E4942)); fh.write(bytes(blob))
