// 생성한 후면 광원을 기존 광원의 크기에 맞춰 정렬한다. 배경 알파를 보존한다.
import sharp from 'sharp';
import fs from 'node:fs/promises';
import path from 'node:path';
const root = path.resolve(import.meta.dirname, '../../assets/gimmicks_v1/source-directions');
const resized = await sharp(path.join(root, 'source-up-generated.png')).trim()
  .resize(140, 112, {fit: 'inside'}).png().toBuffer({resolveWithObject: true});
const left = Math.round((256 - resized.info.width) / 2), top = 220 - resized.info.height;
await sharp({create: {width: 256, height: 256, channels: 4, background: '#00000000'}})
  .composite([{input: resized.data, left, top}]).png().toFile(path.join(root, 'source-up.png'));
await fs.writeFile(path.join(root, 'manifest.json'), JSON.stringify({
  atlases: {source_directions: {file: 'source-up.png', width: 256, height: 256}},
  sprites: {mana_source_up: {file: 'source-up.png', width: 256, height: 256,
    anchor: {x: 119, y: 210}, atlas: 'source_directions', clip_rect_pico2d: [0, 0, 256, 256],
    content_rect: {left, top, width: resized.info.width, height: resized.info.height}}}
}, null, 2) + '\n');
console.log('Rear light source: 256x256 RGBA, upright base and upper-right muzzle.');
