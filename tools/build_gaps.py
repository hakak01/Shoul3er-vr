"""Phase C: build the missing structures of docs/GAPS.md as approximate geometry fitted to the
existing bones, capsule, tendons, nerves and vessels -> assets/gaps.glb + assets/gaps.json (approx: true).
Run from the repo root:  python3 -I tools/build_gaps.py   (~1 min)
Needs: numpy, scipy; data/raw/shoulder_raw.glb (from build_assets.py); Node.js (npx) for meshopt."""
import os, sys, json, subprocess, time
from types import SimpleNamespace
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import numpy as np
import glbio, gapgeom as G, gaps_joint, gaps_nv, gaps_fat
from gapgeom import MM

RAW = os.path.join(ROOT, 'data/raw/shoulder_raw.glb')
RAW_OUT = os.path.join(ROOT, 'data/raw/gaps_raw.glb')
OUT = os.path.join(ROOT, 'assets')
LOG = os.path.join(ROOT, 'data/raw/gaps_log.txt')
DEEP = ('fascia_retinacula', 'muscle', 'tendon_sheath', 'ligament_capsule', 'bone', 'context_bone')


def context():
    D = glbio.read(RAW)
    man = json.load(open(os.path.join(OUT, 'manifest.json')))
    model = json.load(open(os.path.join(OUT, 'model.json')))

    def get(name, mat=None, exclude=None):
        ps = [(v, f) for v, f, m in D[name] if (mat is None or m == mat) and m != exclude]
        return G.merge(ps) if ps else (np.zeros((0, 3)), np.zeros((0, 3), int))

    def pts(names, mat=None, spacing=0.6 * MM):
        return np.vstack([G.sample_surface(*get(n, mat), spacing=spacing) for n in names])
    layer = {e['name']: e['layer'] for e in man}
    return SimpleNamespace(D=D, get=get, pts=pts, C=np.array(model['center']), R=0.0224, layer=layer,
                           kind={e['name']: e.get('kind') for e in man})


def main(only=None):
    t0 = time.time()
    log_f = open(LOG, 'w')
    log = lambda *a: (print(*a, file=log_f, flush=True), print(*a))
    K = context()
    items = gaps_joint.build(K, log)
    log('joint: %d items (%.0f s)' % (len(items), time.time() - t0))
    ni = gaps_nv.build(K, log)
    items += ni
    log('nerves and vessels: %d items (%.0f s)' % (len(ni), time.time() - t0))
    if only != 'nofat':
        deep = [n for n in K.D if K.layer.get(n) in DEEP and not K.kind.get(n)]
        deep_pts = np.vstack([K.pts(deep, spacing=1.0 * MM)] +
                             [G.sample_surface(*it['mesh'], spacing=1.0 * MM) for it in items if it['layer'] != 'nerve'
                              and it['layer'] not in ('artery', 'vein')])
        fi, stats = gaps_fat.build(K.get, lambda n: {m for _, _, m in K.D[n]},
                                   [n for n in K.D if K.layer.get(n) == 'skin'], deep_pts)
        items += fi
        for k, (med, mx) in stats.items():
            log('  fat under %-36s median %.1f mm, max %.1f mm' % (k, med, mx))
    gj = []
    for it in items:
        V, F = it['mesh']
        log('%-58s %-17s tris %6d' % (it['name'], it['layer'], len(F)))
        e = dict(name=it['name'], layer=it['layer'], source='Approximate model, build_gaps.py (%s)' % it['ref'],
                 approx=True, triangles=int(len(F)))
        if it.get('replaces'):
            e['replaces'] = it['replaces']
        gj.append(e)
    glbio.write(RAW_OUT, [(it['name'], [(it['mesh'][0], it['mesh'][1], it['mat'])]) for it in items])
    json.dump(gj, open(os.path.join(OUT, 'gaps.json'), 'w'), indent=1)
    subprocess.run('npx -y -q @gltf-transform/cli meshopt "%s" "%s" --level medium' % (
        RAW_OUT, os.path.join(OUT, 'gaps.glb')), shell=True, check=True, stdout=subprocess.DEVNULL)
    log('items %d, triangles %d, GLB MB raw %.2f, compressed %.2f, %.0f s' % (
        len(items), sum(e['triangles'] for e in gj), os.path.getsize(RAW_OUT) / 1e6,
        os.path.getsize(os.path.join(OUT, 'gaps.glb')) / 1e6, time.time() - t0))


if __name__ == '__main__':
    main(*sys.argv[1:])
