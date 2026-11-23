"""Select region (tools/region.py) structures in Z-Anatomy and assign layers/names."""
import re
from mathutils import Vector

from region import ACTIVE as REG, R
FASCIA = re.compile(r'fascia|aponeurosis|retinaculum|septum|fibrous shea|'
                    r'superficial transverse metacarpal', re.I)
SHEATH = re.compile(r'sheath', re.I)
BURSA = re.compile(r'bursa', re.I)
VEIN = re.compile(r'vein|venous', re.I)


def system(o):
    for c in o.users_collection:
        m = re.match(r'^(\d):', c.name)
        if m:
            return int(m.group(1))
    return 0


def world_bbox(o):
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return ([min(v[i] for v in bb) for i in range(3)],
            [max(v[i] for v in bb) for i in range(3)])


def context_text(o):
    s = [c.name for c in o.users_collection]
    p = o.parent
    while p:
        s.append(p.name)
        p = p.parent
    return ' '.join(s) + ' ' + o.name


def base_name(n):
    return R['sides'].sub('', n) if R['sides'].search(n) else n


def is_context(o):
    return system(o) == 1 and bool(R['context_bones'].search(base_name(o.name))) and \
        ('.' not in o.name or o.name.endswith('.r'))


def selected(o):
    """Region rules live in tools/region.py."""
    if o.type not in ('MESH', 'CURVE') or system(o) not in REG['systems']:
        return False
    if is_context(o) or R['always'].search(o.name):
        return True
    if not R['sides'].search(o.name):
        return False
    s, b = system(o), base_name(o.name)
    if s == 1:
        return bool(R['bones'].search(b))
    if s in (2, 4) and R['whole_muscles'].search(b):
        return True
    if s == 6 and not R['nodes'].search(b):
        return False
    mn, mx = world_bbox(o)
    cx, cz = (mn[0] + mx[0]) / 2, (mn[2] + mx[2]) / 2
    if s in (2, 4) and cx < REG['limb_x'] and mx[2] > REG['elbow_top'] and mn[2] < REG['z_lo']:
        return True
    if R['exclude'].search(b) and not R['exclude_keep'].search(b):
        return False
    if s in (5, 7) and R['limb_names'].search(b) and mx[2] >= REG['z_lo'] and mn[2] <= REG['z_hi']:
        return cx < REG['x_max']
    return cx < REG['x_max'] and REG['z_lo'] <= cz <= REG['z_hi']


def layer(o):
    s, n = system(o), o.name
    if s == 1:
        return 'context_bone' if is_context(o) else 'bone'
    if s == 2:
        return 'attachment'
    if s == 3:
        return 'ligament_capsule'
    if s == 4:
        if FASCIA.search(n):
            return 'fascia_retinacula'
        if BURSA.search(n):
            return 'bursa'
        if SHEATH.search(n):
            return 'tendon_sheath'
        return 'muscle'
    if s == 5:
        return 'vein' if VEIN.search(n) else 'artery'
    if s == 6:
        return 'lymph_node'
    if s == 7:
        return 'nerve'
    return 'skin'


def clean_name(n):
    """'Median nerve.r' -> 'Median nerve'; 'FDS.e2r' -> ('FDS (insertion 2)', 'insertion')."""
    base, suf = n.rsplit('.', 1) if '.' in n else (n, '')
    base = base.strip()
    if base.startswith('(') and base.endswith(')'):
        base = base[1:-1]
    kind = None
    m = re.match(r'^([oe])(\d*)r$', suf)
    if m:
        kind = 'origin' if m.group(1) == 'o' else 'insertion'
        base = '%s (%s%s)' % (base, kind, ' ' + m.group(2) if m.group(2) else '')
    return base.replace(':', '-'), kind


def lighten_curve(o):
    """Lower curve/bevel resolution so vessels and nerves stay light."""
    c = o.data
    c.resolution_u = min(c.resolution_u, 3)
    c.bevel_resolution = min(c.bevel_resolution, 2)
    if getattr(c, 'bevel_mode', '') == 'OBJECT' and c.bevel_object:
        bo = c.bevel_object.data
        bo.resolution_u = min(bo.resolution_u, 2)
