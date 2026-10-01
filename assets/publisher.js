/* Canvas-only artwork: identical preview and export, no external fonts or services. */
const SOCIAL = {width:1080,height:1440,top:296,bottom:1290,gap:14,font:'"Microsoft YaHei", "PingFang SC", sans-serif'};
function artFont(g,size,weight=400){g.font=`${weight} ${size}px ${SOCIAL.font}`;}
function wrapArt(g,text,width){let lines=[],line='';for(const c of String(text||'')){if(line&&g.measureText(line+c).width>width){lines.push(line);line=c;}else line+=c;}if(line)lines.push(line);return lines.length?lines:['—'];}
function socialPages(rows,index){
 const sorted=fundSort(rows),total=Math.ceil(sorted.length/15),perPage=Math.ceil(sorted.length/Math.max(1,total));
 const groups=[];for(let i=0;i<sorted.length;i+=perPage)groups.push(sorted.slice(i,i+perPage));
 return groups.map((rows,i)=>({type:'otc',index,rows,part:i+1,total:groups.length,count:sorted.length}));
}
const heroImage=new Image();heroImage.src='assets/nasdaq-hero-v1.png';
const heroReady=new Promise(resolve=>{heroImage.onload=resolve;heroImage.onerror=resolve;});
function rounded(g,x,y,w,h,r,color){g.fillStyle=color;g.beginPath();g.roundRect(x,y,w,h,r);g.fill();}
function ink(g,text,x,y,size=24,weight=400,color='#242b29'){artFont(g,size,weight);g.fillStyle=color;g.fillText(String(text),x,y);}
function signedReturn(v){return v==null?'—':`${v>=0?'+':''}${Number(v).toFixed(2)}%`;}
function quotaArt(v){return typeof v==='number'?v.toLocaleString('zh-CN',{maximumFractionDigits:2}):v==null?'待核验':String(v);}
function fitInk(g,text,x,y,width,size=26,weight=600,color='#15233b'){
 while(size>16){artFont(g,size,weight);if(g.measureText(String(text)).width<=width)break;size--;}
 ink(g,text,x,y,size,weight,color);
}
function drawSocialOTC(p){
 const c=document.createElement('canvas');c.width=1080;c.height=1440;const g=c.getContext('2d');
 g.fillStyle='#edf4ff';g.fillRect(0,0,1080,1440);
 if(heroImage.complete&&heroImage.naturalWidth)g.drawImage(heroImage,0,0,1080,270);else{g.fillStyle='#cfe8ff';g.fillRect(0,0,1080,270);}
 const fade=g.createLinearGradient(0,0,700,0);fade.addColorStop(0,'rgba(255,255,255,.96)');fade.addColorStop(.78,'rgba(255,255,255,.54)');fade.addColorStop(1,'rgba(255,255,255,0)');g.fillStyle=fade;g.fillRect(0,0,715,270);
 rounded(g,18,18,54,54,0,'#1267f4');ink(g,'↗',33,54,31,800,'#fff');ink(g,'纳斯达克100',43,99,62,800,'#082553');ink(g,'🇺🇸',435,94,36,400);ink(g,'QDII',43,153,50,800,'#082553');rounded(g,190,109,148,57,10,'#e3f1ff');ink(g,'ETF',204,153,48,800,'#1267f4');ink(g,'& 基金一览',354,153,43,800,'#082553');
 rounded(g,43,183,598,42,21,'rgba(255,255,255,.92)');ink(g,'一图看懂价格 · 涨跌 · 溢价 · 限额 · 直销/代销 · 近1年收益',60,212,20,800,'#152e5a');rounded(g,857,25,182,46,23,'#0d397b');g.textAlign='center';ink(g,(D.date||'—').replaceAll('-','/'),948,57,25,800,'#fff');g.textAlign='left';ink(g,'数据更新：北京时间 10:00',812,99,18,700,'#132b58');
 rounded(g,22,281,1036,148,22,'rgba(255,255,255,.95)');const etfs=D.etf||[],prem=etfs.filter(r=>typeof r.premium_pct==='number'),avg=prem.length?prem.reduce((s,r)=>s+r.premium_pct,0)/prem.length:null,topPremium=prem.reduce((a,r)=>!a||r.premium_pct>a.premium_pct?r:a,null),best=etfs.reduce((a,r)=>!a||(typeof r.return_1y==='number'&&r.return_1y>a.return_1y)?r:a,null);const stats=[['ETF数量（场内）',`${etfs.length} 只`,'实时行情 / T-1 溢价'],['平均 T-1 溢价',avg==null?'—':`${avg>=0?'+':''}${avg.toFixed(2)}%`,'公开汇总'],['最高 T-1 溢价',topPremium?`${topPremium.premium_pct>=0?'+':''}${topPremium.premium_pct.toFixed(2)}%`:'—',topPremium?`(${topPremium.code})`:''],['近1年最高收益',best?`${best.return_1y>=0?'+':''}${best.return_1y.toFixed(1)}%`:'—',best?`(${best.code})`:'']];stats.forEach((s,i)=>{const x=40+i*218;ink(g,s[0],x,320,18,700,'#14274b');fitInk(g,s[1],x,372,184,35,800,'#ed1733');ink(g,s[2],x,399,16,600,'#415979');g.strokeStyle='#d7e1ef';g.beginPath();g.moveTo(x+202,303);g.lineTo(x+202,414);g.stroke();});ink(g,'场外基金',915,320,18,700,'#14274b');ink(g,`${p.count} 只`,915,372,35,800,'#1267f4');ink(g,`第 ${p.part} / ${p.total} 张`,915,399,16,600,'#415979');
 const grad=g.createLinearGradient(22,446,1058,503);grad.addColorStop(0,'#7833f8');grad.addColorStop(.48,'#2d5cff');grad.addColorStop(1,'#75ccff');g.fillStyle=grad;g.fillRect(22,446,1036,57);ink(g,`▣  场外基金（共 ${p.count} 只）`,43,485,29,800,'#fff');g.textAlign='right';ink(g,'● 申购限额    ● 直销/代销    ● 年费率    ● 近1年收益',1037,483,17,800,'#fff');g.textAlign='left';
 /* Header artwork above intentionally mirrors the supplied reference layout. */
 g.fillStyle='#dff0ff';g.fillRect(22,503,1036,48);
 const xs=[45,58,499,644,789,911];['序号','基金名称（代码）','代销额度','直销额度','年费率','近1年收益'].forEach((v,i)=>ink(g,v,xs[i],534,18,800,'#112d5d'));
 const top=551,rowH=Math.min(51,748/Math.max(1,p.rows.length));let lastCompany=null,group=-1;
 for(let i=0;i<p.rows.length;i++){
  const r=p.rows[i],y=top+i*rowH,company=r.fund_company||r.code;
  if(company!==lastCompany){group++;lastCompany=company;}
  const bg=group%2===0?'#f8fbff':'#ffffff';rounded(g,22,y,1036,rowH,0,bg);
  if(i===0||company!==p.rows[i-1].fund_company){rounded(g,22,y+8,4,rowH-16,2,'#1267f4');}
  const baseline=y+31;ink(g,String(i+1+(p.part-1)*15),45,baseline,19,600);fitInk(g,`${r.name}（${r.code}）`,58,baseline,420,20,600);fitInk(g,quotaArt(r.agency_limit),499,baseline,132,20,700);fitInk(g,quotaArt(r.direct_limit),644,baseline,132,20,700);fitInk(g,r.fee_annual==null?'—':`${Number(r.fee_annual).toFixed(2)}%`,789,baseline,110,19,600);fitInk(g,signedReturn(r.return_1y),911,baseline,115,20,800,typeof r.return_1y==='number'&&r.return_1y>=0?'#ec1d37':'#1267f4');g.strokeStyle='#d9e6f4';g.beginPath();g.moveTo(22,y+rowH);g.lineTo(1058,y+rowH);g.stroke();
 }
 ink(g,'场外额度按基金公司总额度排序，同公司产品连续排列 · 单位：元/日',31,1363,17,600,'#61708a');ink(g,'公开数据整理，不构成投资建议。以实际销售渠道及基金公司公告为准。',31,1393,16,400,'#8793a8');
 return c;
}
let exportItems=[];
async function previewNasdaq(){await Promise.all([document.fonts.ready,heroReady]);openExport(pages().filter(p=>p.type==='otc'&&p.index==='纳指100'));}
async function previewCurrent(){await Promise.all([document.fonts.ready,heroReady]);const label=currentIndex==='nasdaq100'?'纳指100':'标普500';openExport(pages().filter(p=>p.type===currentType&&p.index===label));}
function exportFilename(p){return `${D.date||'QDII'}-${p.index}-${p.type==='otc'?'场外':'场内'}-${String(p.part).padStart(2,'0')}.png`;}
function saveBlob(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}
function canvasBlob(canvas){return new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('图片生成失败')),'image/png'));}
function openExport(ps){
 if(!ps.length){alert('当前没有可生成的数据，请先更新。');return;}
 const grid=$('exportGrid');grid.replaceChildren();exportItems=[];
 for(const p of ps){const canvas=drawPage(p),card=document.createElement('article');card.className='export-card';card.append(canvas);
  const button=document.createElement('button');button.className='ghost';button.textContent=`下载 ${p.index} · 第 ${p.part} / ${p.total} 张`;button.onclick=async()=>saveBlob(await canvasBlob(canvas),exportFilename(p));card.append(button);grid.append(card);exportItems.push({p,canvas});}
 $('exportCount').textContent=`${ps.length} 张 · 1080 × 1440 · 每张最多 15 只 · 紧凑榜单`;
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
