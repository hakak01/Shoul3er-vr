"""Error-bounded decimation (Blender 'collapse'): keep the smallest ratio whose
two-way max surface deviation is <= MAX_DEV. Used only to meet the triangle budget."""
import bpy
from mathutils.bvhtree import BVHTree

MAX_DEV = 0.0003            # metres (0.3 mm)
RATIOS = (0.06, 0.1, 0.15, 0.25, 0.35, 0.5, 0.7)


def _bvh(me):
    me.calc_loop_triangles()
    return BVHTree.FromPolygons([v.co for v in me.vertices],
                                [t.vertices for t in me.loop_triangles])


def _dev(a, b):
    """Max distance from vertices of mesh a to the surface of mesh b (metres)."""
    t = _bvh(b)
    return max((t.find_nearest(v.co)[3] or 0.0) for v in a.vertices)


def decimate(obj):
    """Decimate obj.data in place. Returns (old_tris, new_tris, deviation_mm, ratio)."""
    me = obj.data
    me.calc_loop_triangles()
    n0 = len(me.loop_triangles)
    dg = bpy.context.evaluated_depsgraph_get()
    for r in RATIOS:
        mod = obj.modifiers.new('dec', 'DECIMATE')
        mod.ratio = r
        dg.update()
        new = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), depsgraph=dg)
        obj.modifiers.remove(mod)
        dev = max(_dev(me, new), _dev(new, me))
        if dev <= MAX_DEV:
            new.calc_loop_triangles()
            n1 = len(new.loop_triangles)
            mats = list(me.materials)
            obj.data = new
            new.materials.clear()
            for m in mats:
                new.materials.append(m)
            new.polygons.foreach_set('use_smooth', [True] * len(new.polygons))
            return n0, n1, dev * 1000, r
        bpy.data.meshes.remove(new)
    return n0, n0, 0.0, 1.0


def to_budget(items, tri, budget, pattern, log):
    """Decimate items whose name matches pattern, largest first, until under budget."""
    for it in sorted(items, key=lambda i: -tri[i['name']]):
        total = sum(tri.values())
        if total <= budget:
            break
        if not pattern.search(it['name']):
            continue
        n0, n1, dev, r = decimate(it['obj'])
        tri[it['name']] = n1
        log('decimate %-50s %6d -> %6d  ratio %.2f  max dev %.2f mm' % (it['name'], n0, n1, r, dev))
    return sum(tri.values())
