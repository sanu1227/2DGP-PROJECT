/** Build individual theme packs. Sources are preserved; only derived files are rebuilt. */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const pack = path.join(project, 'assets/map_pack_v1');
const oldRoot = path.join(project, 'assets/art_v1');
const oldManifest = JSON.parse(await fs.readFile(path.join(oldRoot, 'manifest.json'), 'utf8'));
const allThemes = ['crypt', 'sewer', 'forge', 'archive'];
const themes = process.argv.slice(2).length ? process.argv.slice(2) : allThemes;
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const json = (file, data) => fs.writeFile(file, JSON.stringify(data, null, 2) + '\n');
const esc = value => String(value).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]);
const text = (x, y, value, fontSize = 18, fill = '#dce3dc') =>
  `<text x="${x}" y="${y}" fill="${fill}" font-size="${fontSize}" font-family="Segoe UI, Malgun Gothic, sans-serif">${esc(value)}</text>`;
const svg = (width, height, body) => Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">${body}</svg>`);

function bounds(data, width, height) {
  let left = width, top = height, right = -1, bottom = -1, visible = 0, edge = 0;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    if (data[(y * width + x) * 4 + 3] <= 8) continue;
    visible++;
    left = Math.min(left, x); top = Math.min(top, y);
    right = Math.max(right, x); bottom = Math.max(bottom, y);
    if (!x || !y || x === width - 1 || y === height - 1) edge++;
  }
  if (!visible) throw new Error('Empty sprite');
  return { left, top, width: right - left + 1, height: bottom - top + 1, visible, edge };
}

for (const theme of themes) {
  if (!allThemes.includes(theme)) throw new Error(`Unknown theme: ${theme}`);
  const root = path.join(pack, theme);
  const spec = JSON.parse(await fs.readFile(path.join(root, 'source/spec.json'), 'utf8'));
  const original = await fs.readFile(path.join(root, 'source/atlas.png'));
  const meta = await sharp(original).metadata();
  if (!meta.hasAlpha || spec.entries.length !== 16) throw new Error(`${theme}: expected alpha source and 16 entries`);
  for (const dir of ['tiles', 'props', 'previews']) await fs.mkdir(path.join(root, dir), { recursive: true });
  const cells = [];
  for (let i = 0; i < 16; i++) {
    const col = i % 4, row = Math.floor(i / 4);
    const left = Math.round(col * meta.width / 4), top = Math.round(row * meta.height / 4);
    const rect = { left, top, width: Math.round((col + 1) * meta.width / 4) - left,
      height: Math.round((row + 1) * meta.height / 4) - top };
    const { data, info } = await sharp(original).extract(rect).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    for (let p = 3; p < data.length; p += 4) if (data[p] <= 8) data[p] = 0;
    const box = bounds(data, info.width, info.height);
    if (box.edge) throw new Error(`${spec.entries[i].id}: source crosses cell edge (${box.edge} pixels)`);
    cells.push({ ...spec.entries[i], data, info, box, rect, col, row });
  }
  const manifest = {
    version: 1, created: spec.date, theme, title: spec.title, generator: spec.generator,
    status: 'map-decoration-pack; stage placement lives in data/scenery.json',
    coordinates: { image: 'top-left origin; anchor and source_rect use x right, y down',
      pico2d: 'clip_rect_pico2d uses bottom-left origin', tile_footprint: { width: 224, height: 112 } },
    source: { file: 'source/atlas.png', width: meta.width, height: meta.height, sha256: hash(original), grid: [4, 4] },
    atlases: {}, sprites: {},
    placement: 'Wall variants are rear-edge boundary decorations. Neither walls nor props create collision rules automatically.',
  };
  const composites = [];
  for (const cell of cells) {
    const { box } = cell;
    let width, height, left, top, anchor;
    if (cell.kind !== 'prop') {
      width = 224;
      // Fit tile top and front lip to the same footprint used by art_v1.
      height = Math.round(box.height * 124 / cells[0].box.height);
      anchor = { x: 128, y: 160 };
      left = 16;
      top = 228 - height;
    } else {
      const scale = Math.min(cell.width / box.width, 196 / box.height);
      width = Math.round(box.width * scale);
      height = Math.round(box.height * scale);
      anchor = { x: 128, y: 220 };
      left = Math.round(128 - width / 2);
      top = 220 - height;
    }
    if (top < 4 || left < 4 || top + height > 252 || left + width > 252) {
      throw new Error(`${cell.id}: normalized sprite would clip`);
    }
    const cropped = await sharp(cell.data, { raw: { width: cell.info.width, height: cell.info.height, channels: 4 } })
      .extract({ left: box.left, top: box.top, width: box.width, height: box.height })
      .resize(width, height, { fit: 'fill' }).png().toBuffer();
    const bytes = await sharp({ create: { width: 256, height: 256, channels: 4, background: '#00000000' } })
      .composite([{ input: cropped, left, top }]).png().toBuffer();
    const file = `${cell.kind === 'prop' ? 'props' : 'tiles'}/${cell.id}.png`;
    await fs.writeFile(path.join(root, file), bytes);
    manifest.sprites[cell.id] = {
      file, kind: cell.kind, width: 256, height: 256, anchor, atlas: theme,
      clip_rect_pico2d: [cell.col * 256, (3 - cell.row) * 256, 256, 256],
      source_rect: cell.rect, source_content_rect: { left: box.left, top: box.top, width: box.width, height: box.height },
      content_rect: { left, top, width, height }, sha256: hash(bytes),
    };
    composites.push({ input: bytes, left: cell.col * 256, top: cell.row * 256 });
  }
  const atlas = await sharp({ create: { width: 1024, height: 1024, channels: 4, background: '#00000000' } })
    .composite(composites).png().toBuffer();
  await fs.writeFile(path.join(root, 'atlas.png'), atlas);
  manifest.atlases[theme] = { file: 'atlas.png', width: 1024, height: 1024, cell_size: 256, grid: [4, 4], sha256: hash(atlas) };
  await json(path.join(root, 'manifest.json'), manifest);

  let labels = text(30, 44, spec.title, 30, '#e7c98d')
    + text(30, 77, `${spec.subtitle}  /  4 floors + 4 walls + 8 props`, 18, '#9eb6b2');
  const overview = [];
  for (let i = 0; i < 16; i++) {
    const entry = manifest.sprites[spec.entries[i].id];
    const x = 16 + (i % 4) * 256, y = 100 + Math.floor(i / 4) * 256;
    overview.push({ input: await sharp(path.join(root, entry.file)).resize(240, 240).toBuffer(), left: x, top: y });
    labels += text(x + 8, y + 249, spec.entries[i].id, 13);
  }
  await sharp({ create: { width: 1056, height: 1140, channels: 4, background: '#19252b' } })
    .composite([...overview, { input: svg(1056, 1140, labels) }]).png().toFile(path.join(root, 'previews/overview.png'));

  // Small room demonstrates real sprite composition with the existing worker and puzzle art.
  const scene = [];
  const scale = 112 / 224;
  const screen = (x, y) => [480 + (x - y) * 56, 170 + (x + y) * 28];
  async function put(id, x, y) {
    const old = !manifest.sprites[id];
    const entry = (old ? oldManifest : manifest).sprites[id];
    const [sx, sy] = screen(x, y);
    scene.push({ input: await sharp(path.join(old ? oldRoot : root, entry.file)).resize(128, 128).toBuffer(),
      left: Math.round(sx - entry.anchor.x * scale), top: Math.round(sy - entry.anchor.y * scale) });
  }
  const floors = spec.entries.slice(0, 4).map(e => e.id);
  const placements = spec.entries.slice(8).map((entry, i) => ({ id: entry.id,
    pos: [[1, 1], [3, 1], [5, 1], [1, 3], [5, 3], [1, 5], [3, 5], [5, 5]][i] }));
  const tall = [];
  for (let depth = 0; depth < 11; depth++) for (let y = 0; y < 6; y++) {
    const x = depth - y;
    if (x < 0 || x > 5) continue;
    let tile = floors[(x * 3 + y) % 4];
    if (x === 0 || y === 0) {
      tile = floors[0];
      const wall = x === 0 && y === 0 ? 'wall_corner' : x === 0 ? 'wall_nw' : 'wall_ne';
      tall.push({ id: `${theme}_${x === 0 && y === 4 ? 'wall_broken' : wall}`, pos: [x, y] });
    }
    if (x === 3 && y === 3) tile = 'trap_installed';
    if (x === 4 && y === 5) tile = 'exit_ready';
    await put(tile, x, y);
  }
  tall.push(...placements, { id: 'worker_se_idle', pos: [3, 4] }, { id: 'part', pos: [4, 2] });
  tall.sort((a, b) => (a.pos[0] + a.pos[1]) - (b.pos[0] + b.pos[1]));
  for (const entry of tall) await put(entry.id, ...entry.pos);
  const title = text(40, 48, spec.title, 30, '#e7c98d')
    + text(40, 82, '조립 예시 · 기존 수리공/함정과 조합 · 실제 플레이 맵 아님', 16, '#a9bdb8')
    + text(40, 594, `${spec.subtitle}   |   16 reusable sprites   |   224 x 112 tile footprint`, 18, '#a9bdb8');
  await sharp({ create: { width: 960, height: 640, channels: 4, background: '#19252b' } })
    .composite([...scene, { input: svg(960, 640, title) }]).png().toFile(path.join(root, 'previews/room.png'));

  const validation = { count: 16, alpha: true, source_cells_unclipped: true, output_padding: true, sprites: [] };
  for (const [id, entry] of Object.entries(manifest.sprites)) {
    const { data, info } = await sharp(path.join(root, entry.file)).raw().toBuffer({ resolveWithObject: true });
    const box = bounds(data, info.width, info.height);
    if (info.channels !== 4 || box.edge || box.visible >= 65536) throw new Error(`${id}: alpha/padding validation failed`);
    validation.sprites.push({ id, visible_pixels: box.visible, edge_pixels: box.edge });
  }
  await json(path.join(root, 'validation.json'), validation);
  console.log(`${theme}: 16 RGBA sprites + atlas + previews; source borders and output padding passed.`);
}

// Aggregate previews only when all four individual packs have been built.
if ((await Promise.all(allThemes.map(async t => {
  try { await fs.access(path.join(pack, t, 'previews/room.png')); return true; } catch { return false; }
}))).every(Boolean)) {
  const combined = await Promise.all(allThemes.map(async (theme, i) => ({
    input: await fs.readFile(path.join(pack, theme, 'previews/room.png')),
    left: (i % 2) * 960, top: Math.floor(i / 2) * 640,
  })));
  await sharp({ create: { width: 1920, height: 1280, channels: 4, background: '#19252b' } })
    .composite(combined).png().toFile(path.join(pack, 'theme_comparison.png'));
}
