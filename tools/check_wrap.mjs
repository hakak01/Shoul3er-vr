// Phase D2 headless browser test (not part of the site). Needs Playwright and a local three@0.170.0 copy (the CDN is
// blocked in the cloud session). Serve the repo:  python3 -m http.server 8765 --bind 127.0.0.1
// Run:  node tools/check_wrap.mjs <dir with node_modules/three> <output dir>   then  python3 -I tools/check_wrap.py <output dir>/js_dump.json
// Prints per pose: corrective weights, scapula contact (deg), rope NaN check, nerve stretch %, rest drift.
import { createRequire } from 'module'; const { chromium } = createRequire(import.meta.url)('playwright');
import fs from 'fs';
const S = process.argv[2], OUT = process.argv[3], url = 'http://127.0.0.1:8765/index.html';
const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const p = await b.newPage({ viewport: { width: 1000, height: 700 } });
const errs = [];
p.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errs.push(m.type() + ': ' + m.text().slice(0, 200)); });
p.on('pageerror', (e) => errs.push('pageerror: ' + e.message.slice(0, 300)));
await p.route('https://cdn.jsdelivr.net/npm/three@0.170.0/**', (r) => {
  const f = S + '/node_modules/three/' + r.request().url().split('three@0.170.0/')[1];
  r.fulfill({ body: fs.readFileSync(f), contentType: f.endsWith('.js') ? 'text/javascript' : 'application/octet-stream' });
});
await p.goto(url);
try { await p.waitForFunction(() => window.app && app.rig && app.realism && app.realism.view === 'realistic', null, { timeout: 120000 }); } catch (e) { console.log('LOAD FAILED', errs.join('\n')); process.exit(1); }
const POSES = { rest: null, abd90: { plane: 0, elev: 90, rot: 0 }, fullElev: { plane: 30, elev: 170, rot: 0 }, ER: { elev: 0, rot: 90 },
  IR: { elev: 0, rot: -80 }, ABER: { plane: 0, elev: 90, rot: 90 }, crossBody: { plane: 135, elev: 90, rot: 0 } };
const DUMP = ['Clavicular part of deltoid muscle', 'Subscapularis muscle', 'Supraspinatus muscle', 'Serratus anterior muscle', 'Deltoid region'];
const NERVES = ['Axillary nerve', 'Suprascapular nerve', 'Musculocutaneous nerve', 'Radial nerve', 'Ulnar nerve', 'Median nerve',
  'Lateral cord of brachial plexus', 'Medial cord of brachial plexus', 'Posterior cord of brachial plexus', 'Roots of brachial plexus',
  'Axillary artery', 'Axillary vein', 'Cephalic vein'];
const dump = {};
for (const [nm, pose] of Object.entries(POSES)) {
  const r = await p.evaluate(({ pose, DUMP, NERVES, nm }) => {
    const R = app.rig, A = app.anatomy, T = R.wrap; R.set(pose || R.home); R.update(); while (R.ropes.left > 0) R.ropes.step(30);
    const s1 = NERVES.map((n) => R.ropes.stretch(n).whole); R.ropes.left = 300; while (R.ropes.left > 0) R.ropes.step(30);
    const conv = Math.max(...NERVES.map((n, i) => Math.abs(R.ropes.stretch(n).whole - s1[i]))) * 100;
    const sc = R.scene, v = new (sc.position.constructor)(), out = {}, bad = [];
    for (const n of DUMP) { const s = A.byName.get(n); if (!s) continue; const pts = [];
      for (const m of s.meshes) { const P = m.geometry.attributes.position;
        for (let i = 0; i < P.count; i += 7) { m.getVertexPosition(i, v); v.applyMatrix4(m.matrixWorld); sc.worldToLocal(v); pts.push([v.x, v.y, v.z]); } }
      out[n] = pts; }
    let maxJump = 0;                                  // rope tube vertices vs their particle (exploding check)
    for (const B of R.ropes.meshes) { const P = B.m.geometry.attributes.position;
      for (let i = 0; i < P.count; i++) { v.fromBufferAttribute(P, i); if (!isFinite(v.x)) bad.push(B.m.name);
        v.applyMatrix4(B.m.matrixWorld); sc.worldToLocal(v); maxJump = Math.max(maxJump, v.distanceTo(R.ropes.x[B.a[i]])); } }
    const st = {}; for (const n of NERVES) { const q = R.ropes.stretch(n); if (q) st[n] = [+(100 * q.whole).toFixed(1), +(100 * q.part).toFixed(1)]; }
    const ax = A.byName.get('Axillary nerve'); let axAcr = null;
    if (ax) { const AA = new (sc.position.constructor)(...R.rig.landmarks.AA).applyMatrix4(R.D.scapula); axAcr = 1e9;
      for (const i of R.ropes.d.s.map((s, i) => [s, i]).filter(([s]) => R.ropes.d.names[s] === 'Axillary nerve').map(([, i]) => i))
        axAcr = Math.min(axAcr, R.ropes.x[i].distanceTo(AA)); }
    return { out, w: T.w.map((x) => +x.toFixed(2)), extra: +T.extra.toFixed(1), maxJumpMM: +(maxJump * 1000).toFixed(1), bad: [...new Set(bad)],
      st, axAcrMM: axAcr && +(axAcr * 1000).toFixed(1), morphs: T.morphs.length, conv: +conv.toFixed(2) };
  }, { pose, DUMP, NERVES, nm });
  dump[nm] = r.out;
  console.log(nm, JSON.stringify({ w: r.w, contact: r.extra, ropeVertMaxFromParticleMM: r.maxJumpMM, NaN: r.bad, morphMeshes: r.morphs, changeAfter300morePassesPct: r.conv }));
  console.log('   stretch % [whole, most stretched part]:', JSON.stringify(r.st));
  if (nm === 'abd90' || nm === 'fullElev') {
    await p.evaluate(() => { app.resetView(); }); await p.waitForTimeout(300);
    await p.screenshot({ path: OUT + '/shot_' + nm + '.png' });
  }
}
fs.writeFileSync(OUT + '/js_dump.json', JSON.stringify(dump));
console.log('rest drift', await p.evaluate(() => { const R = app.rig; R.set(R.home); R.update(); const o = [];
  R.ropes.x.forEach((x, i) => { const d = x.distanceTo(R.ropes.x0[i]); if (d > 1e-4) o.push([R.ropes.d.names[R.ropes.d.s[i]].slice(0, 20), i, R.ropes.pin[i], +(d * 1000).toFixed(2)]); });
  return JSON.stringify(o.slice(0, 12)) + ' n=' + o.length; }));
const mem = await p.evaluate(() => { let n = 0; app.rig.wrap.morphs.forEach(({ m }) => { n += m.geometry.attributes.position.count; }); return n; });
console.log('morph vertices', mem, '-> GPU ~', (mem * 6 * 16 / 1e6).toFixed(1), 'MB; fps (swiftshader)', await p.evaluate(() => app.fps));
console.log('errors:', errs.length ? errs.join('\n') : 'none');
await b.close();
