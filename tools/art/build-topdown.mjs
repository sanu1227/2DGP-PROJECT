/** Normalize generated 4x4 sheets without changing the preserved source art. */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const root = path.join(project, 'assets/topdown_v1');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const manifest = {version: 1, created: '2026-11-09', generator: 'image_gen.imagegen',
  projection: 'front-facing orthographic 3/4 top-down; horizontal X; ground depth 0.65',
  coordinates: {tile_footprint: {width: 224, height: 146}}, atlases: {}, sprites: {}, sources: {}};
const validation = {sprite_count: 0, transparent_outputs: true, clipped_outputs: 0, source_edges: []};
await fs.mkdir(path.join(root, 'sprites'), {recursive: true});
await fs.mkdir(path.join(root, 'atlases'), {recursive: true});

function bounds(data, width, height) {
  let left = width, top = height, right = -1, bottom = -1, edge = 0;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const a = data[(y * width + x) * 4 + 3];
    if (a <= 16) {data[(y * width + x) * 4 + 3] = 0; continue;}
    if (a < 48) continue;
    left = Math.min(left, x); top = Math.min(top, y);
    right = Math.max(right, x); bottom = Math.max(bottom, y);
    if (!x || !y || x === width - 1 || y === height - 1) edge++;
  }
  if (right < left) throw new Error('Empty source cell');
  return {left, top, width: right - left + 1, height: bottom - top + 1, edge};
}

for (const group of ['terrain', 'devices', 'worker', 'props']) {
  const spec = JSON.parse(await fs.readFile(path.join(root, 'source', `${group}.json`), 'utf8'));
  const original = await fs.readFile(path.join(root, 'source', `${group}.png`));
  const metadata = await sharp(original).metadata();
  if (!metadata.hasAlpha || spec.entries.length !== 16) throw new Error(`${group}: alpha and 16 entries required`);
  // 생성된 시트의 실제 투명 여백을 찾아 인접 행의 소품을 잘라내지 않는다.
  const whole = await sharp(original).ensureAlpha().raw().toBuffer();
  const cuts = axis => {
    const length = axis === 'x' ? metadata.width : metadata.height;
    const other = axis === 'x' ? metadata.height : metadata.width;
    const result = [0];
    for (let boundary = 1; boundary < 4; boundary++) {
      const expected = Math.round(length * boundary / 4);
      let best = expected, score = Infinity;
      for (let candidate = expected - Math.round(length / 32); candidate <= expected + Math.round(length / 32); candidate++) {
        let count = 0;
        for (let j = 0; j < other; j++) {
          const pixel = axis === 'x' ? j * metadata.width + candidate : candidate * metadata.width + j;
          count += whole[pixel * 4 + 3] >= 48;
        }
        if (count < score || (count === score && Math.abs(candidate - expected) < Math.abs(best - expected))) {
          best = candidate; score = count;
        }
      }
      result.push(best);
    }
    result.push(length);
    return result;
  };
  const columns = cuts('x'), rows = cuts('y');
  const cells = [];
  for (let i = 0; i < 16; i++) {
    const col = i % 4, row = Math.floor(i / 4);
    const left = columns[col], top = rows[row];
    const sourceRect = {left, top, width: columns[col + 1] - left, height: rows[row + 1] - top};
    const {data, info} = await sharp(original).extract(sourceRect).ensureAlpha().raw().toBuffer({resolveWithObject: true});
    const box = bounds(data, info.width, info.height);
    if (box.edge) validation.source_edges.push({group, id: spec.entries[i], pixels: box.edge});
    cells.push({id: `td_${spec.entries[i]}`, data, info, box, sourceRect, col, row});
  }
  const workerScale = Math.min(208 / Math.max(...cells.map(c => c.box.height)),
                               208 / Math.max(...cells.map(c => c.box.width)));
  const overlays = [];
  const atlas = `topdown_${group}`;
  manifest.sources[group] = {file: `source/${group}.png`, width: metadata.width, height: metadata.height, sha256: hash(original)};
  for (const cell of cells) {
    let width, height, top, anchor;
    if (group === 'terrain') {
      width = 224; height = cell.id.endsWith('_face') ? 112 : 146;
      top = Math.round(160 - height / 2); anchor = {x: 128, y: 160};
    } else {
      const scale = group === 'worker' ? workerScale : Math.min(208 / cell.box.width, 208 / cell.box.height);
      width = Math.round(cell.box.width * scale); height = Math.round(cell.box.height * scale);
      top = 232 - height; anchor = {x: 128, y: 232};
    }
    const left = Math.round((256 - width) / 2);
    const content = await sharp(cell.data, {raw: {width: cell.info.width, height: cell.info.height, channels: 4}})
      .extract({left: cell.box.left, top: cell.box.top, width: cell.box.width, height: cell.box.height})
      .resize(width, height, {fit: 'fill'}).png().toBuffer();
    const png = await sharp({create: {width: 256, height: 256, channels: 4, background: '#00000000'}})
      .composite([{input: content, left, top}]).png().toBuffer();
    if (left < 8 || top < 8 || left + width > 248 || top + height > 248) throw new Error(`${cell.id}: output clips`);
    await fs.writeFile(path.join(root, 'sprites', `${cell.id}.png`), png);
    manifest.sprites[cell.id] = {file: `sprites/${cell.id}.png`, width: 256, height: 256,
      kind: group, anchor, atlas, clip_rect_pico2d: [cell.col * 256, (3 - cell.row) * 256, 256, 256],
      content_rect: {left, top, width, height}, source_rect: cell.sourceRect,
      source_content_rect: cell.box, sha256: hash(png)};
    overlays.push({input: png, left: cell.col * 256, top: cell.row * 256});
    validation.sprite_count++;
  }
  const bytes = await sharp({create: {width: 1024, height: 1024, channels: 4, background: '#00000000'}})
    .composite(overlays).png().toBuffer();
  await fs.writeFile(path.join(root, 'atlases', `${group}.png`), bytes);
  manifest.atlases[atlas] = {file: `atlases/${group}.png`, width: 1024, height: 1024, sha256: hash(bytes)};
}
await fs.writeFile(path.join(root, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
await fs.writeFile(path.join(root, 'validation.json'), JSON.stringify(validation, null, 2) + '\n');
console.log(JSON.stringify(validation));
