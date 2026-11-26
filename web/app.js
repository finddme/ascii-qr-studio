'use strict';
const $ = id => document.getElementById(id);
let image = null, imageData = null, crop = null, start = null, reuse = null;
let current = null, view = 'color', busy = false, loadingImage = false, baseline = null;
let originalUrl=null, originalJob=null;
const names = {ready:'Verified', failed:'Decode check failed', error:'Conversion error', running:'Interrupted'};
const selection = () => ({url:$('url').value, columns:Number($('columns').value), min_version:Number($('version').value), fit:$('fit').value, crop});
const signature = () => JSON.stringify({source:reuse || imageData, ...selection()});
function status(text, error=false) { $('status').textContent=text; $('status').classList.toggle('error',error); }
function state(text, kind='') { $('result-state').textContent=text; $('result-state').dataset.state=kind; }
function markDirty() { held=null; $('dirty').hidden=!(current?.status==='ready' && baseline!==signature()); refreshBanner(); }
function lock(value) {
  busy=value; $('editor').disabled=value; $('rerun').disabled=value;
  $('crop').tabIndex=value?-1:0;
  document.querySelector('.results').setAttribute('aria-busy',String(value));
  document.querySelectorAll('.open-job,.delete').forEach(b=>b.disabled=value);
  $('generate-label').textContent=value?'Generating & checking…':'Make ASCII QR';
  if(!value)refreshBanner();
}
let animateNext=false,held=null;
function readiness(){ return (imageData||reuse)&&$('url').value&&$('url').checkValidity()?'ready':'idle'; }
function refreshBanner(){ if(busy)return; window.fx?.banner(held||current?.status==='ready'&&baseline===signature()?'done':readiness()); }
function point(e) { const r=$('crop').getBoundingClientRect(); return [Math.min(1,Math.max(0,(e.clientX-r.left)/r.width)),Math.min(1,Math.max(0,(e.clientY-r.top)/r.height))]; }
function draw() {
  if(!image)return;
  const c=$('crop'),ctx=c.getContext('2d'); c.width=600; c.height=Math.round(600*image.height/image.width);
  ctx.drawImage(image,0,0,c.width,c.height);
  if(crop) { const [l,t,r,b]=crop; ctx.fillStyle='#0009';ctx.fillRect(0,0,c.width,c.height);ctx.save();ctx.beginPath();ctx.rect(l*c.width,t*c.height,(r-l)*c.width,(b-t)*c.height);ctx.clip();ctx.drawImage(image,0,0,c.width,c.height);ctx.restore();ctx.strokeStyle='#eba6cb';ctx.lineWidth=4;ctx.strokeRect(l*c.width,t*c.height,(r-l)*c.width,(b-t)*c.height); }
  $('crop-label').textContent=crop?'Selection: '+crop.map(v=>Math.round(v*100)+'%').join(' / '):'Using the full image';
}
async function loadImage(src) {
  const im=new Image(); await new Promise((resolve,reject)=>{im.onload=resolve;im.onerror=()=>reject(new Error('Could not open this image. Try a PNG or JPG.'));im.src=src;});
  image=im; $('crop-area').hidden=false; draw();
}
$('file').addEventListener('change',async()=>{
  const file=$('file').files[0];if(!file||busy)return;
  loadingImage=true; lock(true);
  try {
    if(file.size>12*1024*1024)throw new Error('Choose an image of 12 MB or less.');
    const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(new Error('Could not read the file. Please choose it again.'));r.readAsDataURL(file);});
    await loadImage(data);imageData=data.split(',')[1];reuse=null;crop=null;draw();window.fx?.tray(1,data);window.fx?.tray(2);window.fx?.tray(3);$('file-name').textContent=file.name;markDirty();status('Image loaded. Pick an area or generate right away.');
  } catch(e) { $('file').value='';status(e.message,true); }
  finally { loadingImage=false;lock(false); }
});
$('crop').addEventListener('pointerdown',e=>{if(busy)return;start=point(e);$('crop').setPointerCapture(e.pointerId);});
$('crop').addEventListener('pointermove',e=>{if(!start||busy)return;const p=point(e);crop=[Math.min(start[0],p[0]),Math.min(start[1],p[1]),Math.max(start[0],p[0]),Math.max(start[1],p[1])];draw();});
function finish() { if(!start)return;if(crop&&(crop[2]-crop[0]<.02||crop[3]-crop[1]<.02))crop=null;start=null;draw();markDirty(); }
$('crop').addEventListener('pointerup',finish);$('crop').addEventListener('pointercancel',finish);
$('crop').addEventListener('keydown',e=>{
  if(busy||!image)return;
  if(e.key==='Escape'){e.preventDefault();crop=null;draw();markDirty();return;}
  if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;
  e.preventDefault();let [l,t,r,b]=crop||[.1,.1,.9,.9];const dx=e.key==='ArrowLeft'?-.02:e.key==='ArrowRight'?.02:0,dy=e.key==='ArrowUp'?-.02:e.key==='ArrowDown'?.02:0;
  if(e.shiftKey){r=Math.max(l+.04,Math.min(1,r+dx));b=Math.max(t+.04,Math.min(1,b+dy));}
  else { const x=Math.max(-l,Math.min(1-r,dx)),y=Math.max(-t,Math.min(1-b,dy));l+=x;r+=x;t+=y;b+=y; }
  crop=[l,t,r,b].map(v=>Math.round(v*10000)/10000);draw();markDirty();
});
$('reset-crop').onclick=()=>{crop=null;draw();markDirty();};
$('columns').oninput=()=>{$('columns-value').textContent=$('columns').value+' cols';markDirty();};
for(const id of ['url','fit','version'])$(id).addEventListener('input',markDirty);
async function showView() {
  if(!current||current.status!=='ready')return;
  const paths={original:'ascii/source.png',ascii:'ascii/color.png',color:'selected-color.png',mono:'selected-mono.png'};
  const src=`/files/${current.id}/result/${paths[view]}`;
  let displaySrc=src;
  if(view==='original') {
    const id=current.id;
    try {
      const response=await fetch(`/files/${id}/result/ascii/preview.html`);
      if(!response.ok)throw new Error('Could not load the original preview.');
      const doc=new DOMParser().parseFromString(await response.text(),'text/html');
      displaySrc=doc.querySelector('figure img')?.getAttribute('src');
      if(!displaySrc?.startsWith('data:image/'))throw new Error('Original preview not found.');
      if(current?.id!==id||view!=='original')return;
      if(originalJob!==id){
        const [header,encoded]=displaySrc.split(',');
        const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));
        const blob=new Blob([bytes],{type:header.slice(5,header.indexOf(';'))});
        if(current?.id!==id||view!=='original')return;
        if(originalUrl)URL.revokeObjectURL(originalUrl);
        originalUrl=URL.createObjectURL(blob);originalJob=id;
      }
      displaySrc=originalUrl;
    }catch(e){status(e.message,true);return;}
  }
  $('result-image').src=displaySrc;$('image-link').href=displaySrc;
  const short=current.id.slice(0,8),file={original:'original',ascii:'ascii',color:'qr-color',mono:'qr-bw'}[view];
  $('download-view').href=displaySrc;$('download-view').download=`ascii-qr-${short}-${file}.png`;
  $('download-view-label').textContent={original:'Download original',ascii:'Download ASCII',color:'Download Color QR',mono:'Download B&W QR'}[view]+' (PNG)';
  $('result-image').alt={original:'Original image with crop and fit applied',ascii:'Image converted to ASCII characters',color:'Color ASCII QR',mono:'Black-and-white ASCII QR'}[view];
  $('result-image').classList.toggle('art-view',['original','ascii'].includes(view));
  // Match the artwork region to the QR's four-module quiet zone at every size.
  sizePreview();
  const fresh=animateNext;animateNext=false;
  const q=current.qr_modules||41;
  window.fx?.assemble($('result-image'),['color','mono'].includes(view)?(fresh?{cells:q+8}:{cells:q+8,spread:.12,dur:260,stagger:240}):{cells:fresh?40:24,spread:fresh?.5:.12,dur:fresh?520:260,stagger:fresh?600:240});
  document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));
}
function sizePreview(){
  const stage=document.querySelector('.image-stage');
  const size=Math.min(stage.clientWidth,stage.clientHeight);
  if(!size)return;
  const img=$('result-image');img.style.width=size+'px';img.style.height=size+'px';
  img.style.setProperty('--art-inset',(4/((current?.qr_modules||41)+8)*size)+'px');
}
new ResizeObserver(sizePreview).observe(document.querySelector('.image-stage'));
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{view=b.dataset.view;showView();});
function showResult(job) {
  current=job;baseline=signature();$('dirty').hidden=true;
  if(job.status!=='ready') {
    $('result').hidden=true;$('empty').hidden=false;
    state(names[job.status]||'No result','error');
    const message=job.status==='failed'?'No candidate passed every decode check. Change the area or QR density and try again.':'The conversion did not finish. Check the image and settings, then try again.';
    $('empty-title').textContent=names[job.status]||'Could not finish generating.';$('empty-copy').textContent=message;status(message,true);window.fx?.tray(2);window.fx?.tray(3);held='error';return;
  }
  $('empty').hidden=true;$('result').hidden=false;state(`Decode checks ${job.checks}/14 passed`,'ready');
  $('result-info').textContent=`${job.settings.columns} cols · QR ${job.qr_modules} × ${job.qr_modules} · ${job.settings.url}`;
  $('download').href=`/api/jobs/${job.id}/download`;$('report').href=`/files/${job.id}/result/preview.html`;
  animateNext=true;showView();
  window.fx?.tray(2,`/files/${job.id}/result/ascii/color.png`);setTimeout(()=>{if(current?.id===job.id)window.fx?.tray(3,`/files/${job.id}/result/selected-color.png`);},450);
}
async function openJob(job) {
  if(busy)return;lock(true);
  try {
    await loadImage(`/files/${job.id}/input.png`);window.fx?.tray(1,`/files/${job.id}/input.png`);
    reuse=job.id;imageData=null;$('file').value='';crop=job.settings.crop;$('url').value=job.settings.url;
    $('columns').value=job.settings.columns;$('columns-value').textContent=job.settings.columns+' cols';$('fit').value=job.settings.fit;
    // Older/API jobs may use versions not present in the standard presets.
    if(![...$('version').options].some(o=>o.value===String(job.settings.min_version))){const o=new Option('Custom · '+job.settings.min_version,job.settings.min_version);$('version').add(o);}
    $('version').value=job.settings.min_version;$('file-name').textContent='Saved input image';draw();showResult(job);
    if(job.status==='ready')status('Saved job loaded. Change the settings to generate again.');
    document.querySelector('.results').scrollIntoView({block:'start'});
  }finally{lock(false);}
}
async function history() {
  const response=await fetch('/api/jobs');if(!response.ok)throw new Error('Could not load history. Refresh and try again.');
  const jobs=await response.json();$('history-count').textContent=jobs.length;$('history').replaceChildren();
  if(!jobs.length){const p=document.createElement('p');p.className='hint';p.textContent='Your designs will be saved here.';$('history').append(p);return;}
  for(const job of jobs){
    const row=document.createElement('div');row.className='job';
    const open=document.createElement('button');open.type='button';open.className='open-job';open.disabled=busy;
    const img=document.createElement('img');img.src=`/files/${job.id}/${job.status==='ready'?'result/selected-color.png':'input.png'}`;img.alt='';img.loading='lazy';
    const copy=document.createElement('div');copy.className='job-copy';const title=document.createElement('span');title.textContent=new Date(job.created).toLocaleString('en-US',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});const badge=document.createElement('em');badge.textContent=names[job.status]||'No result';
    const url=document.createElement('small');url.textContent=job.settings.url;copy.append(title,badge,url);open.append(img,copy);open.onclick=()=>openJob(job).catch(e=>status(e.message,true));
    const del=document.createElement('button');del.type='button';del.className='delete';del.textContent='Delete';del.disabled=busy;del.setAttribute('aria-label','Delete job '+job.id.slice(0,8));
    del.onclick=async()=>{
      if(busy||!confirm('Delete this job\'s input image and results?'))return;
      try{const res=await fetch('/api/jobs/'+job.id,{method:'DELETE'});if(!res.ok)throw new Error('Could not delete. Try again after the conversion finishes.');
        if(current?.id===job.id){current=null;baseline=null;$('dirty').hidden=true;$('result').hidden=true;$('empty').hidden=false;$('empty-title').textContent='Waiting for a new image';$('empty-copy').textContent='Add an image and a URL to make the next design.';state('Waiting for input');}
        if(current===null){window.fx?.tray(2);window.fx?.tray(3);}
        if(reuse===job.id){reuse=null;image=null;imageData=null;crop=null;$('crop-area').hidden=true;window.fx?.tray(1);$('file-name').textContent='PNG · JPG · WebP · GIF / up to 12 MB';}
        await history();refreshBanner();status('Job deleted.');
      }catch(e){status(e.message,true);}
    };row.append(open,del);$('history').append(row);
  }
}
async function generate() {
  if(busy||loadingImage)return;
  if(!imageData&&!reuse){status('Choose an image first.',true);$('file').focus();return;}
  if(!$('form').reportValidity())return;
  const payload={image:imageData,reuse,...selection()};held=null;lock(true);window.fx?.banner('busy');state('Generating & checking','busy');status('Running the ASCII conversion and QR decode checks. Please wait.');
  try {
    const response=await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const job=await response.json();
    if(!response.ok)throw new Error(response.status===409?'Another conversion is running. Try again in a moment.':response.status===400?'The image could not be processed or the settings are invalid. Images must be 12 MB / 24 MP or less, and the URL must start with http or https.':'The conversion request failed. Check that the server is running and try again.');
    showResult(job);if(job.status==='ready'){status('Done. Compare the views, then download the one you are looking at, or all files as a ZIP.');if(matchMedia('(max-width:720px)').matches)document.querySelector('.results').scrollIntoView({block:'start'});}
    await history();
  } catch(e) { status(e.message,true);state('Request failed · try again','error');held='error'; }
  finally { lock(false); }
}
$('form').onsubmit=e=>{e.preventDefault();generate();};$('rerun').onclick=generate;
history().catch(e=>status(e.message,true));
