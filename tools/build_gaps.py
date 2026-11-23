"""Phase C: build the missing / partial structures of docs/GAPS.md as approximate geometry
fitted to the existing bones and tendons -> assets/gaps.glb + assets/gaps.json (approx: true).
Run from the repo root:  python3 -I tools/build_gaps.py
Needs: numpy, scipy; data/raw/hand_raw.glb (from build_assets.py); Node.js (npx) for meshopt."""
import os, sys, json, subprocess, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import numpy as np
import glbio, gapgeom as G, gaps_finger, gaps_wrist, gaps_fat
from gapgeom import MM

RAW = os.path.join(ROOT, 'data/raw/hand_raw.glb')
RAW_OUT = os.path.join(ROOT, 'data/raw/gaps_raw.glb')
OUT = os.path.join(ROOT, 'assets')
LOG = os.path.join(ROOT, 'data/raw/gaps_log.txt')
DEEP = ('fascia_retinacula', 'muscle', 'tendon_sheath', 'ligament_capsule', 'bone')


def main():
    t0 = time.time()
    log_f = open(LOG, 'w')
    log = lambda *a: (print(*a, file=log_f, flush=True), print(*a))
    D = glbio.read(RAW)
    man = json.load(open(os.path.join(OUT, 'manifest.json')))
    layer = {e['name']: e['layer'] for e in man}
    kind = {e['name']: e.get('kind') for e in man}

    def get(name, mat=None):
        ps = [(v, f) for v, f, m in D[name] if mat is None or m == mat]
        return G.merge(ps) if ps else (np.zeros((0, 3)), np.zeros((0, 3), int))

    def pts(names, mat=None, spacing=0.6 * MM):
        return np.vstack([G.sample_surface(*get(n, mat), spacing=spacing) for n in names])

    def c(name):
        return get(name)[0].mean(0)

    items, rays = gaps_finger.build(get, pts)
    log('fingers: %d items (%.0f s)' % (len(items), time.time() - t0))
    for o, R in rays.items():
        log('  %-7s joints (mm from MCP) %s, tip %.1f' % (o, np.round(R.joint_s / MM, 1).tolist(), R.tip_s / MM))
    wi, W = gaps_wrist.build(get, pts, c)
    items += wi
    log('wrist: %d items (%.0f s)' % (len(wi), time.time() - t0))
    deep = [n for n in D if layer.get(n) in DEEP and not kind.get(n)]
    deep_pts = np.vstack([pts(deep, spacing=1.0 * MM)] +
                         [G.sample_surface(*it['mesh'], spacing=1.0 * MM) for it in items])
    fi, stats = gaps_fat.build(get, lambda n: {m for _, _, m in D[n]}, [n for n in D if layer.get(n) == 'skin'], deep_pts)
    items += fi
    for k, (med, mx) in stats.items():
        log('  fat under %-36s median %.1f mm, max %.1f mm' % (k, med, mx))

    gj = []
    for it in items:
        V, F = it['mesh']
        log('%-62s %-17s tris %5d' % (it['name'], it['layer'], len(F)))
        gj.append(dict(name=it['name'], layer=it['layer'], source='Approximate model, build_gaps.py (%s)' % it['ref'],
                       approx=True, triangles=int(len(F))))
    glbio.write(RAW_OUT, [(it['name'], [(it['mesh'][0], it['mesh'][1], it['mat'])]) for it in items])
    json.dump(gj, open(os.path.join(OUT, 'gaps.json'), 'w'), indent=1)
    subprocess.run('npx -y -q @gltf-transform/cli meshopt "%s" "%s" --level medium' % (
        RAW_OUT, os.path.join(OUT, 'gaps.glb')), shell=True, check=True, stdout=subprocess.DEVNULL)
    log('items %d, triangles %d, GLB MB raw %.2f, compressed %.2f, %.0f s' % (
        len(items), sum(e['triangles'] for e in gj), os.path.getsize(RAW_OUT) / 1e6,
        os.path.getsize(os.path.join(OUT, 'gaps.glb')) / 1e6, time.time() - t0))


if __name__ == '__main__':
    main()
