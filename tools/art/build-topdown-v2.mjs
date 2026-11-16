import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = fileURLToPath(new URL('../../assets/topdown_v2/', import.meta.url));
const tile = 256;
const pairedTerrain = (a, b) => [
  `${a}_floor`, `${a}_floor_alt`, `${b}_floor`, `${b}_floor_alt`,
  `${a}_cap`, `${a}_face`, `${b}_cap`, `${b}_face`,
  `${a}_corner`, `${a}_rock`, `${b}_corner`, `${b}_rock`,
];
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
  workshop_finish_terrain: [
    'workshop_floor_ashlar', 'workshop_floor_slate', 'workshop_floor_scorched',
    'workshop_cap', 'workshop_face', 'workshop_corner',
    'workshop_rock', 'workshop_rock_chipped', 'workshop_plinth',
  ],
  workshop_finish_props: [
    'workshop_trap_broken', 'workshop_trap_installed', 'workshop_trap_active', 'workshop_exit_closed',
    'workshop_exit_ready', 'workshop_lever_off', 'workshop_lever_on', 'workshop_part',
    'workshop_anvil', 'workshop_lantern', 'workshop_candle_sconce', 'workshop_tool_rack',
  ],
  rooms_02_03: pairedTerrain('room_02', 'room_03'),
  rooms_04_05: pairedTerrain('room_04', 'room_05'),
  rooms_06_07: pairedTerrain('room_06', 'room_07'),
  room_08: [
    'room_08_floor', 'room_08_floor_alt', 'room_08_floor_inlay',
    'room_08_cap', 'room_08_face', 'room_08_corner',
    'room_08_rock', 'room_08_rock_alt', 'room_08_plinth',
  ],
  room_devices: [
    'depth_bone', 'depth_soldier_carried', 'depth_soldier_deployed', 'depth_post_empty',
    'depth_bench_empty', 'depth_bench_bone', 'depth_plate_up', 'depth_plate_down',
    null, null, 'depth_rubble', 'depth_chute_outlet',
  ],
  room_magic: [
    'depth_chute_inlet', 'depth_source', 'depth_receiver', 'depth_mirror_base',
    'depth_winch', 'depth_helper', 'depth_crystal_sconce', 'depth_lantern',
    'depth_candle_sconce', 'depth_air_vent', 'depth_wall_pipes', 'depth_crest',
  ],
  room_decor: [
    'depth_sarcophagus', 'depth_candles', 'depth_books', 'depth_throne',
    'depth_hand_pump', 'depth_elbow_pipe', 'depth_water_barrel', 'depth_brazier',
    'depth_treasure', 'depth_treasure_banner', 'depth_crypt_banner', 'depth_archive_banner',
  ],
  device_mechanisms: [
    'workshop_trap_broken', 'workshop_trap_installed', 'workshop_trap_active',
    'workshop_lever_off', 'workshop_lever_on', 'workshop_exit_closed',
    'workshop_exit_ready', 'depth_plate_up', 'depth_plate_down',
  ],
  device_fixtures: [
    null, null, 'depth_rubble', 'depth_post_empty',
    'depth_bench_empty', 'depth_bench_bone', 'depth_chute_inlet', 'depth_chute_outlet',
  ],
  device_magic: [
    'depth_source', 'depth_receiver', 'depth_receiver_powered',
    'depth_mirror_base', null, 'replay_seal',
  ],
  device_recording: ['recording_plate', 'recording_plate_active'],
  device_gates: ['depth_gate_open', 'depth_gate_panel'],
};
const sheetColumns = {
  workshop_finish_terrain: 3, room_08: 3, device_mechanisms: 3, device_magic: 3,
  device_recording: 2, device_gates: 2,
};
const terrainSheets = new Set(['terrain', 'workshop_finish_terrain', 'rooms_02_03',
  'rooms_04_05', 'rooms_06_07', 'room_08']);
// 투명 여백의 중심에서 자른다. 생성 원화에 따라 위아래 여백이 균등하지 않다.
const sourceCuts = {
  rooms_02_03: [[319, 627, 933], [466, 807]],
  rooms_04_05: [[322, 626, 934], [448, 787]],
  rooms_06_07: [[319, 627, 934], [480, 827]],
  room_08: [[429, 824], [430, 822]],
  room_devices: [[315, 635, 924], [454, 828]],
  room_magic: [[367, 762, 1075], [368, 722]],
  room_decor: [[344, 624, 925], [423, 801]],
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
  const columns = sheetColumns[name] ?? 4;
  const rows = names.length / columns;
  const terrain = terrainSheets.has(name);
  const [xCuts, yCuts] = sourceCuts[name] ?? [
    Array.from({ length: columns - 1 }, (_, index) => Math.floor((index + 1) * width / columns)),
    Array.from({ length: rows - 1 }, (_, index) => Math.floor((index + 1) * height / rows)),
  ];
  const xs = [0, ...xCuts, width];
  const ys = [0, ...yCuts, height];
  const layers = [];
  for (const [index, key] of names.entries()) {
    if (key === null) continue;
    const col = index % columns;
    const row = Math.floor(index / columns);
    const left = xs[col];
    const top = ys[row];
    const cell = { left, top, width: xs[col + 1] - left, height: ys[row + 1] - top };
    const { data, info } = await source.clone().extract(cell).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    let bounds;
    try {
      bounds = cleanAlpha(data, info.width, info.height);
    } catch (error) {
      throw new Error(`${name}/${key}: ${error.message}`, { cause: error });
    }
    if (terrain) {
      bounds.left += 8;
      bounds.top += 8;
      bounds.width -= 16;
      bounds.height -= 16;
    }
    // 레버가 움직여도 본체가 같은 높이와 크기로 보이도록 두 상태를 같은 틀로 자른다.
    if (name === 'device_mechanisms' && key.startsWith('workshop_lever_')) {
      bounds.top = 28;
      bounds.height = 322;
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
  await sharp({ create: { width: tile * columns, height: tile * rows, channels: 4, background: '#00000000' } })
    .composite(layers).png().toFile(path.join(root, relative));
  manifest.atlases[name] = relative;
}

await mkdir(path.join(root, 'atlases'), { recursive: true });
const manifest = { atlases: {}, sprites: {} };
for (const [name, sprites] of Object.entries(sheets)) await packSheet(name, sprites, manifest);
await writeFile(path.join(root, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
console.log(`${Object.keys(manifest.sprites).length} sprites packed into ${Object.keys(sheets).length} atlases.`);
