"""Phase A: build assets/shoulder.glb + assets/manifest.json from Z-Anatomy + BodyParts3D.
Run from the repo root:  python3 -I tools/build_assets.py
Needs: pip install bpy scipy ; Node.js (npx) for meshopt compression."""
import os, sys, json, subprocess, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import bpy, bmesh
import numpy as np
from scipy.spatial import cKDTree
import zsel, boneswap, decimate
from region import ACTIVE as REG, R

BLEND = os.path.join(ROOT, 'data/raw/zblend/Z-Anatomy/Startup.blend')
BP3D = os.path.join(ROOT, 'data/raw/bp3d/assets/BodyParts3D_data')
OUT = os.path.join(ROOT, 'assets')
GLB = 'shoulder.glb'
RAW_GLB = os.path.join(ROOT, 'data/raw/shoulder_raw.glb')
LOG = os.path.join(ROOT, 'data/raw/build_log.txt')
log_f = open(LOG, 'w')


def log(*a):
    print(*a, file=log_f, flush=True)


def mesh_arrays(me):
    v = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', v)
    me.calc_loop_triangles()
    t = np.empty(len(me.loop_triangles) * 3, int)
    me.loop_triangles.foreach_get('vertices', t)
    p = np.empty(len(me.loop_triangles), int)
    me.loop_triangles.foreach_get('polygon_index', p)
    mi = np.empty(len(me.polygons), int)
    me.polygons.foreach_get('material_index', mi)
    return v.reshape(-1, 3), t.reshape(-1, 3), mi[p]


def set_geometry(me, v, f, mat):
    mats = list(me.materials)
    me.clear_geometry()
    me.from_pydata(v.tolist(), [], f.tolist())
    me.update()
    me.materials.clear()
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set('material_index', np.asarray(mat, np.int32))


def extract():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    src = [o for o in bpy.data.objects if zsel.selected(o)]
    for o in src:
        if o.type == 'CURVE':
            zsel.lighten_curve(o)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    col = bpy.data.collections.new('EXPORT')
    bpy.context.scene.collection.children.link(col)
    out, used = [], set()
    for o in src:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
        if len(me.polygons) == 0:
            log('skip (no faces):', o.name)
            continue
        me.transform(o.matrix_world)
        for i, s in enumerate(o.material_slots):
            if i < len(me.materials):
                me.materials[i] = s.material
            else:
                me.materials.append(s.material)
        name, kind = zsel.clean_name(o.name)
        while name in used:
            name += ' 2'
        used.add(name)
        no = bpy.data.objects.new(name, me)
        col.objects.link(no)
        out.append(dict(obj=no, name=name, src=o.name, layer=zsel.layer(o), kind=kind,
                        source='Z-Anatomy'))
    return out


def swap_bones(items):
    names = {}
    for line in open(os.path.join(BP3D, 'parts_list_e.txt'), encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('\t')
        if len(p) >= 2:
            names[p[1].strip()] = p[0].strip()
    stl = {f[:-4] for f in os.listdir(os.path.join(BP3D, 'stl'))}
    cand = {}
    for n, fma in names.items():
        if fma in stl:
            v, f = boneswap.load_stl(os.path.join(BP3D, 'stl', fma + '.stl'))
            cand[n] = (v, f)
    bones = [it for it in items if it['layer'] == 'bone']
    zdat = {it['name']: mesh_arrays(it['obj'].data) for it in bones}
    pairs = [(it['name'], boneswap.bp_name(it['name'])) for it in bones]
    pairs = [(z, b) for z, b in pairs if b in cand]
    zc = np.array([zdat[z][0].mean(0) for z, _ in pairs])
    bc = np.array([cand[b][0].mean(0) for _, b in pairs])
    s, R, t = boneswap.umeyama(bc, zc)
    log('global fit: scale %.6f, rot-dev %.2f deg, pairs %d' % (
        s, np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))), len(pairs)))
    cnames = list(cand)
    cv = {n: cand[n][0] * s @ R.T + t for n in cnames}
    tree = cKDTree(np.array([cv[n].mean(0) for n in cnames]))
    res = []
    for it in bones:
        zv, zf, zm = zdat[it['name']]
        zvol = boneswap.volume(zv, zf)
        match = None
        for k in tree.query(zv.mean(0), k=4)[1]:
            n = cnames[k]
            r = boneswap.volume(cv[n], cand[n][1]) / max(zvol, 1e-12)
            if 0.5 < r < 2.0:
                match = n
                break
        if match is None:
            log('%-45s no BP3D match -> keep Z-Anatomy' % it['name'])
            res.append((it['name'], None, None, 'kept'))
            continue
        if match != boneswap.bp_name(it['name']):
            log('  note: nearest-centroid match %s differs from name %s' % (match, boneswap.bp_name(it['name'])))
        nv, nf, mat, mean, mx = boneswap.swap_bone(zv, zf, zm, cv[match], cand[match][1])
        ok = mean <= 1.5 and len(nf) >= len(zf)   # only swap for a more detailed bone
        ci = [i for i, m in enumerate(it['obj'].data.materials) if m and 'Cartilage' in m.name]
        cf = lambda a: np.isin(a, ci).mean() * 100
        log('%-45s -> %-38s mean %.2f mm  max %.2f mm  tris %d->%d  cartilage %.0f%%->%.0f%%  %s' % (
            it['name'], match, mean, mx, len(zf), len(nf), cf(zm), cf(mat), 'SWAPPED' if ok else 'kept Z-Anatomy'))
        if ok:
            set_geometry(it['obj'].data, nv, nf, mat)
            it['source'] = 'BodyParts3D (ICP-fitted to Z-Anatomy)'
        res.append((it['name'], mean, mx, 'swapped' if ok else 'kept'))
    return res


def repair(it):
    me = it['obj'].data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if len(bm.verts) < 300:
        before = [v.co.copy() for v in bm.verts]
        for _ in range(2):
            bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=0.5,
                                  use_axis_x=True, use_axis_y=True, use_axis_z=True)
        for v, b in zip(bm.verts, before):
            d = v.co - b
            if d.length > 0.0003:
                v.co = b + d.normalized() * 0.0003
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    return len(me.polygons)


def export(items):
    # Z-Anatomy world coordinates are kept (no recentring); the viewer recentres.
    bpy.ops.object.select_all(action='DESELECT')
    for it in items:
        it['obj'].select_set(True)
    bpy.ops.export_scene.gltf(filepath=RAW_GLB, export_format='GLB', use_selection=True,
                              export_yup=True, export_texcoords=False, export_normals=True,
                              export_materials='EXPORT', export_image_format='NONE',
                              export_animations=False, export_skins=False, export_morph=False,
                              export_cameras=False, export_lights=False, export_extras=False)


def main():
    items = extract()
    log('extracted', len(items))
    res = swap_bones(items)
    tri = {}
    for it in items:
        tri[it['name']] = repair(it)
    log('before budget: %d triangles' % sum(tri.values()))
    log('after flat-muscle decimation: %d' % decimate.to_budget(items, tri, REG['budget'], R['flat'], log))
    log('after footprint decimation: %d' % decimate.to_budget(items, tri, REG['budget'], R['footprints'], log))
    export(items)
    os.makedirs(OUT, exist_ok=True)
    man = []
    for it in items:
        e = dict(name=it['name'], layer=it['layer'], source=it['source'], approx=False,
                 triangles=tri[it['name']])
        if it['kind']:
            e['kind'] = it['kind']
        man.append(e)
    json.dump(man, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1)
    subprocess.run('npx -y -q @gltf-transform/cli meshopt "%s" "%s" --level medium' % (
        RAW_GLB, os.path.join(OUT, GLB)), shell=True, check=True,
        stdout=subprocess.DEVNULL)
    c = collections.Counter(e['layer'] for e in man)
    tl = collections.Counter()
    for e in man:
        tl[e['layer']] += e['triangles']
    log('per layer (objects, triangles):', {k: (c[k], tl[k]) for k in c})
    log('total triangles', sum(tri.values()))
    log('top10', sorted(tri.items(), key=lambda x: -x[1])[:10])
    log('swap: %d swapped, %d kept' % (sum(r[3] == 'swapped' for r in res),
                                       sum(r[3] == 'kept' for r in res)))
    log('GLB MB raw %.1f, compressed %.1f' % (os.path.getsize(RAW_GLB) / 1e6,
        os.path.getsize(os.path.join(OUT, GLB)) / 1e6))


if __name__ == '__main__':
    main()
