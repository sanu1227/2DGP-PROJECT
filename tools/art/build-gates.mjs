/** Normalize paired gate sprites with one shared transform; no runtime Node dependency. */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../assets/gate_pack_v1');
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const size = 512;
const manifest = { sources: {}, atlases: {}, sprites: {} };
const composites = [];
await fs.mkdir(path.join(root, 'sprites'), { recursive: true });
for (const [index, name] of ['gate_closed', 'gate_open'].entries()) {
  const source = await fs.readFile(path.join(root, 'sources', `${name}.png`));
  const meta = await sharp(source).metadata();
  if (meta.width !== 1254 || meta.height !== 1254 || !meta.hasAlpha)
    throw new Error(`${name}: expected paired 1254 x 1254 RGBA sources`);
  // Shared full-canvas transform preserves the jambs across open/closed states.
  // Foot-centre reference: (50%, 78.9%). Projected post spacing follows 2:1 axes.
  const normalized = await sharp(source).resize(256, 360, { fit: 'fill' }).toBuffer();
  const png = await sharp({ create: { width: size, height: size, channels: 4, background: '#00000000' } })
    .composite([{ input: normalized, left: 128, top: 100 }]).png().toBuffer();
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  let left = size, top = size, right = 0, bottom = 0, transparent = 0;
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    if (data[(y * size + x) * info.channels + 3] < 16) { transparent++; continue; }
    left = Math.min(left, x); right = Math.max(right, x);
    top = Math.min(top, y); bottom = Math.max(bottom, y);
  }
  if (!transparent || left <= 0 || top <= 0 || right >= size - 1 || bottom >= size - 1)
    throw new Error(`${name}: missing transparency or clipped content`);
  await fs.writeFile(path.join(root, 'sprites', `${name}.png`), png);
  manifest.sources[name] = { file: `sources/${name}.png`, width: meta.width, height: meta.height, sha256: hash(source) };
  manifest.sprites[name] = { file: `sprites/${name}.png`, width: size, height: size,
    anchor: { x: 256, y: 384 }, atlas: 'gates',
    clip_rect_pico2d: [index * size, 0, size, size],
    content_rect: { left, top, width: right - left + 1, height: bottom - top + 1 }, sha256: hash(png) };
  composites.push({ input: png, left: index * size, top: 0 });
}
const atlas = await sharp({ create: { width: size * 4, height: size, channels: 4, background: '#00000000' } })
  .composite(composites).png().toBuffer();
await fs.writeFile(path.join(root, 'atlas.png'), atlas);
manifest.atlases.gates = { file: 'atlas.png', width: size * 4, height: size,
  cell_size: size, grid: [4, 1], sha256: hash(atlas) };
await fs.writeFile(path.join(root, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
console.log('Gate pack: 2 aligned sprites, 1 atlas; shared footprint, alpha and margins verified.');
