"""Minimal GLB read/write with numpy (no compression). Used by build_gaps.py."""
import json, struct
import numpy as np

CT = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}
NC = {'SCALAR': 1, 'VEC3': 3, 'VEC2': 2, 'VEC4': 4}


def read(path):
    """-> {node name: list of (verts Nx3 float64, faces Mx3 int, material name)}"""
    b = open(path, 'rb').read()
    n = struct.unpack('<I', b[12:16])[0]
    j = json.loads(b[20:20 + n])
    binp = 20 + n + 8
    def acc(i):
        a = j['accessors'][i]; bv = j['bufferViews'][a['bufferView']]
        off = binp + bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        dt = CT[a['componentType']]; k = NC[a['type']]
        return np.frombuffer(b, dt, a['count'] * k, off).reshape(-1, k) if k > 1 else \
            np.frombuffer(b, dt, a['count'], off)
    out = {}
    for nd in j['nodes']:
        if 'mesh' not in nd:
            continue
        prims = []
        for p in j['meshes'][nd['mesh']]['primitives']:
            v = acc(p['attributes']['POSITION']).astype(np.float64)
            f = acc(p['indices']).astype(np.int64).reshape(-1, 3)
            prims.append((v, f, j['materials'][p['material']]['name'] if 'material' in p else ''))
        out[nd['name']] = prims
    return out


def vertex_normals(v, f):
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    vn = np.zeros_like(v)
    for k in range(3):
        np.add.at(vn, f[:, k], fn)
    return vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)


def write(path, objects):
    """objects: list of (name, [(verts, faces, material name), ...])"""
    blob = bytearray(); views = []; accs = []; mats = []; meshes = []; nodes = []
    def add(arr, target, typ):
        arr = np.ascontiguousarray(arr)
        while len(blob) % 4:
            blob.append(0)
        views.append(dict(buffer=0, byteOffset=len(blob), byteLength=arr.nbytes, target=target))
        blob.extend(arr.tobytes())
        a = dict(bufferView=len(views) - 1, componentType=5126 if arr.dtype == np.float32 else 5125,
                 count=len(arr) if typ == 'VEC3' else arr.size, type=typ)
        if typ == 'VEC3':
            a['min'] = arr.min(0).tolist(); a['max'] = arr.max(0).tolist()
        accs.append(a)
        return len(accs) - 1
    for name, prims in objects:
        ps = []
        for v, f, m in prims:
            if m not in mats:
                mats.append(m)
            v = np.asarray(v, np.float32); f = np.asarray(f, np.uint32)
            pa = add(v, 34962, 'VEC3'); na = add(vertex_normals(v.astype(np.float64), f.astype(np.int64)).astype(np.float32), 34962, 'VEC3')
            ia = add(f.reshape(-1), 34963, 'SCALAR')
            ps.append(dict(attributes=dict(POSITION=pa, NORMAL=na), indices=ia, material=mats.index(m)))
        meshes.append(dict(name=name, primitives=ps))
        nodes.append(dict(name=name, mesh=len(meshes) - 1))
    j = dict(asset=dict(version='2.0', generator='Han-vr build_gaps.py'), scene=0,
             scenes=[dict(nodes=list(range(len(nodes))))], nodes=nodes, meshes=meshes,
             materials=[dict(name=m, pbrMetallicRoughness=dict(metallicFactor=0, roughnessFactor=0.7)) for m in mats],
             accessors=accs, bufferViews=views, buffers=[dict(byteLength=len(blob))])
    js = json.dumps(j, separators=(',', ':')).encode()
    js += b' ' * (-len(js) % 4)
    while len(blob) % 4:
        blob.append(0)
    with open(path, 'wb') as fh:
        fh.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        fh.write(struct.pack('<II', len(js), 0x4E4F534A)); fh.write(js)
        fh.write(struct.pack('<II', len(blob), 0x004E4942)); fh.write(bytes(blob))
