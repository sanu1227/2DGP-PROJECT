// Pack new authored poses; preserve all source files and within-shot proportions.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../assets/worker_motion_v2');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const manifest = {version:2, generator:'built-in image_gen', canvas:[362,362], anchor:[210,344],
  sources:{}, sprites:{}, groups:{}};
const groups = {};
await fs.mkdir(path.join(root, 'sprites'), {recursive:true});

function bounds(data, width, height) {
  let left=width, top=height, right=-1, bottom=-1, transparent=0;
  for(let y=0;y<height;y++) for(let x=0;x<width;x++) {
    const a=data[(y*width+x)*4+3];
    if(!a) transparent++;
    if(a>16) {left=Math.min(left,x);top=Math.min(top,y);right=Math.max(right,x);bottom=Math.max(bottom,y);}
  }
  if(right<left || transparent<width*height*.2) throw Error('Invalid transparent sprite');
  if(left<2 || top<2 || right>=width-2 || bottom>=height-2) throw Error(`Sprite touches cell border: ${JSON.stringify({left,top,right,bottom,width,height})}`);
  return {left,top,width:right-left+1,height:bottom-top+1};
}

for(const group of ['walk','settle','sigh']) {
  const sourceFile=`sources/${group==='walk' ? 'walk-refined' : group}.png`;
  const source=await fs.readFile(path.join(root,sourceFile));
  const meta=await sharp(source).metadata();
  if(!meta.hasAlpha) throw Error(`${group}: missing alpha`);
  manifest.sources[group]={file:sourceFile,width:meta.width,height:meta.height,sha256:hash(source)};
  groups[group]=[];
  for(let i=0;i<12;i++) {
    const left=Math.round(i%4*meta.width/4), right=Math.round((i%4+1)*meta.width/4);
    const top=Math.round(Math.floor(i/4)*meta.height/3), bottom=Math.round((Math.floor(i/4)+1)*meta.height/3);
    const raw=await sharp(source).extract({left,top,width:right-left,height:bottom-top}).ensureAlpha().raw().toBuffer({resolveWithObject:true});
    const box=bounds(raw.data,raw.info.width,raw.info.height);
    const png=await sharp(raw.data,{raw:raw.info}).extract(box).png().toBuffer();
    groups[group].push({png,box,crop:{left:left+box.left,top:top+box.top,width:box.width,height:box.height}});
  }
}

// Match equivalent contact/inhalation poses across sheets with ONE scale per
// sheet. Never normalize each pose's height: that would erase the final slump.
const scales={walk:315/groups.walk[0].box.height};
scales.settle=315/groups.settle[0].box.height;
scales.sigh=groups.settle[11].box.height*scales.settle/groups.sigh[0].box.height;
let frame=0;
for(const [group,poses] of Object.entries(groups)) {
  manifest.groups[group]={start:frame,count:12,scale:scales[group]};
  for(const pose of poses) {
    const height=Math.round(pose.box.height*scales[group]);
    const width=Math.round(pose.box.width*scales[group]);
    const x=18, y=344-height;
    if(y<4 || width+x>358) throw Error('Aligned pose exceeds its canvas');
    const png=await sharp(pose.png).resize(width,height).png().toBuffer();
    const output=await sharp({create:{width:362,height:362,channels:4,background:'#00000000'}})
      .composite([{input:png,left:x,top:y}]).png().toBuffer();
    const name=`worker_smooth_${String(frame).padStart(2,'0')}`;
    const file=`sprites/${name}.png`;
    await fs.writeFile(path.join(root,file),output);
    manifest.sprites[name]={file,sha256:hash(output),anchor:[210,344],group,source_crop:pose.crop,
      bounds:{left:x,top:y,width,height}};
    frame++;
  }
}
if(new Set(Object.values(manifest.sprites).map(s=>s.sha256)).size!==36) throw Error('Duplicate authored pose');
await fs.writeFile(path.join(root,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({frames:frame,scales,heights:Object.fromEntries(Object.entries(manifest.sprites).map(([n,s])=>[n,s.bounds.height]))}));
