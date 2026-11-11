// Generated character sheets are only sliced, aligned and packed here.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../assets/comic_motion_v1');
const canvas = 362;
const castNames = ['hero_enter', 'hero_leave', 'skeleton_guard', 'skeleton_broken',
  'boss', 'worker_cower', 'skeleton_skull', 'breath'];
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const manifest = {version: 1, generator: 'built-in image_gen', canvas: [canvas, canvas],
  worker_anchor: [210, 344], cast_anchor: [181, 344], sources: {}, sprites: {}};
await fs.mkdir(path.join(root, 'sprites'), {recursive: true});

function bounds(data, width, height) {
  let left = width, top = height, right = -1, bottom = -1, transparent = 0;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const alpha = data[(y * width + x) * 4 + 3];
    if (!alpha) transparent++;
    if (alpha > 16) {
      left = Math.min(left, x); top = Math.min(top, y);
      right = Math.max(right, x); bottom = Math.max(bottom, y);
    }
  }
  if (right < left || transparent < width * height * .12) throw Error('Missing sprite or transparency');
  return {left, top, width: right - left + 1, height: bottom - top + 1};
}

for (const group of ['worker', 'cast', 'backgrounds']) {
  const bytes = await fs.readFile(path.join(root, 'sources', `${group}.png`));
  const meta = await sharp(bytes).metadata();
  manifest.sources[group] = {file: `sources/${group}.png`, width: meta.width, height: meta.height, sha256: hash(bytes)};
  if (group === 'backgrounds') continue;
  if (!meta.hasAlpha) throw Error(`${group} has no alpha channel`);
  const rows = group === 'worker' ? 3 : 2;
  for (let i = 0; i < rows * 4; i++) {
    const col = i % 4, row = Math.floor(i / 4);
    // The sword crosses the uniform boundary; 474 is the observed empty gap
    // before the next hero. Use that gap, without copying a neighboring sprite.
    const columns = group === 'cast' ? [0, 474, 887, 1330, 1774]
      : Array.from({length:5}, (_, x) => Math.round(x * meta.width / 4));
    const left = columns[col];
    const top = Math.round(row * meta.height / rows);
    const right = columns[col + 1];
    const bottom = Math.round((row + 1) * meta.height / rows);
    const cell = await sharp(bytes).extract({left, top, width: right - left, height: bottom - top}).ensureAlpha().raw().toBuffer({resolveWithObject:true});
    const box = bounds(cell.data, cell.info.width, cell.info.height);
    if (box.left === 0 || box.top === 0 || box.left + box.width >= cell.info.width || box.top + box.height >= cell.info.height)
      throw Error(`${group} ${i}: art touches extraction edge ${JSON.stringify({box, size:cell.info})}`);
    const cropped = await sharp(cell.data, {raw: cell.info}).extract(box).png().toBuffer();
    const sprite = group === 'worker' ? cropped : await sharp(cropped).resize({width: 330, height: 330, fit: 'inside'}).png().toBuffer();
    const sm = await sharp(sprite).metadata();
    const x = group === 'worker' ? 18 : Math.round((canvas - sm.width) / 2);
    const y = 344 - sm.height;
    if (x < 0 || y < 4 || x + sm.width > canvas - 4) throw Error(`${group} ${i}: bad aligned bounds`);
    const result = await sharp({create:{width:canvas,height:canvas,channels:4,background:'#00000000'}})
      .composite([{input:sprite,left:x,top:y}]).png().toBuffer();
    const name = group === 'worker' ? `worker_${String(i).padStart(2, '0')}` : castNames[i];
    const file = `sprites/${name}.png`;
    await fs.writeFile(path.join(root, file), result);
    manifest.sprites[name] = {file, sha256:hash(result), source_cell:i,
      source_crop:{left:left+box.left,top:top+box.top,width:box.width,height:box.height},
      bounds:{left:x,top:y,width:sm.width,height:sm.height}};
  }
}
await fs.writeFile(path.join(root, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
console.log(JSON.stringify({sprites:Object.keys(manifest.sprites).length, sources:Object.keys(manifest.sources).length,
  worker_heights:Object.entries(manifest.sprites).filter(([n])=>n.startsWith('worker_')).map(([n,s])=>[n,s.bounds.height]),
  cast_bounds:Object.fromEntries(castNames.map(n=>[n,manifest.sprites[n].bounds]))}));
