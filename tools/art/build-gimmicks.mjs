// 이미지 생성 원본의 투명 여백 정리·크기 정렬·아틀라스 포장만 수행한다.
import sharp from 'sharp';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
const root = path.resolve(import.meta.dirname, '../../assets/gimmicks_v1');
const specs = [
  ['mirror', 150, 174], ['valve', 128, 158], ['push_rubble', 164, 158],
  ['helper_work', 176, 178], ['mana_source', 140, 112], ['mana_receiver', 124, 142],
  ['water', 224, 112], ['float_bridge', 224, 126], ['winch', 122, 128],
];
await fs.mkdir(path.join(root, 'sprites'), {recursive:true});
const sprites={}, composite=[], preview=[];
for (let i=0; i<specs.length; i++) {
  const [id,w,h]=specs[i];
  const source=path.join(root,'sources',id+'.png');
  const original=await sharp(source).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  let x0=original.info.width,y0=original.info.height,x1=0,y1=0, transparent=0;
  for(let y=0;y<original.info.height;y++) for(let x=0;x<original.info.width;x++) {
    const a=original.data[(y*original.info.width+x)*4+3];
    if(a>8){x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y);} else transparent++;
  }
  if(!transparent || x1<=x0) throw Error(id+': transparent silhouette missing');
  const tile=id==='water'||id==='float_bridge';
  const resized=await sharp(source).extract({left:x0,top:y0,width:x1-x0+1,height:y1-y0+1})
    .resize(w,h,{fit:tile?'fill':'inside'}).png().toBuffer({resolveWithObject:true});
  const left=Math.round((256-resized.info.width)/2),top=tile?104:220-resized.info.height;
  const buffer=await sharp({create:{width:256,height:256,channels:4,background:'#00000000'}})
    .composite([{input:resized.data,left,top}]).png().toBuffer();
  await fs.writeFile(path.join(root,'sprites',id+'.png'),buffer);
  const col=i%3,row=Math.floor(i/3);
  composite.push({input:buffer,left:col*256,top:row*256});
  preview.push({input:buffer,left:col*280+12,top:row*290+16});
  sprites[id]={file:'sprites/'+id+'.png',width:256,height:256,anchor:{x:128,y:tile?160:210},
    atlas:'gimmicks',clip_rect_pico2d:[col*256,768-(row+1)*256,256,256],
    content_rect:{left,top,width:resized.info.width,height:resized.info.height},
    sha256:crypto.createHash('sha256').update(buffer).digest('hex')};
}
await sharp({create:{width:768,height:768,channels:4,background:'#00000000'}}).composite(composite).png().toFile(path.join(root,'atlas.png'));
await sharp({create:{width:840,height:870,channels:4,background:'#26353c'}}).composite(preview).png().toFile(path.join(root,'overview.png'));
await fs.writeFile(path.join(root,'manifest.json'),JSON.stringify({atlases:{gimmicks:{file:'atlas.png',width:768,height:768}},sprites},null,2)+'\n');
console.log('9 RGBA sprites, alpha bounds checked, 768x768 atlas');
