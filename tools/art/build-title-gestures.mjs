// Extract authored hand-wave poses; preserve source colors, alpha and scale.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import sharp from 'sharp';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../assets/title_gestures_v2');
const hash=data=>crypto.createHash('sha256').update(data).digest('hex');
const source=await fs.readFile(path.join(root,'sources/skeleton-wave.png'));
const meta=await sharp(source).metadata();
const manifest={version:2,source:{file:'sources/skeleton-wave.png',width:meta.width,height:meta.height,
  sha256:hash(source)},sprites:{}};
await fs.mkdir(path.join(root,'sprites'),{recursive:true});
for(let i=0;i<8;i++) {
  const left=Math.round(i%4*meta.width/4),right=Math.round((i%4+1)*meta.width/4);
  const top=Math.round(Math.floor(i/4)*meta.height/2),bottom=Math.round((Math.floor(i/4)+1)*meta.height/2);
  const crop={left,top,width:right-left,height:bottom-top};
  const {data,info}=await sharp(source).extract(crop).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  let x0=info.width,y0=info.height,x1=-1,y1=-1,empty=0;
  for(let y=0;y<info.height;y++)for(let x=0;x<info.width;x++) {
    const a=data[(y*info.width+x)*4+3];
    if(a===0)empty++;
    if(a>24){x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y);}
  }
  if(empty<info.width*info.height*.20 || x0<3 || y0<3 || x1>=info.width-3 || y1>=info.height-3)
    throw Error(`Invalid alpha or margin: pose ${i} ${JSON.stringify({x0,y0,x1,y1,empty})}`);
  const name=`wave_${i}`,file=`sprites/${name}.png`;
  const output=await sharp(data,{raw:info}).png().toBuffer();
  await fs.writeFile(path.join(root,file),output);
  manifest.sprites[name]={file,width:info.width,height:info.height,sha256:hash(output),crop,
    bounds:{left:x0,top:y0,width:x1-x0+1,height:y1-y0+1},anchor:[info.width/2,y1+1]};
}
if(new Set(Object.values(manifest.sprites).map(s=>s.sha256)).size!==8)throw Error('Duplicate pose');
await fs.writeFile(path.join(root,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({sprites:8,validated:'alpha, margins, unique poses, hashes'}));
