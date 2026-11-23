"""Phase D1: rig (joint centres, ISB frames) + skin weights for shoulder.glb, gaps.glb and landmarks.glb.
Run AFTER build_assets.py, build_landmarks.py and build_gaps.py (they write the unskinned raw files):
  python3 -I tools/build_rig.py      (~1 min; needs numpy, scipy, Node.js npx for meshopt)
Writes assets/rig.json and re-writes assets/shoulder.glb, gaps.glb, landmarks.glb with a 6-bone skin."""
import os, sys, json, subprocess, time
import numpy as np
from scipy.spatial import cKDTree
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import glbio, gapgeom as G, rig_frames, glbskin, rig_weights as RW
from gapgeom import MM

RAW, OUT = os.path.join(ROOT, 'data/raw'), os.path.join(ROOT, 'assets')
FILES = [('shoulder_raw.glb', 'shoulder.glb', 'manifest.json'), ('gaps_raw.glb', 'gaps.glb', 'gaps.json'),
         ('landmarks_raw.glb', 'landmarks.glb', 'landmarks.json')]
LOG = open(os.path.join(RAW, 'rig_log.txt'), 'w')


def log(*a):
    s = ' '.join(str(x) for x in a); print(s); LOG.write(s + '\n'); LOG.flush()


def strip(n):
    return n[:-4] if len(n) > 4 and n[-4] == '.' and n[-3:].isdigit() else n


def main():
    t0 = time.time()
    data = {f: glbio.read(os.path.join(RAW, f)) for f, _, _ in FILES}
    man = {}
    for _, _, m in FILES: man.update({e['name']: e for e in json.load(open(os.path.join(OUT, m)))})
    S = {strip(k): v for k, v in data['shoulder_raw.glb'].items()}
    get = lambda n, m=None: G.merge([(v, f) for v, f, mm in S[n] if m is None or mm == m])
    rig = rig_frames.build(get, log)
    J = {k: np.array(v) for k, v in rig['joints'].items()}; ant = np.array(rig['frames']['thorax'])[:, 0]
    bones = {b: [] for b in range(len(RW.BONES))}
    for k, ps in S.items():
        L = man.get(k, {}).get('layer')
        if k in RW.MAIN: bones[RW.MAIN[k]] += [(v, f) for v, f, _ in ps]
        elif k == 'Glenoid labrum': bones[2] += [(v, f) for v, f, _ in ps]   # IGHL etc. attach via the labrum
        elif L == 'context_bone': bones[0] += [(v, f) for v, f, _ in ps]
    field = RW.Field(bones)
    feet = []
    for k, ps in S.items():
        base, kind = RW.footprint_key(k)
        if base: feet.append((base, kind, np.vstack([v for v, _, _ in ps])))
    muscles, ligs, dom, weights, stats = {}, {}, {}, {f: {} for f, _, _ in FILES}, {}
    for f, _, _ in FILES:
        groups = {}                                   # skin / fat / fascia pieces: weighted together (no seams)
        for node in data[f]:
            L = man.get(strip(node), {}).get('layer')
            if L in ('skin', 'fat', 'fascia_retinacula'): groups.setdefault(L, []).append(node)
        for L, nodes in groups.items():
            U, maps, A = RW.weld([(v, fc) for n in nodes for v, fc, _ in data[f][n]])
            W = RW.smooth(RW.soft(field, U), A, 8); k = 0
            for n in nodes:
                weights[f][n] = [W[maps[k + i]] for i in range(len(data[f][n]))]; k += len(data[f][n])
                dom[strip(n)] = RW.BONES[int(np.vstack(weights[f][n]).sum(0).argmax())]
            stats['soft'] = stats.get('soft', 0) + len(nodes)
        for node, ps in data[f].items():
            name = strip(node); e = man.get(name)
            if not e: log('  not in manifest:', node); continue
            if node in weights[f]: continue
            L = e['layer']; U, maps, A = RW.weld([(v, fc) for v, fc, _ in ps]); kind = 'soft'
            if name in RW.MAIN: W = RW.rigid(len(U), RW.MAIN[name]); kind = 'rigid'
            elif L == 'context_bone': W = RW.rigid(len(U), 0); kind = 'rigid'
            elif name in RW.RIGID: W = RW.rigid(len(U), RW.RIGID[name]); kind = 'rigid'
            elif L == 'attachment':
                b, _ = field.nearest(U); W = RW.rigid(len(U), int(np.bincount(b).argmax())); kind = 'rigid'
            elif L == 'muscle':
                tu = cKDTree(U); near = lambda P: P[tu.query(P)[0] < 4 * MM]
                P = np.vstack([near(P) for b, k, P in feet if RW.group_match(b, name)] or [np.zeros((0, 3))])
                W, line = RW.muscle(field, U, P, J, A, name); kind = 'muscle'
                if line: muscles[name] = dict(a=line[0].round(5).tolist(), ba=RW.BONES[line[1]],
                                              b=line[2].round(5).tolist(), bb=RW.BONES[line[3]])
            elif L in ('ligament_capsule', 'bursa', 'tendon_sheath'):
                W, pair = RW.contact(field, U, name); kind = 'contact'
                if pair and L == 'ligament_capsule':
                    n = 8 if 'capsule of glenohumeral' in name or 'capsule of elbow' in name else 1
                    fb = RW.fibres(U, W, pair, ant, n)
                    if fb: ligs[name] = fb
            else:
                W = RW.smooth(RW.soft(field, U), A, 8)
            weights[f][node] = [W[m] for m in maps]
            tot = W.sum(0); dom[name] = RW.BONES[int(tot.argmax())]
            stats[kind] = stats.get(kind, 0) + 1
    log('structures by weighting rule:', stats, '| muscle lines', len(muscles), '| ligaments with tension', len(ligs))
    for nm in ['Long head of biceps brachii', 'Short head of biceps brachii', 'Long head of triceps brachii',
               'Supraspinatus muscle', 'Acromial part of deltoid muscle']:
        if nm in muscles: log('  %s: %s -> %s' % (nm, muscles[nm]['ba'], muscles[nm]['bb']))
    heads = [J[b] for b in RW.BONES]
    for f, out, _ in FILES:
        tmp = os.path.join(RAW, f.replace('_raw', '_skin'))
        glbskin.add_skin(os.path.join(RAW, f), tmp, RW.BONES, RW.PARENT, heads, weights[f])
        subprocess.run('npx -y -q @gltf-transform/cli meshopt "%s" "%s" --level medium --quantization-volume scene' % (tmp, os.path.join(OUT, out)),
                       shell=True, check=True, stdout=subprocess.DEVNULL)
        log('  %s %.2f MB' % (out, os.path.getsize(os.path.join(OUT, out)) / 1e6))
    rig.update(bones=RW.BONES, parents=RW.PARENT, muscles=muscles, ligaments=ligs, dominant=dom, approx=True)
    json.dump(rig, open(os.path.join(OUT, 'rig.json'), 'w'), separators=(',', ':'))
    log('rig.json %.0f kB; done in %.0f s' % (os.path.getsize(os.path.join(OUT, 'rig.json')) / 1e3, time.time() - t0))


if __name__ == '__main__':
    main()
