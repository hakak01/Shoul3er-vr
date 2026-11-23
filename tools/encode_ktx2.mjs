// Encode data/raw/tex/*.rgba (1024x1024 RGBA) -> assets/tex/*.ktx2 (UASTC + Zstd, mipmaps, linear).
// Needs the encoder once:  cd data/raw/enc && npm init -y && npm install ktx2-encoder
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..');
const enc = pathToFileURL(path.join(root, 'data/raw/enc/node_modules/ktx2-encoder/dist/node/index.js')).href;
const { encodeToKTX2 } = await import(enc);
const N = 1024, src = path.join(root, 'data/raw/tex'), dst = path.join(root, 'assets/tex');
fs.mkdirSync(dst, { recursive: true });
const only = process.argv.slice(2);
for (const f of fs.readdirSync(src).filter((f) => f.endsWith('.rgba'))) {
  const name = f.slice(0, -5);
  if (only.length && !only.includes(name)) continue;
  const raw = fs.readFileSync(path.join(src, f));
  const out = await encodeToKTX2(raw, {
    imageDecoder: async () => ({ width: N, height: N, data: new Uint8Array(raw) }),
    isUASTC: true, isNormalMap: false, isSetKTX2SRGBTransferFunc: false, generateMipmap: true,
    needSupercompression: true, enableRDO: true, rdoQualityLevel: 2.0, qualityLevel: 230,
  });
  fs.writeFileSync(path.join(dst, name + '.ktx2'), out);
  console.log(name.padEnd(10), (out.length / 1024).toFixed(0), 'KB');
}
