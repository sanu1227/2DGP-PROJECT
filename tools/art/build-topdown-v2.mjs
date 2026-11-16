import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = fileURLToPath(new URL('../../assets/topdown_v2/', import.meta.url));
const tile = 256;
const sheets = {
  terrain: ['floor', 'wall'].flatMap(kind =>
    Array.from({ length: 8 }, (_, index) => `${kind}_${index + 1}`)),
  devices: [
    'trap_broken', 'trap_installed', 'trap_active', 'exit_closed',
    'exit_ready', 'lever_off', 'lever_on', 'bench_empty',
    'bench_bone', 'plate_up', 'plate_down', 'gate_closed',
    'gate_open', 'post_empty', 'soldier_deployed', 'rubble',
  ],
  objects: [
    'part', 'bone', 'soldier_carried', 'chute_inlet',
    'chute_outlet', 'source', 'mirror_base', 'receiver',
    'winch', 'helper', 'anvil', 'urn',
    'books', 'pipe', 'treasure', 'throne',
  ],
  worker: ['down', 'left', 'up', 'right'].flatMap(direction =>
    ['idle', 'walk_a', 'walk_b', 'carry'].map(pose => `worker_${direction}_${pose}`)),
  decor: [
    'sarcophagus', 'candles', 'hand_pump', 'elbow_pipe',
    'water_barrel', 'treasure_banner', 'brazier', 'lantern',
    'tool_rack', 'candle_sconce', 'crypt_banner', 'crest',
    'crystal_sconce', 'archive_banner', 'wall_pipes', 'air_vent',
  ],
};

function cleanAlpha(data, width, height) {
  const marked = new Uint8Array(width * height);
  const queue = new Int32Array(width * height);
  for (let start = 0; start < marked.length; start += 1) {
    if (marked[start] || data[start * 4 + 3] < 16) continue;
    let end = 1;
    queue[0] = start;
    marked[start] = 1;
    for (let head = 0; head < end; head += 1) {
      const index = queue[head];
      const x = index % width;
      const adjacent = [
        x > 0 ? index - 1 : -1,
        x + 1 < width ? index + 1 : -1,
        index - width,
        index + width,
      ];
      for (const next of adjacent) {
        if (next >= 0 && next < marked.length && !marked[next] && data[next * 4 + 3] >= 16) {
          marked[next] = 1;
          queue[end] = next;
          end += 1;
        }
      }
    }
    if (end < 45) {
      for (let head = 0; head < end; head += 1) data[queue[head] * 4 + 3] = 0;
    }
  }

  let left = width;
  let right = 0;
  let top = height;
  let bottom = 0;
  for (let index = 0; index < marked.length; index += 1) {
    const alpha = index * 4 + 3;
    if (data[alpha] < 16) {
      data[alpha] = 0;
      continue;
    }
    const x = index % width;
    const y = Math.floor(index / width);
    left = Math.min(left, x);
    right = Math.max(right, x);
    top = Math.min(top, y);
    bottom = Math.max(bottom, y);
  }
  if (right - left < 36 || bottom - top < 36) throw new Error('Source slot is empty or clipped.');
  if (left === 0 || top === 0 || right === width - 1 || bottom === height - 1) {
    throw new Error('Source slot touches a neighboring slot.');
  }
  return { left, top, width: right - left + 1, height: bottom - top + 1 };
}

async function packSheet(name, names, manifest) {
  const sourcePath = path.join(root, 'source', `${name}.png`);
  const source = sharp(sourcePath);
  const { width, height } = await source.metadata();
  const layers = [];
  for (const [index, key] of names.entries()) {
    const col = index % 4;
    const row = Math.floor(index / 4);
    const left = Math.floor(col * width / 4);
    const top = Math.floor(row * height / 4);
    const cell = { left, top, width: Math.floor((col + 1) * width / 4) - left,
      height: Math.floor((row + 1) * height / 4) - top };
    const { data, info } = await source.clone().extract(cell).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const bounds = cleanAlpha(data, info.width, info.height);
    const terrain = name === 'terrain';
    if (terrain) {
      bounds.left += 8;
      bounds.top += 8;
      bounds.width -= 16;
      bounds.height -= 16;
    }
    const { data: image, info: sprite } = await sharp(data, { raw: info })
      .extract(bounds).resize(terrain ? tile : tile - 8, terrain ? tile : tile - 8,
        { fit: terrain ? 'fill' : 'inside' })
      .png().toBuffer({ resolveWithObject: true });
    const input = terrain ? await sharp(image).flatten({ background: '#22282c' }).png().toBuffer() : image;
    const x = col * tile + Math.floor((tile - sprite.width) / 2);
    const y = row * tile + Math.floor((tile - sprite.height) / 2);
    layers.push({ input, left: x, top: y });
    manifest.sprites[key] = [name, x, y, sprite.width, sprite.height];
  }
  const relative = `atlases/${name}.png`;
  await sharp({ create: { width: tile * 4, height: tile * 4, channels: 4, background: '#00000000' } })
    .composite(layers).png().toFile(path.join(root, relative));
  manifest.atlases[name] = relative;
}

await mkdir(path.join(root, 'atlases'), { recursive: true });
const manifest = { atlases: {}, sprites: {} };
for (const [name, sprites] of Object.entries(sheets)) await packSheet(name, sprites, manifest);
await writeFile(path.join(root, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
console.log(`${Object.keys(manifest.sprites).length} sprites packed into ${Object.keys(sheets).length} atlases.`);
