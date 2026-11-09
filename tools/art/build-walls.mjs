/** Slice generated wall sheets; keep source PNGs and prompts intact. */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const pack = path.join(project, 'assets/wall_pack_v1');
const themes = ['crypt', 'sewer', 'forge', 'archive'];
const selected = process.argv.slice(2).length ? process.argv.slice(2) : themes;
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const json = (file, data) => fs.writeFile(file, JSON.stringify(data, null, 2) + '\n');

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

for (const theme of selected) {
  if (!themes.includes(theme)) throw new Error(`Unknown theme: ${theme}`);
  const root = path.join(pack, theme);
  const spec = JSON.parse(await fs.readFile(path.join(root, 'source/spec.json'), 'utf8'));
  const original = await fs.readFile(path.join(root, 'source/atlas.png'));
  const meta = await sharp(original).metadata();
  if (!meta.hasAlpha) throw new Error(`${theme}: transparent source required`);
  // Generated sheets keep columns regular but vary row spacing; use actual alpha gutters.
  const rgba = await sharp(original).ensureAlpha().raw().toBuffer();
  const bands = [];
  let occupied = false;
  for (let y = 0; y < meta.height; y++) {
    let visible = false;
    for (let x = 0; x < meta.width; x++) {
      if (rgba[(y * meta.width + x) * 4 + 3] > 8) { visible = true; break; }
    }
    if (visible && !occupied) bands.push([y]);
    if (!visible && occupied) bands.at(-1).push(y - 1);
    occupied = visible;
  }
  if (occupied) bands.at(-1).push(meta.height - 1);
  if (bands.length !== 3) throw new Error(`${theme}: expected three isolated rows, found ${bands.length}`);
  const rowEdges = [0, Math.floor((bands[0][1] + bands[1][0]) / 2),
    Math.floor((bands[1][1] + bands[2][0]) / 2), meta.height];
  const ids = ['wall_tall_nw', 'wall_tall_ne', 'wall_damaged_nw', 'wall_damaged_ne',
    'wall_short_nw', 'wall_short_ne', ...spec.mounts.flatMap(([name]) => [`mount_${name}_nw`, `mount_${name}_ne`])];
  for (const dir of ['walls', 'mounts', 'previews']) await fs.mkdir(path.join(root, dir), { recursive: true });
  const cells = [];
  for (let i = 0; i < ids.length; i++) {
    const col = i % 4, row = Math.floor(i / 4);
    const left = Math.round(col * meta.width / 4), top = rowEdges[row];
    const rect = { left, top, width: Math.round((col + 1) * meta.width / 4) - left,
      height: rowEdges[row + 1] - top };
    const { data, info } = await sharp(original).extract(rect).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    for (let p = 3; p < data.length; p += 4) if (data[p] <= 8) data[p] = 0;
    const box = bounds(data, info.width, info.height);
    if (box.edge) throw new Error(`${ids[i]} crosses its source cell`);
    cells.push({ id: `${theme}_${ids[i]}`, data, info, box, rect, col, row, i });
  }
  const atlasName = `walls_${theme}`;
  const manifest = {
    version: 1, created: spec.generation.date, theme, title: spec.title,
    generator: spec.generation.tool,
    coordinates: { image: 'top-left; x right and y down', pico2d: 'clip_rect_pico2d uses bottom-left origin',
      tile_footprint: { width: 224, height: 112 }, wall_upright: 232 },
    source: { file: 'source/atlas.png', width: meta.width, height: meta.height, sha256: hash(original), grid: [4, 3], row_edges: rowEdges },
    placement: 'Draw a floor first. Rear walls anchor at tile center; independent mounts anchor at their center. Collision belongs to the level.',
    atlases: {}, sprites: {},
  };
  const composites = [], checks = [];
  let labels = `<text x="24" y="38" font-size="25">${spec.title} · 벽면과 벽 장식 12종</text>`;
  for (const cell of cells) {
    const { box, i } = cell;
    const mount = i >= 6;
    const direction = i % 2 ? 'ne' : 'nw';
    let width, height, left, top, anchor;
    if (mount) {
      const factor = Math.min(94 / box.width, 140 / box.height);
      width = Math.round(box.width * factor); height = Math.round(box.height * factor);
      left = Math.round(128 - width / 2); top = Math.round(192 - height / 2);
      anchor = { x: 128, y: 192 };
    } else {
      width = 128;
      height = Math.round(288 * box.height / cells[i % 2].box.height);
      left = direction === 'nw' ? 8 : 120; top = 340 - height;
      anchor = { x: 128, y: 340 };
    }
    if (top < 4 || left < 4 || top + height > 380 || left + width > 252) throw new Error(`${cell.id}: output clips`);
    const cropped = await sharp(cell.data, { raw: { width: cell.info.width, height: cell.info.height, channels: 4 } })
      .extract({ left: box.left, top: box.top, width: box.width, height: box.height })
      .resize(width, height, { fit: 'fill' }).png().toBuffer();
    const bytes = await sharp({ create: { width: 256, height: 384, channels: 4, background: '#00000000' } })
      .composite([{ input: cropped, left, top }]).png().toBuffer();
    const file = `${mount ? 'mounts' : 'walls'}/${cell.id}.png`;
    await fs.writeFile(path.join(root, file), bytes);
    manifest.sprites[cell.id] = {
      file, kind: mount ? 'wall_mount' : 'wall_face', direction,
      width: 256, height: 384, anchor, atlas: atlasName,
      clip_rect_pico2d: [cell.col * 256, (2 - cell.row) * 384, 256, 384],
      source_rect: cell.rect, source_content_rect: { left: box.left, top: box.top, width: box.width, height: box.height },
      content_rect: { left, top, width, height }, sha256: hash(bytes),
    };
    const { data, info } = await sharp(bytes).raw().toBuffer({ resolveWithObject: true });
    const check = bounds(data, info.width, info.height);
    if (info.channels !== 4 || check.edge) throw new Error(`${cell.id}: alpha/padding failed`);
    checks.push({ id: cell.id, visible_pixels: check.visible, edge_pixels: check.edge });
    composites.push({ input: bytes, left: cell.col * 256, top: cell.row * 384 });
    labels += `<text x="${cell.col * 256 + 8}" y="${cell.row * 384 + 422}" font-size="12">${cell.id}</text>`;
  }
  const atlas = await sharp({ create: { width: 1024, height: 1152, channels: 4, background: '#00000000' } })
    .composite(composites).png().toBuffer();
  await fs.writeFile(path.join(root, 'atlas.png'), atlas);
  manifest.atlases[atlasName] = { file: 'atlas.png', width: 1024, height: 1152, cell_width: 256, cell_height: 384, grid: [4, 3], sha256: hash(atlas) };
  await json(path.join(root, 'manifest.json'), manifest);
  await json(path.join(root, 'validation.json'), { count: 12, alpha: true, source_cells_unclipped: true, output_padding: true, sprites: checks });
  const labelSvg = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1216"><g font-family="Segoe UI, Malgun Gothic, sans-serif" fill="#e6dac0">${labels}</g></svg>`);
  await sharp({ create: { width: 1024, height: 1216, channels: 4, background: '#26323b' } })
    .composite([{ input: atlas, top: 64, left: 0 }, { input: labelSvg }]).png().toFile(path.join(root, 'previews/overview.png'));
  console.log(`${theme}: 12 RGBA sprites, atlas and catalog; alpha, source borders, output padding passed.`);
}
