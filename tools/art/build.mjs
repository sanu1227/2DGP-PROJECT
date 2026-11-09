/** Slice original generated atlases into aligned sprites. No game runtime dependency. */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const root = path.join(project, 'assets/art_v1');
const size = 256;
const tileWidth = 224;
const tileHeight = 112;
const stoneLip = 12;
const alphaCutoff = 8;
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const writeJson = (file, value) => fs.writeFile(file, JSON.stringify(value, null, 2) + '\n');
const groupIds = {
  environment: [
    'floor_plain', 'floor_cracked', 'floor_moss', 'floor_scuffed',
    'wall_low', 'rubble', 'trap_broken', 'trap_installed',
    'trap_active', 'post_empty', 'exit_closed', 'exit_ready',
  ],
  props: [
    'part', 'bone_bundle', 'soldier_carried', 'soldier_deployed',
    'bench_empty', 'bench_one_bone', 'bench_assembled', 'lever_off',
    'lever_on', 'plate_up', 'plate_down', 'chute_inlet',
    'chute_outlet', 'conveyor_ne', 'conveyor_se', 'brazier',
  ],
  worker: ['ne', 'se', 'sw', 'nw'].flatMap(direction =>
    ['idle', 'walk_a', 'walk_b', 'carry'].map(pose => `worker_${direction}_${pose}`)),
};
const dimensions = {
  part: { width: 96 }, bone_bundle: { width: 98 },
  soldier_carried: { height: 132 }, soldier_deployed: { height: 174 },
  bench_empty: { width: 180 }, bench_one_bone: { width: 180 }, bench_assembled: { width: 180 },
  lever_off: { width: 112 }, lever_on: { width: 112 },
  plate_up: { width: 192 }, plate_down: { width: 192 },
  chute_inlet: { width: 130 }, chute_outlet: { width: 130 },
  conveyor_ne: { width: 190 }, conveyor_se: { width: 190 }, brazier: { width: 100 },
};
// Standalone replacements retain the original atlas slot and runtime anchor.
const replacements = { part: 'sources/part-fragment.png' };
const manifest = {
  version: 1, created: '2026-11-08', status: 'first-production-art-pass',
  generator: 'built-in image_gen',
  coordinates: {
    image: 'top-left origin, x right, y down; anchors in pixels',
    pico2d: 'bottom-left screen origin, y up',
    draw: 'For a scaled sprite use image.draw(sx+(width/2-anchor.x)*scale, sy+(anchor.y-height/2)*scale, width*scale, height*scale).',
    clip: 'clip_rect_pico2d already converts atlas y to bottom-left origin.',
    tile_footprint: { width: tileWidth, height: tileHeight },
  },
  alpha_export: { cutoff: alphaCutoff, note: 'Only near-transparent alpha noise is cleared. Original source PNGs remain unchanged.' },
  sources: {}, atlases: {}, sprites: {},
  animations: { worker: {} },
  limitations: [
    'Originally delivered as an art pack; current game integration status is documented in assets/art_v1/README.md.',
    'Walk contains two generated key poses, not a final polished animation cycle. Timing is a starting value.',
    'Pressure plates, chutes and conveyors are art for planned mechanics, not implemented gameplay.',
    'Conveyors have NE and SE art only. Do not assume NW/SW variants exist.',
    'Bench assembled is an optional visual state; current game gives the soldier directly to the player.',
    'UI art, audio, effects animation and a final character design approval are outside this first pack.',
  ],
};

function bounds(data, width, height, threshold = alphaCutoff) {
  let left = width, top = height, right = -1, bottom = -1;
  let visible = 0, transparent = 0, edge = 0;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const a = data[(y * width + x) * 4 + 3];
    if (a === 0) transparent++;
    if (a > threshold) {
      visible++;
      left = Math.min(left, x); top = Math.min(top, y);
      right = Math.max(right, x); bottom = Math.max(bottom, y);
      if (!x || !y || x === width - 1 || y === height - 1) edge++;
    }
  }
  if (!visible) throw new Error('Empty sprite');
  return { left, top, width: right - left + 1, height: bottom - top + 1, visible, transparent, edge };
}

for (const folder of ['tiles', 'objects', 'characters/worker', 'atlases', 'previews']) {
  await fs.mkdir(path.join(root, folder), { recursive: true });
}

for (const [group, ids] of Object.entries(groupIds)) {
  const rows = ids.length / 4;
  const sourceBytes = await fs.readFile(path.join(root, `sources/${group}.png`));
  const meta = await sharp(sourceBytes).metadata();
  if (!meta.hasAlpha) throw new Error(`${group}: source has no alpha`);
  manifest.sources[group] = {
    file: `sources/${group}.png`, width: meta.width, height: meta.height,
    sha256: hash(sourceBytes), grid: [4, rows],
  };
  const cells = [];
  for (let index = 0; index < ids.length; index++) {
    const column = index % 4, row = Math.floor(index / 4);
    const left = Math.round(column * meta.width / 4), top = Math.round(row * meta.height / rows);
    const rect = { left, top, width: Math.round((column + 1) * meta.width / 4) - left,
      height: Math.round((row + 1) * meta.height / rows) - top };
    const { data, info } = await sharp(sourceBytes).extract(rect).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    // Clear low-opacity matte specks without changing painted RGB or the source image.
    for (let p = 3; p < data.length; p += 4) if (data[p] <= alphaCutoff) data[p] = 0;
    const box = bounds(data, info.width, info.height);
    if (box.edge) throw new Error(`${ids[index]}: source touches cell edge; inspect before slicing`);
    cells.push({ data, info, rect, box, id: ids[index], row, column });
  }
  const workerScale = group === 'worker' ? 176 / Math.max(...cells.map(cell => cell.box.height)) : null;
  for (const cell of cells) {
    const file = replacements[cell.id];
    if (!file) continue;
    const bytes = await fs.readFile(path.join(root, file));
    const { data, info } = await sharp(bytes).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    for (let p = 3; p < data.length; p += 4) if (data[p] <= alphaCutoff) data[p] = 0;
    const box = bounds(data, info.width, info.height);
    if (box.edge) throw new Error(`${cell.id}: replacement touches image edge`);
    Object.assign(cell, { data, info, box, sourceFile: file,
      rect: { left: 0, top: 0, width: info.width, height: info.height } });
    manifest.sources[`${cell.id}_replacement`] = {
      file, width: info.width, height: info.height, sha256: hash(bytes),
    };
  }
  const composites = [];
  for (const cell of cells) {
    const { id, box, info } = cell;
    let scaleX, scaleY, sourceAnchor, anchor;
    if (group === 'environment') {
      scaleX = tileWidth / box.width;
      // Floor top face is fitted to a 2:1 diamond; a 12px stone lip remains below it.
      scaleY = (tileHeight + stoneLip) / cells[0].box.height;
      sourceAnchor = [box.left + box.width / 2,
        box.top + box.height - (tileHeight / 2 + stoneLip) / scaleY];
      anchor = { x: 128, y: 160 };
    } else if (group === 'worker') {
      const idle = cells[cell.row * 4];
      // Preserve the torso reference across a row so extended carrying arms do not shift the body.
      sourceAnchor = [idle.box.left + idle.box.width / 2, idle.box.top + idle.box.height];
      scaleX = scaleY = workerScale;
      anchor = { x: 128, y: 220 };
    } else {
      const target = dimensions[id];
      scaleX = scaleY = target.width ? target.width / box.width : target.height / box.height;
      // Ground center under the bounding footprint; per-art direction corrections can be added later.
      sourceAnchor = [box.left + box.width / 2, box.top + box.height];
      anchor = { x: 128, y: 220 };
    }
    const width = Math.round(box.width * scaleX), height = Math.round(box.height * scaleY);
    const left = Math.round(anchor.x - (sourceAnchor[0] - box.left) * scaleX);
    const top = Math.round(anchor.y - (sourceAnchor[1] - box.top) * scaleY);
    if (left < 2 || top < 2 || left + width > size - 2 || top + height > size - 2) {
      throw new Error(`${id}: output would clip (${left}, ${top}, ${width}, ${height})`);
    }
    const cropped = await sharp(cell.data, { raw: { width: info.width, height: info.height, channels: 4 } })
      .extract({ left: box.left, top: box.top, width: box.width, height: box.height })
      .resize(width, height, { fit: 'fill', kernel: 'lanczos3' }).png().toBuffer();
    const bytes = await sharp({ create: { width: size, height: size, channels: 4, background: '#00000000' } })
      .composite([{ input: cropped, left, top }]).png().toBuffer();
    const category = group === 'environment' ? 'tiles' : group === 'worker' ? 'characters/worker' : 'objects';
    const file = `${category}/${id}.png`;
    await fs.writeFile(path.join(root, file), bytes);
    composites.push({ input: bytes, left: cell.column * size, top: cell.row * size });
    manifest.sprites[id] = {
      file, width: size, height: size, anchor,
      atlas: group, clip_rect_pico2d: [cell.column * size, (rows - cell.row - 1) * size, size, size],
      source_rect: cell.rect, source_content_rect: { left: box.left, top: box.top, width: box.width, height: box.height },
      ...(cell.sourceFile ? { source_file: cell.sourceFile } : {}),
      content_rect: { left, top, width, height },
      sha256: hash(bytes),
      intended_use: ['plate_up', 'plate_down', 'chute_inlet', 'chute_outlet', 'conveyor_ne', 'conveyor_se'].includes(id)
        ? 'planned-mechanic-art' : id === 'bench_assembled' ? 'optional-visual-state' : 'prototype-art',
    };
  }
  const atlas = await sharp({ create: { width: 4 * size, height: rows * size, channels: 4, background: '#00000000' } })
    .composite(composites).png().toBuffer();
  await fs.writeFile(path.join(root, `atlases/${group}.png`), atlas);
  manifest.atlases[group] = { file: `atlases/${group}.png`, width: 4 * size, height: rows * size,
    cell_size: size, grid: [4, rows], sha256: hash(atlas) };
}
// Standalone wall variants use the same footprint and ground anchor as wall_low.
groupIds.low_walls = [
  'wall_low_chipped', 'wall_low_patched', 'wall_low_braced', 'wall_low_axis_y',
  'wall_low_corner_nw', 'wall_low_corner_ne', 'wall_low_corner_se', 'wall_low_corner_sw',
  'wall_low_pier',
];
const lowWallRows = Math.ceil(groupIds.low_walls.length / 4);
const lowWallComposites = [];
for (const [index, id] of groupIds.low_walls.entries()) {
  const file = `sources/${id.replaceAll('_', '-')}.png`;
  const source = await fs.readFile(path.join(root, file));
  const meta = await sharp(source).metadata();
  if (!meta.hasAlpha) throw new Error(`${id}: source has no alpha`);
  const { data, info } = await sharp(source).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  for (let p = 3; p < data.length; p += 4) if (data[p] <= alphaCutoff) data[p] = 0;
  const box = bounds(data, info.width, info.height);
  if (box.edge) throw new Error(`${id}: source touches image edge`);
  const reference = manifest.sprites.wall_low;
  // Side-facing elbows project deeper than a straight wall. Preserve their
  // masonry height instead of flattening them into the straight-wall box.
  const rect = ['wall_low_corner_ne', 'wall_low_corner_sw'].includes(id)
    ? { ...reference.content_rect, top: 43, height: 185 }
    : reference.content_rect;
  const crop = await sharp(data, { raw: { width: info.width, height: info.height, channels: 4 } })
    .extract({ left: box.left, top: box.top, width: box.width, height: box.height })
    .resize(rect.width, rect.height, { fit: 'fill' }).png().toBuffer();
  const bytes = await sharp({ create: { width: size, height: size, channels: 4, background: '#00000000' } })
    .composite([{ input: crop, left: rect.left, top: rect.top }]).png().toBuffer();
  await fs.writeFile(path.join(root, `tiles/${id}.png`), bytes);
  manifest.sources[id] = { file, width: info.width, height: info.height, sha256: hash(source) };
  manifest.sprites[id] = {
    file: `tiles/${id}.png`, width: size, height: size, anchor: reference.anchor,
    atlas: 'low_walls', clip_rect_pico2d: [(index % 4) * size, (lowWallRows - 1 - Math.floor(index / 4)) * size, size, size],
    source_file: file, source_rect: { left: 0, top: 0, width: info.width, height: info.height },
    source_content_rect: { left: box.left, top: box.top, width: box.width, height: box.height },
    content_rect: rect, sha256: hash(bytes), intended_use: 'prototype-art',
  };
  lowWallComposites.push({ input: bytes, left: (index % 4) * size, top: Math.floor(index / 4) * size });
}
const lowWalls = await sharp({ create: { width: 4 * size, height: lowWallRows * size, channels: 4, background: '#00000000' } })
  .composite(lowWallComposites).png().toBuffer();
await fs.writeFile(path.join(root, 'atlases/low_walls.png'), lowWalls);
manifest.atlases.low_walls = { file: 'atlases/low_walls.png', width: 4 * size, height: lowWallRows * size,
  cell_size: size, grid: [4, lowWallRows], sha256: hash(lowWalls) };

for (const direction of ['ne', 'se', 'sw', 'nw']) {
  manifest.animations.worker[direction] = {
    idle: [`worker_${direction}_idle`],
    walk: [`worker_${direction}_idle`, `worker_${direction}_walk_a`, `worker_${direction}_idle`, `worker_${direction}_walk_b`],
    carry: [`worker_${direction}_carry`], suggested_walk_fps: 6,
  };
}

const escapeXml = text => String(text).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[char]);
const textSvg = (width, height, elements) => Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">${elements}</svg>`);
const text = (x, y, value, fontSize = 16, fill = '#d6e0d9') =>
  `<text x="${x}" y="${y}" fill="${fill}" font-size="${fontSize}" font-family="Segoe UI, Malgun Gothic, sans-serif">${escapeXml(value)}</text>`;
const composites = [];
let labels = text(40, 48, 'THE PLACE THE HERO LEFT', 30, '#e4c78c')
  + text(40, 82, `ART PACK v1  |  ${Object.keys(manifest.sprites).length} sprites  |  2:1 isometric  |  alpha PNG`, 18, '#9eb2b2');
let y = 120;
for (const [group, ids] of Object.entries(groupIds)) {
  labels += text(40, y + 25, `${group.toUpperCase()}  /  ${ids.length}`, 20, '#7fd4c6');
  y += 40;
  for (let index = 0; index < ids.length; index++) {
    const col = index % 8, row = Math.floor(index / 8);
    const x = 30 + col * 192, top = y + row * 195;
    const sprite = manifest.sprites[ids[index]];
    const image = await sharp(path.join(root, sprite.file)).resize(176, 176).toBuffer();
    composites.push({ input: image, left: x + 8, top });
    labels += text(x + 4, top + 190, ids[index], 13);
  }
  y += Math.ceil(ids.length / 8) * 195 + 24;
}
await sharp({ create: { width: 1596, height: y + 25, channels: 4, background: '#172329' } })
  .composite([...composites, { input: textSvg(1596, y + 25, labels) }]).png().toFile(path.join(root, 'previews/overview.png'));

// Compose the real third tutorial layout as an art review, without changing the game renderer.
const stages = JSON.parse(await fs.readFile(path.join(project, 'data/stages.json'), 'utf8'));
const map = stages.stages[2].map;
const scene = [];
const scale = 110 / tileWidth;
async function place(id, x, y, customScale = scale) {
  const sprite = manifest.sprites[id];
  const w = Math.round(size * customScale), h = Math.round(size * customScale);
  const img = await sharp(path.join(root, sprite.file)).resize(w, h).toBuffer();
  scene.push({ input: img, left: Math.round(x - sprite.anchor.x * customScale), top: Math.round(y - sprite.anchor.y * customScale) });
}
for (let depth = 0; depth < map.length + map[0].length - 1; depth++) {
  for (let row = 0; row < map.length; row++) {
    const col = depth - row;
    if (col < 0 || col >= map[row].length) continue;
    const char = map[row][col];
    const sx = 520 + (col - row) * 55, sy = 200 + depth * 27.5;
    let tile = char === '#' ? 'wall_low' : char === 'T' ? 'trap_broken'
      : char === 'S' ? 'post_empty' : char === 'E' ? 'exit_closed'
        : ['floor_plain', 'floor_cracked', 'floor_plain', 'floor_moss'][(col + row * 3) % 4];
    await place(tile, sx, sy);
    const object = { '@': 'worker_se_idle', P: 'part', B: 'bone_bundle', A: 'bench_empty', L: 'lever_off' }[char];
    if (object) await place(object, sx, sy);
  }
}
let sceneLabels = text(55, 62, '용사가 지나간 자리', 34, '#e4c78c')
  + text(57, 98, '에셋 조립 예시 · 입문 3번 방 · 실제 게임 화면 아님', 18, '#a3b5b4')
  + text(1020, 210, 'STATE READABILITY', 22, '#7fd4c6');
for (const [i, [a, b, caption]] of [
  ['trap_installed', 'trap_active', 'Trap: installed / active'],
  ['lever_off', 'lever_on', 'Lever: off / on'],
  ['soldier_carried', 'soldier_deployed', 'Guard: carried / deployed'],
  ['exit_closed', 'exit_ready', 'Exit: closed / ready'],
].entries()) {
  const sy = 285 + i * 145;
  await place(a, 1100, sy, 0.48); await place(b, 1260, sy, 0.48);
  sceneLabels += text(1020, sy + 60, caption, 16);
}
sceneLabels += text(57, 800, 'Teal repair worker  /  brass mechanisms  /  ivory bones  /  violet guard posts', 18)
  + text(57, 834, `${Object.keys(manifest.sprites).length} individual PNGs + ${Object.keys(manifest.atlases).length} aligned atlases. Game rules preserved.`, 16, '#9eb2b2')
  + text(57, 870, 'First art pass. Walk keyframes and small-scale readability still need play review.', 16, '#9eb2b2');
await sharp({ create: { width: 1440, height: 920, channels: 4, background: '#172329' } })
  .composite([...scene, { input: textSvg(1440, 920, sceneLabels) }]).png().toFile(path.join(root, 'previews/room_composition.png'));

// Tile-only connectivity review at a larger scale.
const tileScene = [];
for (let depth = 0; depth < 7; depth++) for (let row = 0; row < 4; row++) {
  const col = depth - row;
  if (col < 0 || col > 3) continue;
  const id = ['floor_plain', 'floor_cracked', 'floor_moss', 'floor_scuffed'][(col + row) % 4];
  const sprite = manifest.sprites[id];
  tileScene.push({ input: await fs.readFile(path.join(root, sprite.file)), left: 480 + (col - row) * 112 - 128,
    top: 160 + (col + row) * 56 - 160 });
}
await sharp({ create: { width: 960, height: 650, channels: 4, background: '#273339' } })
  .composite([...tileScene, { input: textSvg(960, 650, text(35, 45, 'Tile connectivity review: 224 x 112 step, shared ground anchors', 19)) }])
  .png().toFile(path.join(root, 'previews/tile_connection.png'));

const validation = { sprite_count: Object.keys(manifest.sprites).length, atlas_count: Object.keys(manifest.atlases).length,
  checks: { source_has_alpha: true, source_cell_edges_clear: true, output_clipping: false,
    sprites_have_transparent_pixels: true, sprites_have_visible_content: true, runtime_dependencies_changed: false },
  sprites: [] };
for (const [id, sprite] of Object.entries(manifest.sprites)) {
  const { data, info } = await sharp(path.join(root, sprite.file)).raw().toBuffer({ resolveWithObject: true });
  const box = bounds(data, info.width, info.height, 0);
  if (info.channels !== 4 || !box.transparent || box.edge) throw new Error(`${id}: exported alpha or padding check failed`);
  validation.sprites.push({ id, size: [info.width, info.height], transparent_fraction: Number((box.transparent / (size * size)).toFixed(4)),
    content_bounds: { left: box.left, top: box.top, width: box.width, height: box.height }, edge_pixels: box.edge });
}
await writeJson(path.join(root, 'manifest.json'), manifest);
await writeJson(path.join(root, 'validation.json'), validation);
console.log(`Exported ${validation.sprite_count} sprites, ${validation.atlas_count} atlases and 3 previews. Alpha, padding and source-cell checks passed.`);
