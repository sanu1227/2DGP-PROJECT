// Pack the two authored letter groups without altering their colors or alpha.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import sharp from 'sharp';

const projectRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const root=path.resolve(projectRoot, process.argv[2] || 'assets/splash_motion_v1');
const hash=data=>crypto.createHash('sha256').update(data).digest('hex');
const source=await fs.readFile(path.join(root,'sources/letters.png'));
const meta=await sharp(source).metadata();
const background=await fs.readFile(path.join(root,'sources/background.png'));
const backgroundMeta=await sharp(background).metadata();
const manifest={version:1,sources:{
  letters:{file:'sources/letters.png',width:meta.width,height:meta.height,sha256:hash(source)},
  background:{file:'sources/background.png',width:backgroundMeta.width,height:backgroundMeta.height,sha256:hash(background)}
},sprites:{}};
await fs.mkdir(path.join(root,'sprites'),{recursive:true});
for (const [index,name] of ['2d','gp'].entries()) {
  const left=Math.round(index*meta.width/2),right=Math.round((index+1)*meta.width/2);
  const crop={left,top:0,width:right-left,height:meta.height};
  const {data,info}=await sharp(source).extract(crop).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  let x0=info.width,y0=info.height,x1=-1,y1=-1,empty=0;
  for(let y=0;y<info.height;y++)for(let x=0;x<info.width;x++) {
    const alpha=data[(y*info.width+x)*4+3];
    if(alpha===0)empty++;
    if(alpha>24){x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y);}
  }
  if(x1<x0 || y1<y0 || empty<info.width*info.height*.20 || x0<8 || y0<8 || x1>=info.width-8 || y1>=info.height-8)
    throw Error(`Invalid alpha/margin: ${name} ${JSON.stringify({x0,y0,x1,y1,empty})}`);
  const file=`sprites/${name}.png`,output=await sharp(data,{raw:info}).png().toBuffer();
  await fs.writeFile(path.join(root,file),output);
  manifest.sprites[name]={file,width:info.width,height:info.height,sha256:hash(output),crop,
    bounds:{left:x0,top:y0,width:x1-x0+1,height:y1-y0+1}};
}
await fs.writeFile(path.join(root,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({sprites:manifest.sprites,validated:'alpha, margins, hashes'}));
