/* Canvas-only artwork: identical preview and export, no external fonts or services. */
const SOCIAL = {width:1080,height:1440,top:296,bottom:1290,gap:14,font:'"Microsoft YaHei", "PingFang SC", sans-serif'};
function artFont(g,size,weight=400){g.font=`${weight} ${size}px ${SOCIAL.font}`;}
function wrapArt(g,text,width){let lines=[],line='';for(const c of String(text||'')){if(line&&g.measureText(line+c).width>width){lines.push(line);line=c;}else line+=c;}if(line)lines.push(line);return lines.length?lines:['—'];}
function otcLayout(row,g){artFont(g,29,700);const lines=wrapArt(g,row.name,824);return {row,lines,height:174+(lines.length-1)*36};}
function socialPages(rows,index){
 const g=document.createElement('canvas').getContext('2d'), groups=[];let group=[],used=0;
 for(const row of fundSort(rows)){const item=otcLayout(row,g);if(group.length&&used+SOCIAL.gap+item.height>SOCIAL.bottom-SOCIAL.top){groups.push(group);group=[];used=0;}group.push(item);used+=item.height+(group.length>1?SOCIAL.gap:0);}
 if(group.length)groups.push(group);
 // Balance a sparse tail while preserving the exact company/fund ordering.
 const minimum=Math.min(4,Math.floor(rows.length/Math.max(1,groups.length)));
 for(let i=groups.length-1;i>0;i--){while(groups[i].length<minimum&&groups[i-1].length>1){
  const item=groups[i-1][groups[i-1].length-1],height=groups[i].reduce((n,x)=>n+x.height,0)+groups[i].length*SOCIAL.gap+item.height;
  if(height>SOCIAL.bottom-SOCIAL.top)break;
  groups[i].unshift(groups[i-1].pop());
 }}
 return groups.map((items,i)=>({type:'otc',index,rows:items.map(x=>x.row),items,part:i+1,total:groups.length,count:rows.length}));
}
function rounded(g,x,y,w,h,r,color){g.fillStyle=color;g.beginPath();g.roundRect(x,y,w,h,r);g.fill();}
function ink(g,text,x,y,size=24,weight=400,color='#242b29'){artFont(g,size,weight);g.fillStyle=color;g.fillText(String(text),x,y);}
function signedReturn(v){return v==null?'—':`${v>=0?'+':''}${Number(v).toFixed(2)}%`;}
function quotaArt(v){return typeof v==='number'?v.toLocaleString('zh-CN',{maximumFractionDigits:2}):v==null?'待核验':String(v);}
function drawSocialOTC(p){
 const c=document.createElement('canvas');c.width=SOCIAL.width;c.height=SOCIAL.height;const g=c.getContext('2d');
 g.fillStyle='#f4f1e9';g.fillRect(0,0,1080,1440);
 rounded(g,54,46,8,25,4,'#ca623f');ink(g,'QDII DAILY  /  每日申购观察',78,67,23,600,'#617068');
 rounded(g,806,40,220,49,24,'#e6e8dd');ink(g,D.date||'日期待核验',835,72,25,600,'#3b5548');
 ink(g,p.index==='纳指100'?'纳斯达克100':'标普500',54,158,69,800);
 ink(g,'场外申购额度',57,219,39,600,'#476452');
 ink(g,`${p.count} 只基金  ·  同公司连续排列  ·  额度：元 / 日`,58,264,22,400,'#73786e');
 let y=SOCIAL.top;
 for(const item of p.items){const r=item.row,h=item.height;
  rounded(g,54,y,972,h,21,'#ffffff');
  const active=quotaNum(r.agency_limit)+quotaNum(r.direct_limit)>0;
  rounded(g,54,y+22,5,h-44,2,active?'#5b806a':'#d9ded6');
  item.lines.forEach((line,j)=>ink(g,line,82,y+40+j*36,29,700));
  const shift=(item.lines.length-1)*36;
  ink(g,`${r.code}  /  ${r.fund_company||'基金公司待核验'}`,83,y+71+shift,20,500,'#858a80');
  rounded(g,917,y+20,80,33,16,'#f0f3ed');ink(g,`${r.share_class||'—'} 类`,935,y+43,19,600,'#52705c');
  const base=y+shift;
  ink(g,'代销额度',83,base+110,20,400,'#7a8176');
  ink(g,quotaArt(r.agency_limit),83,base+153,35,700,quotaNum(r.agency_limit)>0?'#365f47':'#94978f');
  ink(g,'直销额度',358,base+110,20,400,'#7a8176');
  ink(g,quotaArt(r.direct_limit),358,base+153,35,700,quotaNum(r.direct_limit)>0?'#365f47':'#94978f');
  g.strokeStyle='#eceee8';g.beginPath();g.moveTo(630,base+97);g.lineTo(630,base+154);g.stroke();
  ink(g,'年费率',666,base+110,20,400,'#7a8176');ink(g,r.fee_annual==null?'—':`${Number(r.fee_annual).toFixed(2)}%`,666,base+149,27,600);
  ink(g,'近 1 年',834,base+110,20,400,'#7a8176');ink(g,signedReturn(r.return_1y),834,base+149,27,600,'#526d59');
  y+=h+SOCIAL.gap;
 }
 g.strokeStyle='#d6dbd0';g.beginPath();g.moveTo(56,1322);g.lineTo(1024,1322);g.stroke();
 ink(g,'来源：qdiilimit · 天天基金公开资料',57,1360,20,400,'#7a8175');
 ink(g,'以实际销售渠道为准 · 历史收益不代表未来 · 不构成投资建议',57,1398,19,400,'#7a8175');
 ink(g,`${String(p.part).padStart(2,'0')} / ${String(p.total).padStart(2,'0')}`,896,1363,28,700,'#476452');
 return c;
}
let exportItems=[];
async function previewNasdaq(){await document.fonts.ready;openExport(pages().filter(p=>p.type==='otc'&&p.index==='纳指100'));}
async function previewCurrent(){await document.fonts.ready;const label=currentIndex==='nasdaq100'?'纳指100':'标普500';openExport(pages().filter(p=>p.type===currentType&&p.index===label));}
function exportFilename(p){return `${D.date||'QDII'}-${p.index}-${p.type==='otc'?'场外':'场内'}-${String(p.part).padStart(2,'0')}.png`;}
function saveBlob(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}
function canvasBlob(canvas){return new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('图片生成失败')),'image/png'));}
function openExport(ps){
 if(!ps.length){alert('当前没有可生成的数据，请先更新。');return;}
 const grid=$('exportGrid');grid.replaceChildren();exportItems=[];
 for(const p of ps){const canvas=drawPage(p),card=document.createElement('article');card.className='export-card';card.append(canvas);
  const button=document.createElement('button');button.className='ghost';button.textContent=`下载 ${p.index} · 第 ${p.part} / ${p.total} 张`;button.onclick=async()=>saveBlob(await canvasBlob(canvas),exportFilename(p));card.append(button);grid.append(card);exportItems.push({p,canvas});}
 $('exportCount').textContent=`${ps.length} 张 · 1080 × 1440 · 按内容长度自动分页`;
 if(!$('exportDialog').open)$('exportDialog').showModal();
}
// Uncompressed ZIP keeps every PNG byte intact and avoids third-party dependencies.
function crc32(bytes){let crc=0xffffffff;for(const b of bytes){crc^=b;for(let i=0;i<8;i++)crc=(crc>>>1)^((crc&1)?0xedb88320:0);}return (crc^0xffffffff)>>>0;}
function zipPngs(files){const encoder=new TextEncoder(),parts=[],directory=[];let offset=0,dirSize=0;
 for(const file of files){const name=encoder.encode(file.name),data=file.data,crc=crc32(data),local=new Uint8Array(30+name.length),v=new DataView(local.buffer);
  v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,0x800,true);v.setUint32(14,crc,true);v.setUint32(18,data.length,true);v.setUint32(22,data.length,true);v.setUint16(26,name.length,true);local.set(name,30);
  const central=new Uint8Array(46+name.length),d=new DataView(central.buffer);d.setUint32(0,0x02014b50,true);d.setUint16(4,20,true);d.setUint16(6,20,true);d.setUint16(8,0x800,true);d.setUint32(16,crc,true);d.setUint32(20,data.length,true);d.setUint32(24,data.length,true);d.setUint16(28,name.length,true);d.setUint32(42,offset,true);central.set(name,46);
  parts.push(local,data);directory.push(central);offset+=local.length+data.length;dirSize+=central.length;
 }
 const end=new Uint8Array(22),v=new DataView(end.buffer);v.setUint32(0,0x06054b50,true);v.setUint16(8,files.length,true);v.setUint16(10,files.length,true);v.setUint32(12,dirSize,true);v.setUint32(16,offset,true);
 return new Blob([...parts,...directory,end],{type:'application/zip'});
}
async function downloadExport(){const button=$('downloadExport');button.disabled=true;button.textContent='正在打包…';try{const files=[];for(const {p,canvas} of exportItems)files.push({name:exportFilename(p),data:new Uint8Array(await(await canvasBlob(canvas)).arrayBuffer())});saveBlob(zipPngs(files),`${D.date||'QDII'}-基金发布图.zip`);}catch(e){alert('下载失败：'+e.message);}finally{button.disabled=false;button.textContent='下载整组图片（ZIP）';}}
