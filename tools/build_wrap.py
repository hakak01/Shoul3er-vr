"""Phase D2: wrapping (corrective morph targets at 6 poses), scapula-thorax contact and nerve/vessel ropes.
Run AFTER build_rig.py (it reads data/raw/*_skin.glb):  python3 -I tools/build_wrap.py   (~3 min)
Writes assets/wrap.json and re-writes assets/shoulder.glb and gaps.glb with morph targets."""
import os, sys, json, subprocess, time
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import glbio, glbskin, rig_pose as RP, rig_weights as RW, wrap_fit as WF, wrap_morph as WM, wrap_rope as WR

RAW, OUT = os.path.join(ROOT, 'data/raw'), os.path.join(ROOT, 'assets')
FILES = [('shoulder_skin.glb', 'shoulder.glb'), ('gaps_skin.glb', 'gaps.glb')]
MORPH_LAYERS = ('muscle', 'skin', 'fat', 'fascia_retinacula', 'bursa')
LOG = open(os.path.join(RAW, 'wrap_log.txt'), 'w')


def log(*a):
    s = ' '.join(str(x) for x in a); print(s); LOG.write(s + '\n'); LOG.flush()


def strip(n):
    return n[:-4] if len(n) > 4 and n[-4] == '.' and n[-3:].isdigit() else n


def load():
    rig, rh = json.load(open(os.path.join(OUT, 'rig.json'))), json.load(open(os.path.join(OUT, 'rhythm.json')))
    man = {}
    for m in ('manifest.json', 'gaps.json'): man.update({e['name']: e for e in json.load(open(os.path.join(OUT, m)))})
    data = {f: RP.read_skinned(os.path.join(RAW, f))[2] for f, _ in FILES}
    return rig, rh, man, data


def bones_of(data, man):
    S = data['shoulder_skin.glb']; parts = {b: [] for b in range(6)}
    for k, ps in S.items():
        n = strip(k)
        if n in RW.MAIN: parts[RW.MAIN[n]] += [(p['v'], p['f']) for p in ps]
        elif man.get(n, {}).get('layer') == 'context_bone': parts[0] += [(p['v'], p['f']) for p in ps]
    ribs = np.vstack([p['v'] for k, ps in S.items() if man.get(strip(k), {}).get('layer') == 'context_bone'
                      and 'rib' in k.lower() for p in ps])
    return parts, ribs


def main():
    t0 = time.time(); rig, rh, man, data = load()
    parts, ribs = bones_of(data, man); Bones = {b: WF.Bone(ps) for b, ps in parts.items()}
    scap = np.vstack([v for v, _ in parts[2]])
    thorax, region = WF.thorax(RP.Pose(rig, rh), ribs, scap, Bones[0], log)
    wrap = dict(thorax=thorax, approx=True); P = RP.Pose(rig, rh, wrap)
    for nm, p in [('abd90', dict(plane=0, elev=90)), ('scaption 150', dict(plane=40, elev=150)), ('full', dict(plane=30, elev=170))]:
        P.deltas(p); log('  scapula contact at %s: extra %.1f deg about AC' % (nm, WM.angle(np.eye(3), P.extra)))
    # corrective shapes
    rope_set = set(WR.ROPES); items = []
    for f, _ in FILES:
        for node, ps in data[f].items():
            if man.get(strip(node), {}).get('layer') in MORPH_LAYERS and strip(node) not in rope_set: items.append(((f, node), ps, man[strip(node)]['layer'] == 'muscle'))
    G = WM.Group(items); C = WM.Corrector(P, G, thorax, region, Bones, log)
    log('corrective input: %d structures, %d vertices (%d closed muscles)' % (len(items), len(G.U), sum(G.closed)))
    deltas = []
    for nm, p in WM.POSES:
        d, st = C.pose(p); deltas.append(d); log('  pose %-9s pushed %6d vertices, largest correction %.1f mm (%.0f s)' % (nm, st['pushed'], st['max_mm'], time.time() - t0))
    targets = {f: {} for f, _ in FILES}; nv = 0
    for si, ((f, node), ps, _) in enumerate(items):
        m = G.own == si
        if max(np.abs(d[m]).max() for d in deltas) < 0.05 * WM.MM: continue
        targets[f][node] = [[d[mp] for d in deltas] for mp in G.maps[si]]; nv += sum(len(p['v']) for p in ps)
    log('morph targets on %d meshes, %d vertices -> GPU %.1f MB (positions, 6 targets x 16 B)' %
        (sum(len(t) for t in targets.values()), nv, nv * 6 * 16 / 1e6))
    # ropes
    rope_S = {}
    for f, _ in FILES:
        for node, ps in data[f].items():
            if strip(node) in rope_set: rope_S[strip(node)] = ps
    colliders, tip = WF.colliders(rig, {n: np.vstack([v for v, _ in parts[b]]) for n, b in RW.MAIN.items()}, log)
    lm = glbio.read(os.path.join(RAW, 'landmarks_raw.glb')); qs = [k for k in lm if k.startswith('Quadrangular space')]
    qs = np.vstack([v for v, _, _ in lm[qs[0]]]).mean(0) if qs else None
    ropes = WR.build(rope_S, Bones, rig['bones'], colliders, thorax, tip, qs, log)
    wrap.update(poses=[dict(name=n, **p) for n, p in WM.POSES], blend=WM.blend_params(P),
                ropes=ropes)
    json.dump(wrap, open(os.path.join(OUT, 'wrap.json'), 'w'), separators=(',', ':'))
    np.savez_compressed(os.path.join(RAW, 'wrap_deltas.npz'), **{'d%d' % i: d for i, d in enumerate(deltas)})
    names = [n for n, _ in WM.POSES]
    for f, out in FILES:
        tmp = os.path.join(RAW, f.replace('_skin', '_morph'))
        glbskin.add_targets(os.path.join(RAW, f), tmp, names, targets[f])
        subprocess.run('npx -y -q @gltf-transform/cli meshopt "%s" "%s" --level medium --quantization-volume scene' % (tmp, os.path.join(OUT, out)),
                       shell=True, check=True, stdout=subprocess.DEVNULL)
        log('  %s %.2f MB' % (out, os.path.getsize(os.path.join(OUT, out)) / 1e6))
    log('wrap.json %.0f kB; done in %.0f s' % (os.path.getsize(os.path.join(OUT, 'wrap.json')) / 1e3, time.time() - t0))


if __name__ == '__main__':
    main()
