"""Finger gaps: flexor pulleys (A1-A5, C1-C3, thumb A1/oblique/A2), MCP volar plates,
finger extensor mechanism. Shapes follow docs/SPEC.md Phase C; sizes in mm scaled by k."""
import numpy as np
from scipy.spatial import cKDTree
import gapgeom as G
from gapgeom import MM, D2R

FINGERS = [('second', 'Second', 'index finger'), ('third', 'Third', 'middle finger'),
           ('fourth', 'Fourth', 'ring finger'), ('fifth', 'Fifth', 'little finger')]
FLEX = ['Flexor digitorum profundus', 'Humero-ulnar head of flexor digitorum superficialis',
        'Radial head of flexor digitorum superficialis']
EXT = ['Extensor digitorum', 'Extensor indicis', 'Extensor digiti minimi']
INTR = ['Dorsal interossei muscles of hand', 'Palmar interossei muscles', 'Lumbrical muscles of hand',
        'Abductor digiti minimi of hand', 'Flexor digiti minimi of hand']
JOINT = ['Articular capsules of metacarpophalangeal joints', 'Collateral metacarpophalangeal ligaments',
         'Articular capsules of proximal interphalangeal joints', 'Collateral interphalangeal ligaments of hand',
         'Articular capsules of distal interphalangeal joints', 'Palmar interphalangeal ligaments']
DOYLE = 'Doyle JR, J Hand Surg Am 1988'
EXTREF = 'extensor mechanism (Green\'s Operative Hand Surgery)'


def lerp(a, b):
    return lambda u: a + (b - a) * u


def taper(T, edge=0.5):
    return lambda u, v: T * (1 - edge * (2 * np.abs(v)) ** 4)


def build(get, pts):
    """get(name, mat) -> (V, F); pts(names, mat) -> sampled points. Returns list of items."""
    out = []
    def add(name, layer, mat, parts, ref):
        out.append(dict(name=name, layer=layer, mat=mat, mesh=G.merge(parts), ref=ref))

    mc1 = get('First metacarpal bone')[0].mean(0)
    rays = {}
    bones = {o: [get(f'{M} metacarpal bone')[0]] + [get(f'{k} phalanx of {o} finger of hand')[0]
             for k in ('Proximal', 'Middle', 'Distal')] for o, M, _ in FINGERS}
    bones['first'] = [get('First metacarpal bone')[0], get('Proximal phalanx of first finger of hand')[0],
                      get('Distal phalanx of first finger of hand')[0]]
    trees = {o: cKDTree(np.vstack(b)) for o, b in bones.items()}
    keys = list(bones)
    def split(P):
        d = np.array([trees[o].query(P)[0] for o in keys]); a = d.argmin(0); dm = d.min(0)
        return {o: P[(a == i) & (dm < 12 * MM)] for i, o in enumerate(keys)}
    flex = split(np.vstack([pts(FLEX, 'Tendon'), pts(['Synovial sheaths of digits of hand']),
                            pts(['Flexor pollicis longus'], 'Tendon'), pts(['Tendon sheath of flexor pollicis longus'])]))
    ext = split(np.vstack([pts(EXT, 'Tendon'), pts(['Extensor pollicis longus', 'Extensor pollicis brevis'], 'Tendon')]))
    joint = split(pts(JOINT))
    intr = split(pts(INTR, 'Tendon'))     # intrinsic tendons only (sagittal bands pass over them)
    bpts = {o: np.vstack([G.sample_surface(b, get_f) for b, get_f in zip(bones[o], bone_faces(get, o))]) for o in keys}
    mc2 = bones['second'][0].mean(0)
    for o in keys:
        hint = (mc1 - mc2) if o == 'first' else (mc1 - bones[o][0].mean(0))
        rays[o] = G.Ray(bones[o], flex[o], hint)
    Lmid = rays['third'].joint_s[1]

    for o, _, fname in FINGERS + [('first', None, 'thumb')]:
        R = rays[o]; thumb = o == 'first'
        L1 = R.joint_s[1]; L2 = 0 if thumb else R.joint_s[2] - L1
        k = L1 / Lmid if not thumb else 1.0
        Eb = R.envelope(np.vstack([bpts[o], joint[o]]), hull=2.0 * MM)
        # --- MCP volar plate (thick distally on the proximal phalanx base, thin on the metacarpal neck)
        vp = R.strip(Eb, lambda u: -2.5 * k * MM, lerp(38 * D2R, 142 * D2R), 11 * k * MM, offset=-0.1 * MM,
                     thick=lambda u, v: (0.8 + 1.2 * (0.5 - v)) * MM * (1 - 0.4 * (2 * np.abs(u - 0.5)) ** 4), nu=24, nv=9)
        add(f'Volar plate of metacarpophalangeal joint of {fname}', 'ligament_capsule', 'Ligament', [vp],
            'MCP palmar plate')
        vpp = G.sample_surface(*vp)
        Ef = R.envelope(np.vstack([bpts[o], joint[o], flex[o], vpp]), hull=1.5 * MM)
        ann = lambda s0, s1, T=0.7, a=12: R.strip(Ef, lambda u: (s0 + s1) / 2 * MM, lerp(a * D2R, (180 - a) * D2R),
                                             (s1 - s0) * MM, offset=0.3 * MM, thick=taper(T * MM), nu=30, nv=6)
        cru = lambda s0, s1: [R.strip(Ef, lerp(s0 * MM, s1 * MM), lerp(a * D2R, b * D2R), 1.4 * MM,
                                      offset=0.35 * MM, thick=taper(0.4 * MM), nu=30, nv=4)
                              for a, b in ((15, 165), (165, 15))]
        if thumb:
            L = L1 / MM
            add('A1 pulley of thumb', 'fascia_retinacula', 'Ligament', [ann(-4, 3.5, a=28)], DOYLE)
            obl = R.strip(Ef, lerp(0.32 * L * MM, 0.62 * L * MM), lerp(140 * D2R, 35 * D2R), 7 * MM,
                          offset=0.3 * MM, thick=taper(0.7 * MM), nu=34, nv=7)
            add('Oblique pulley of thumb', 'fascia_retinacula', 'Ligament', [obl], DOYLE)
            add('A2 pulley of thumb', 'fascia_retinacula', 'Ligament', [ann(L - 7.5, L + 1.5)], DOYLE)
            continue
        P, Dj = L1 / MM, (L1 + L2) / MM
        A = {'A1': (-4.5 * k, 3.5 * k), 'A2': (5 * k, 5 * k + min(17 * k, 0.6 * P - 5 * k)),
             'A3': (P - 1.5 * k, P + 1.5 * k), 'A4': ((P + Dj) / 2 - 3.5 * k, (P + Dj) / 2 + 3.5 * k),
             'A5': (Dj - 1.5 * k, Dj + 1.5 * k)}
        for n, (s0, s1) in A.items():
            add(f'{n} pulley of {fname}', 'fascia_retinacula', 'Ligament', [ann(s0, s1, a=28 if n == 'A1' else 12)], DOYLE)
        for n, a, b in (('C1', 'A2', 'A3'), ('C2', 'A3', 'A4'), ('C3', 'A4', 'A5')):
            s0, s1 = A[a][1] + 0.5, A[b][0] - 0.5
            if s1 - s0 > 1.5:
                add(f'{n} cruciate pulley of {fname}', 'fascia_retinacula', 'Ligament', cru(s0, s1), DOYLE)
        out += extensor(R, fname, k, P, Dj, R.envelope(np.vstack([bpts[o], joint[o], ext[o], intr[o]]), hull=1.5 * MM),
                        R.envelope(np.vstack([bpts[o], joint[o], ext[o]]), hull=1.5 * MM),
                        R.envelope(np.vstack([bpts[o], joint[o], ext[o], flex[o], vpp]), hull=1.5 * MM))
    return out, rays


def bone_faces(get, o):
    if o == 'first':
        names = ['First metacarpal bone', 'Proximal phalanx of first finger of hand', 'Distal phalanx of first finger of hand']
    else:
        M = dict((a, b) for a, b, _ in FINGERS)[o]
        names = [f'{M} metacarpal bone'] + [f'{k} phalanx of {o} finger of hand' for k in ('Proximal', 'Middle', 'Distal')]
    return [get(n)[1] for n in names]


def extensor(R, fname, k, P, Dj, Es, Ee, Ea):
    """Sagittal bands, central slip, lateral bands, terminal tendon, triangular ligament,
    transverse and oblique retinacular ligaments. phi: 0 radial, 90 palmar, -90 dorsal."""
    out = []
    def add(name, layer, mat, parts):
        out.append(dict(name=f'{name} of {fname}', layer=layer, mat=mat, mesh=G.merge(parts), ref=EXTREF))
    Lm = Dj - P
    # angle of each lateral band from the dorsal midline (deg) along s (mm)
    al_s = np.array([0.3 * P, 0.7 * P, P, P + 0.5 * Lm, P + 0.8 * Lm])
    al_a = np.array([80, 62, 50, 25, 4.0])
    alpha = lambda s: np.interp(s / MM, al_s, al_a) * D2R
    mir = lambda f: (lambda u: np.pi - f(u))          # radial path -> ulnar path
    sag = R.strip(Es, lambda u: -2.5 * k * MM, lerp(60 * D2R, -240 * D2R), 7 * k * MM,
                  offset=0.3 * MM, thick=taper(0.6 * MM), nu=60, nv=7)
    add('Sagittal bands', 'ligament_capsule', 'Ligament', [sag])
    cs = R.strip(Ee, lerp(0.5 * P * MM, (P + 3 * k) * MM), lambda u: -90 * D2R,
                 lambda u: (4.5 - u) * k * MM, offset=0.05 * MM, thick=taper(0.8 * MM), nu=30, nv=6)
    add('Central slip', 'muscle', 'Tendon', [cs])
    s_lb = lerp(0.3 * P * MM, (P + 0.8 * Lm) * MM)
    lb_r = lambda u: -np.pi / 2 + alpha(s_lb(u))
    bands = [R.strip(Ee, s_lb, f, 2.2 * k * MM, offset=0.3 * MM, thick=taper(0.9 * MM), nu=50, nv=5)
             for f in (lb_r, mir(lb_r))]
    add('Lateral bands', 'muscle', 'Tendon', bands)
    tt = R.strip(Ee, lerp((P + 0.76 * Lm) * MM, (Dj + 2.5 * k) * MM), lambda u: -90 * D2R,
                 lambda u: (3.6 - 0.6 * u) * k * MM, offset=0.3 * MM, thick=taper(0.9 * MM), nu=24, nv=6)
    add('Terminal extensor tendon', 'muscle', 'Tendon', [tt])
    s_tri = lerp((P + 0.2 * Lm) * MM, (P + 0.68 * Lm) * MM)
    tri_w = lambda u: np.maximum(2 * alpha(s_tri(u)) * R.radius(Ee, s_tri(u), -np.pi / 2 * np.ones_like(u))
                                 - 1.6 * k * MM, 0.5 * MM)
    tri = R.strip(Ee, s_tri, lambda u: -90 * D2R, tri_w, offset=0.45 * MM, thick=taper(0.3 * MM), nu=20, nv=7)
    add('Triangular ligament', 'ligament_capsule', 'Ligament', [tri])
    a_pip = alpha(P * MM) / D2R
    trl_r = lerp((-90 + a_pip + 12) * D2R, 50 * D2R)
    trl = [R.strip(Ea, lambda u: (P - 0.5 * k) * MM, f, 2.5 * k * MM, offset=0.5 * MM, thick=taper(0.35 * MM),
                   nu=30, nv=5) for f in (trl_r, mir(trl_r))]
    add('Transverse retinacular ligaments', 'ligament_capsule', 'Ligament', trl)
    path = G.catmull([[0.6 * P, 55], [P, 12], [P + 0.45 * Lm, -40], [P + 0.8 * Lm, -76]], 20)
    u_p = np.linspace(0, 1, len(path))
    orl_s = lambda u: np.interp(u, u_p, path[:, 0]) * MM
    orl_r = lambda u: np.interp(u, u_p, path[:, 1]) * D2R
    orl = [R.strip(Ea, orl_s, f, 1.3 * MM, offset=0.6 * MM, thick=taper(0.5 * MM), nu=60, nv=4)
           for f in (orl_r, mir(orl_r))]
    add('Oblique retinacular ligaments', 'ligament_capsule', 'Ligament', orl)
    return out
