// Package image_gen layers without changing their artwork or alpha.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import sharp from 'sharp';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../assets/title_motion_v1');
const hash=data=>crypto.createHash('sha256').update(data).digest('hex');
const manifest={version:1,generator:'built-in image_gen',sources:{},sprites:{}};
await fs.mkdir(path.join(root,'sprites'),{recursive:true});
for(const name of ['background','logo','characters','flames']) {
  const bytes=await fs.readFile(path.join(root,`sources/${name}.png`));
  const meta=await sharp(bytes).metadata();
  manifest.sources[name]={file:`sources/${name}.png`,width:meta.width,height:meta.height,sha256:hash(bytes)};
  if(name==='background')continue;
  const count=name==='logo'?1:8,cols=count===1?1:4,rows=count===1?1:2;
  for(let i=0;i<count;i++) {
    const left=Math.round(i%cols*meta.width/cols),right=Math.round((i%cols+1)*meta.width/cols);
    const top=Math.round(Math.floor(i/cols)*meta.height/rows),bottom=Math.round((Math.floor(i/cols)+1)*meta.height/rows);
    const crop={left,top,width:right-left,height:bottom-top};
    const {data,info}=await sharp(bytes).extract(crop).ensureAlpha().raw().toBuffer({resolveWithObject:true});
    let x0=info.width,y0=info.height,x1=-1,y1=-1,empty=0;
    for(let y=0;y<info.height;y++)for(let x=0;x<info.width;x++) {
      const a=data[(y*info.width+x)*4+3];
      if(a===0)empty++;
      if(a>24){x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y);}
    }
    if(empty<info.width*info.height*.15 || x0<3 || y0<3 || x1>=info.width-3 || y1>=info.height-3)
      throw Error(`Invalid transparent margin: ${name}/${i} ${JSON.stringify({x0,y0,x1,y1})}`);
    const id=name==='logo'?'logo':name==='flames'?`flame_${i}`:i<4?`skeleton_${i}`:`worker_${i-4}`;
    const file=`sprites/${id}.png`;
    const output=await sharp(data,{raw:info}).png().toBuffer();
    await fs.writeFile(path.join(root,file),output);
    manifest.sprites[id]={file,width:info.width,height:info.height,sha256:hash(output),crop,
      bounds:{left:x0,top:y0,width:x1-x0+1,height:y1-y0+1},anchor:[info.width/2,y1+1]};
  }
}
if(new Set(Object.values(manifest.sprites).map(s=>s.sha256)).size!==17)throw Error('Duplicate pose');
await fs.writeFile(path.join(root,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({sources:4,sprites:17,validated:'alpha, margins, unique poses, hashes'}));
