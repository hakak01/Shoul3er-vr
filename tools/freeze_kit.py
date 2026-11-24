"""Freeze the shoulder kit (Phase E): copy the viewer, JS modules and assets into kit/<version>/ and record a
sha256 for every file in kit/<version>/FILES.json. A frozen version is never changed: this refuses to overwrite it.
  python3 -I tools/freeze_kit.py v1           make kit/v1
  python3 -I tools/freeze_kit.py v1 --check   verify kit/v1 is unchanged (exit 1 if not)
"""
import hashlib, json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ['index.html', 'demo.html', 'ATTRIBUTION.md']
DIRS = {'js': '*.js', 'assets': '*.json', 'assets/tex': '*.ktx2', 'assets/env': '*.hdr'}
GLB = ['shoulder.glb', 'gaps.glb', 'landmarks.glb']


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def listing(out):
    return {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'FILES.json'}


def check(out):
    rec = json.loads((out / 'FILES.json').read_text())['sha256']
    now = listing(out)
    bad = sorted(k for k in set(rec) | set(now) if rec.get(k) != now.get(k))
    print(f'{out.name}: {len(now)} files,', 'UNCHANGED' if not bad else f'CHANGED: {bad[:10]}')
    return not bad


def freeze(ver):
    out = ROOT / 'kit' / ver
    if out.exists():
        sys.exit(f'{out} exists: frozen versions are never changed. Use a new version name.')
    srcs = [ROOT / f for f in FILES] + [ROOT / 'assets' / g for g in GLB]
    for d, pat in DIRS.items():
        srcs += sorted((ROOT / d).glob(pat))
    for s in srcs:
        dst = out / s.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, dst)
    commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    files = listing(out)
    size = sum((out / k).stat().st_size for k in files)
    (out / 'FILES.json').write_text(json.dumps({'version': ver, 'from_commit': commit, 'three': '0.170.0',
                                                'bytes': size, 'sha256': files}, indent=1))
    print(f'kit/{ver}: {len(files)} files, {size / 1e6:.1f} MB, from commit {commit}')


if __name__ == '__main__':
    v = sys.argv[1]
    if '--check' in sys.argv:
        sys.exit(0 if check(ROOT / 'kit' / v) else 1)
    freeze(v)
