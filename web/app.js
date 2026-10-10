'use strict';
// FaceStudio AI v4 — camera-first; no cloud calls and no automatic camera start.
const $ = id => document.getElementById(id);
const state = {
  tab: 'live', mode: 'studio', filter: 'natural', morph: 'off', celebCount: 0, stream: null, session: 0, pending: null, nextFrame: null, renderHandle: null, renderAt: 0, agePoll: null,
  lastResult: null, failures: 0, models: null,
  photo: null, photoURL: null, report: null
};
let toastTimer;
const tabLabels = {
  live: ['Look different, <span>have fun.</span>', '10 live filters, face animations, age guessing and celebrity twins — on your own computer.'],
  photo: ['Discover your photo <span>insights.</span>', 'Upload a picture to see detected faces, estimated age ranges and photo quality.'],
  people: ['Your galleries, <span>your rules.</span>', 'Manage consenting face profiles and your fun celebrity references in one place.']
};
const emptyLive = '<div class="insight-empty"><div class="empty-emoji">✳</div><b>Waiting for your camera</b><p>Your results will show up here automatically.</p></div>';
const emptyPhoto = '<div class="insight-empty"><div class="empty-emoji">◇</div><b>Nothing analyzed yet</b><p>Upload a photo to get started.</p></div>';
function escapeHTML(value) { return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
function toast(message, isError=false) {
  const t=$('toast');t.textContent=message;t.className='toast show'+(isError?' error':'');
  clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.className='toast',4700);
}
async function api(path, options={}) {
  const res=await fetch(path,{cache:'no-store',...options});
  let data={};try{data=await res.json();}catch{}
  if(!res.ok) throw Error(typeof data.detail==='string'?data.detail:'Request failed ('+res.status+').');
  return data;
}
function switchTab(name) {
  if(!tabLabels[name])return;
  if(name!=='live')stopCamera();
  state.tab=name;
  for(const tab of document.querySelectorAll('.tab')){
    const current=tab.dataset.tab===name;
    tab.classList.toggle('active',current);
    if(current)tab.setAttribute('aria-current','page');else tab.removeAttribute('aria-current');
  }
  for(const page of document.querySelectorAll('.page'))page.classList.toggle('active',page.id==='page-'+name);
  $('pageTitle').innerHTML=tabLabels[name][0];$('pageDesc').textContent=tabLabels[name][1];
  if(name==='people'){refreshPeople();refreshCelebrities();}
}
for(const item of document.querySelectorAll('.tab'))item.addEventListener('click',()=>switchTab(item.dataset.tab));

async function loadStatus() {
  try{
    const r=await api('/api/status');state.models=r.engine;
    $('engineLabel').textContent=(r.engine.face_detection==='YuNet AI')?'AI engine ready':'Basic detector ready';
    $('optRecognize').disabled=!r.engine.face_recognition;
    $('optAge').disabled=!r.engine.age_estimation;
    $('ageSetup').classList.toggle('hidden',!!r.engine.age_estimation);
    $('optAppearance').disabled=!r.engine.appearance_estimation;
    if(!r.engine.face_recognition)$('optRecognize').checked=false;
    if(!r.engine.age_estimation)$('optAge').checked=false;
    if(!r.engine.appearance_estimation)$('optAppearance').checked=false;
    const missing=[];
    if(!r.engine.face_recognition)missing.push('recognition');
    if(!r.engine.age_estimation)missing.push('age');
    if(!r.engine.appearance_estimation)missing.push('appearance');
    $('modelHint').textContent=missing.length?'Optional features unavailable: '+missing.join(', ')+'. Run DOWNLOAD_EXTRAS.ps1 separately, then click Reload models.':'AI models are ready.';
  }catch(e){$('engineLabel').textContent='Cannot reach local engine';toast('Cannot connect to local server: '+e.message,true);}
}

function faceCard(face, live=false){
  const name=face.identity?escapeHTML(face.identity.name):'Face '+escapeHTML(face.index);
  const identity=face.identity?'<span class="match-tag">Possible match</span>':'';
  const age=face.age_estimate?escapeHTML(face.age_estimate.range)+' yrs':'Unavailable';
  const score=Number.isFinite(face.photo_aesthetics_score)?face.photo_aesthetics_score+'/100':'—';
  const appearance=face.appearance_estimate?`<div class="metric"><small>Appearance guess</small><b>${escapeHTML(face.appearance_estimate.label)}</b><span>Not gender identity</span></div>`:'';
  const twins=Array.isArray(face.celebrity_lookalikes)?face.celebrity_lookalikes:[];
  const celebMarkup=twins.length?`<div class="stars-result"><div class="star-title">★ Celebrity lookalikes · just for fun</div>${twins.map((v,i)=>`<div class="star-candidate"><span class="star-rank">${i+1}</span><b>${escapeHTML(v.name)}</b>${v.credit_url&&v.credit_url.startsWith('https://en.wikipedia.org/wiki/')?`<a href="${escapeHTML(v.credit_url)}" rel="noopener noreferrer" target="_blank">Photo source ↗</a>`:''}</div>`).join('')}<small>Closest comparisons in your local references — not a percentage or identity claim.</small></div>`:'';
  const tips=Array.isArray(face.capture_tips)?face.capture_tips.slice(0,live?1:3).map(escapeHTML).join(' · '):'';
  const smile=face.smile_pattern_detected===null?'Not checked':face.smile_pattern_detected?'Found':'Not found';
  const extra=live?'':`<details class="face-details"><summary>More face details</summary><div class="more-data">Brightness: ${Math.round(face.brightness)}/255 · Sharpness: ${Math.round(face.sharpness)}<br>Eyes: ${face.eyes_visible_estimate??'Not checked'} · Smile pattern: ${smile}<br>Framing: ${face.framing_score}/100 · Tilt: ${face.head_tilt_degrees===null?'Unavailable':Math.abs(face.head_tilt_degrees).toFixed(0)+'°'}</div></details>`;
  return `<article class="result-face"><div class="result-heading"><div class="result-title"><div class="result-face-avatar">${escapeHTML(face.index)}</div><div><b>${name}</b><small>${face.identity?'Matched to saved profile':'Face detected'}</small></div></div>${identity}</div><div class="result-metrics"><div class="metric"><small>Estimated age</small><b>${age}</b><span>Approximate</span></div><div class="metric primary-metric"><small>Photo score</small><b>${score}</b><span>Lighting & clarity</span></div>${appearance}</div>${tips?`<div class="face-tip">✦ ${tips}</div>`:''}${celebMarkup}${extra}</article>`;
}
function renderFaces(target, faces, live=false){
  if(!faces.length){target.innerHTML='<div class="insight-empty"><div class="empty-emoji">◎</div><b>No face detected</b><p>Try facing the camera in brighter light.</p></div>';return;}
  target.innerHTML=faces.slice(0,live?4:20).map(f=>faceCard(f,live)).join('') + (live&&faces.length>4?`<p class="quiet">+ ${faces.length-4} more faces detected</p>`:'');
}
function drawBoxes(canvas, result, mirrored=false) {
  const {width,height,faces}=result;
  if(!width||!height)return;
  canvas.width=width;canvas.height=height;
  const ctx=canvas.getContext('2d');ctx.clearRect(0,0,width,height);
  ctx.lineWidth=Math.max(2,Math.round(width/250));ctx.font=`700 ${Math.max(13,Math.round(width/42))}px system-ui,sans-serif`;
  for(const face of faces){
    const [bx,by,bw,bh]=face.bbox;
    const x=mirrored?width-bx-bw:bx;
    const y=by;
    ctx.strokeStyle=face.identity?'#4be4ae':'#b8a1ff';ctx.shadowColor='#0005';ctx.shadowBlur=7;
    ctx.strokeRect(x,y,bw,bh);ctx.shadowBlur=0;
    const label=face.identity?face.identity.name:`Face ${face.index}`;
    const trimmed=String(label).slice(0,24);
    const textwidth=ctx.measureText(trimmed).width;
    const labelW=textwidth+15,labelH=Math.max(22,Math.round(width/29));
    const lx=Math.max(0,Math.min(width-labelW,x));
    const ly=Math.max(0,y-labelH);
    ctx.fillStyle='#241d41e8';ctx.fillRect(lx,ly,labelW,labelH);
    ctx.fillStyle='#fff';ctx.fillText(trimmed,lx+7,ly+labelH-7);
    if(state.mode==='party'&&mirrored){
      ctx.textAlign='center';ctx.font=`${Math.max(26,Math.round(bw*.58))}px system-ui`;
      ctx.fillText('👑',x+bw/2,Math.max(46,y+15));
      ctx.font=`${Math.max(18,Math.round(bw*.4))}px system-ui`;
      ctx.fillText('😎',x+bw/2,y+bh*.53);ctx.textAlign='start';
      ctx.font=`700 ${Math.max(13,Math.round(width/42))}px system-ui,sans-serif`;
    }
    if(state.mode==='vision'&&mirrored&&face.landmarks){
      for(const point of face.landmarks){ctx.beginPath();ctx.arc(width-point[0],point[1],Math.max(3,width/180),0,2*Math.PI);ctx.fillStyle='#54e9d3';ctx.fill();}
    }
  }
}

function setCameraUI(running) {
  $('cameraPlaceholder').classList.toggle('hidden',running);
  $('liveOverlayIndicator').classList.toggle('hidden',!running);
  $('cameraToggle').classList.toggle('is-running',running);
  $('cameraToggle').querySelector('span').textContent=running?'Stop camera':'Start camera';
  $('cameraCapture').disabled=!running;
  $('saveSelfie').disabled=!running;
  $('camIndicator').classList.toggle('online',running);
  $('camIndicator').lastChild.textContent=running?' Live':' Camera off';
  $('cameraHint').textContent=running?'Filters run instantly. AI insights refresh as your computer allows.':'Camera stays off until you press Start.';
  if(!running){$('liveCount').textContent='—';$('liveResults').innerHTML=emptyLive;}
}
async function startCamera(){
  if(!$('allowCamera').checked){toast('Please confirm everyone on camera has given permission.',true);return;}
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){toast('Camera access requires localhost and a modern browser.',true);return;}
  if(state.stream)return;
  const btn=$('cameraToggle');btn.disabled=true;
  try{
    const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:1280},height:{ideal:720}},audio:false});
    if(state.tab!=='live'||!$('allowCamera').checked){stream.getTracks().forEach(t=>t.stop());return;}
    state.stream=stream;
    state.session++;const thisSession=state.session;
    for(const track of stream.getVideoTracks())track.addEventListener('ended',()=>{if(state.session===thisSession)stopCamera();});
    const video=$('camera');video.srcObject=stream;
    await video.play();
    state.failures=0;state.lastResult=null;setCameraUI(true);
    state.renderAt=0;renderLiveEffects(performance.now());
    scheduleLiveFrame(thisSession,150);
  }catch(e){stopCamera();
    const help=e.name==='NotAllowedError'?'Camera permission was denied. Allow camera access in your browser and try again.':e.name==='NotFoundError'?'No webcam found. Connect a camera and try again.':'Unable to start the camera: '+e.message;
    toast(help,true);
  }finally{btn.disabled=false;}
}
function stopCamera(){
  state.session++;
  if(state.renderHandle!==null){cancelAnimationFrame(state.renderHandle);state.renderHandle=null;}
  state.lastResult=null;
  if(state.nextFrame!==null){clearTimeout(state.nextFrame);state.nextFrame=null;}
  if(state.pending){state.pending.abort();state.pending=null;}
  if(state.stream){for(const track of state.stream.getTracks())track.stop();state.stream=null;}
  const video=$('camera');if(video)video.srcObject=null;
  const canvas=$('liveCanvas');if(canvas){const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);}
  setCameraUI(false);
}
function scheduleLiveFrame(session, delay){
  if(session!==state.session||!state.stream)return;
  state.nextFrame=setTimeout(()=>analyzeLiveFrame(session),delay);
}
async function makeCameraImage(){
  const video=$('camera');
  if(!video.videoWidth||!video.videoHeight)return null;
  const scale=Math.min(1,640/video.videoWidth);
  const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(video.videoWidth*scale));canvas.height=Math.max(1,Math.round(video.videoHeight*scale));
  canvas.getContext('2d',{alpha:false}).drawImage(video,0,0,canvas.width,canvas.height);
  return await new Promise(resolve=>canvas.toBlob(blob=>resolve(blob?new File([blob],'live-frame.jpg',{type:'image/jpeg'}):null),'image/jpeg',.74));
}
async function getAnalysis(file,live=false,signal=undefined){
  const f=new FormData();f.append('file',file);
  f.append('recognize',String($('optRecognize').checked));
  f.append('estimate_age',String($('optAge').checked));
  f.append('estimate_appearance',String($('optAppearance').checked));
  f.append('live',String(live));
  f.append('celebrity_mode',String(live?state.mode==='celebrity':$('photoCelebMode').checked));
  return api('/api/analyze',{method:'POST',body:f,signal});
}
async function analyzeLiveFrame(session){
  if(session!==state.session||!state.stream||document.hidden)return;
  state.nextFrame=null;
  const begin=performance.now();
  const controller=new AbortController();state.pending=controller;
  try{
    const frame=await makeCameraImage();
    if(!frame||session!==state.session)return;
    const result=await getAnalysis(frame,true,controller.signal);
    if(session!==state.session)return;
    state.lastResult=result;
    updateChallenge(result);
    $('liveCount').textContent=result.face_count;
    renderFaces($('liveResults'),result.faces,true);
    // Face overlay runs independently from the AI request, so animations stay smooth.
    state.failures=0;
  }catch(e){
    if(e.name!=='AbortError'&&session===state.session){
      state.failures++;
      if(state.failures===1)toast('Camera analysis problem: '+e.message,true);
      if(state.failures>=5){toast('Live analysis stopped after repeated errors. Restart the camera to try again.',true);stopCamera();return;}
    }
  }finally{
    if(state.pending===controller)state.pending=null;
    const elapsed=performance.now()-begin;
    // Never queue uploads; one request at a time. Target up to ~2 analyses/s, hardware permitting.
    scheduleLiveFrame(session,Math.max(90,600-elapsed));
  }
}
$('cameraToggle').addEventListener('click',()=>state.stream?stopCamera():startCamera());
$('allowCamera').addEventListener('change',()=>{if(!$('allowCamera').checked)stopCamera();});
$('cameraCapture').addEventListener('click',async()=>{
  if(!state.stream)return;
  const shot=await makeCameraImage();if(!shot)return;
  setPhoto(shot);
  $('allowAnalyze').checked=true;
  $('analyzeBtn').disabled=false;
  switchTab('photo');
  await analyzePhoto();
});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopCamera();});
window.addEventListener('beforeunload',stopCamera);

function validatePhoto(file){
  if(!file)return false;
  if(!['image/jpeg','image/png','image/webp'].includes(file.type)){toast('Choose a JPG, PNG, or WebP picture.',true);return false;}
  if(file.size>8*1024*1024){toast('This file is too large. Choose one under 8 MB.',true);return false;}
  return true;
}
function setPhoto(file){
  if(!validatePhoto(file))return;
  if(state.photoURL)URL.revokeObjectURL(state.photoURL);
  state.photo=file;state.report=null;state.photoURL=URL.createObjectURL(file);
  $('previewImage').src=state.photoURL;
  $('previewPanel').classList.remove('hidden');$('dropzone').classList.add('hidden');
  $('photoResults').innerHTML=emptyPhoto;
  $('exportBtn').classList.add('hidden');
  $('fileHint').textContent=(file.name==='live-frame.jpg'?'Camera snapshot':file.name)+' · '+(file.size/1024).toFixed(0)+' KB';
  $('analyzeBtn').disabled=!$('allowAnalyze').checked;
  const c=$('photoCanvas');c.getContext('2d').clearRect(0,0,c.width,c.height);
}
$('browseBtn').addEventListener('click',e=>{e.stopPropagation();$('photoInput').click();});
$('dropzone').addEventListener('click',e=>{if(!e.target.closest('button'))$('photoInput').click();});
$('dropzone').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('photoInput').click();}});
$('dropzone').addEventListener('dragover',e=>{e.preventDefault();$('dropzone').classList.add('dragging');});
$('dropzone').addEventListener('dragleave',()=>$('dropzone').classList.remove('dragging'));
$('dropzone').addEventListener('drop',e=>{e.preventDefault();$('dropzone').classList.remove('dragging');setPhoto(e.dataTransfer.files[0]);});
$('photoInput').addEventListener('change',e=>setPhoto(e.target.files[0]));
$('replaceBtn').addEventListener('click',()=>{$('photoInput').click();});
$('allowAnalyze').addEventListener('change',()=>$('analyzeBtn').disabled=!state.photo||!$('allowAnalyze').checked);
async function analyzePhoto(){
  if(!state.photo||!$('allowAnalyze').checked)return;
  const btn=$('analyzeBtn');btn.disabled=true;btn.textContent='Analyzing…';
  try{
    const result=await getAnalysis(state.photo);
    state.report=result;
    renderFaces($('photoResults'),result.faces);
    $('exportBtn').classList.remove('hidden');
    const img=$('previewImage');
    if(img.complete&&img.naturalWidth)drawBoxes($('photoCanvas'),result);
  }catch(e){toast('Could not analyze photo: '+e.message,true);}finally{btn.textContent='Analyze photo →';btn.disabled=false;}
}
$('analyzeBtn').addEventListener('click',analyzePhoto);
$('previewImage').addEventListener('load',()=>{if(state.report)drawBoxes($('photoCanvas'),state.report);});
$('exportBtn').addEventListener('click',()=>{
  if(!state.report)return;
  const data=new Blob([JSON.stringify(state.report,null,2)],{type:'application/json'});
  const link=document.createElement('a');link.href=URL.createObjectURL(data);link.download='facestudio-analysis.json';link.click();
  setTimeout(()=>URL.revokeObjectURL(link.href),5000);
});

$('enrollForm').addEventListener('submit',async event=>{
  event.preventDefault();if(!$('enrollConsent').checked){toast('Please confirm the person agreed to recognition.',true);return;}
  const photo=$('enrollPhoto').files[0];if(!validatePhoto(photo))return;
  const form=new FormData();form.append('file',photo);form.append('name',$('enrollName').value.trim());form.append('consent','true');
  const submit=$('enrollSubmit');submit.disabled=true;submit.textContent='Saving…';
  try{const data=await api('/api/enroll',{method:'POST',body:form});toast(data.name+' saved privately.');$('enrollForm').reset();await refreshPeople();await loadStatus();}
  catch(e){toast('Could not save face: '+e.message,true);}
  finally{submit.disabled=false;submit.textContent='Save person';}
});
async function refreshPeople(){
  try{
    const r=await api('/api/people');
    $('galleryCount').textContent=r.people.length;
    const list=$('peopleList');
    list.innerHTML=r.people.length?r.people.map(person=>`<div class="person"><div class="person-avatar">${escapeHTML(person.name.slice(0,1).toUpperCase())}</div><div class="person-text"><b>${escapeHTML(person.name)}</b><small>${person.samples} saved sample${person.samples===1?'':'s'}</small></div><button class="person-delete" data-id="${person.id}" data-name="${escapeHTML(person.name)}">Delete</button></div>`).join(''):'<div class="people-empty">No one added yet. Register a consenting person to enable recognition.</div>';
    for(const button of list.querySelectorAll('.person-delete'))button.addEventListener('click',async()=>{
      if(!confirm('Delete '+button.dataset.name+' and their face data?'))return;
      try{await api('/api/people/'+button.dataset.id,{method:'DELETE'});await refreshPeople();toast('Face data deleted.');}catch(e){toast(e.message,true);}
    });
  }catch(e){toast('Could not load saved people: '+e.message,true);}
}
$('clearGallery').addEventListener('click',async()=>{
  if(!confirm('Delete ALL saved people and their face data? This cannot be undone.'))return;
  if(!confirm('Confirm permanent removal of every saved face profile?'))return;
  try{await api('/api/people?confirm=DELETE_ALL',{method:'DELETE'});await refreshPeople();toast('All face profiles deleted.');}catch(e){toast(e.message,true);}
});

// A simple mode switch — no more confusing options or restart required.
const modeDescriptions={
  studio:'Live face boxes, camera quality and simple results.',
  celebrity:'★ Find your closest celebrity twin from your local reference gallery.',
  party:'✨ Animated crown, glasses and floating hearts. Save a fun selfie!',
  vision:'◈ See live face points as the camera tracks you.'
};
for(const button of document.querySelectorAll('.mode-chip')){
  button.addEventListener('click',()=>{
    state.mode=button.dataset.mode;
    for(const other of document.querySelectorAll('.mode-chip'))other.classList.toggle('selected',other===button);
    $('modeDescription').textContent=modeDescriptions[state.mode];
    $('celebrityPrompt').classList.toggle('hidden',state.mode!=='celebrity'||state.celebCount>0);
    if(state.stream)state.renderAt=0;
    if(state.mode==='celebrity'&&state.celebCount===0)toast('Add famous-face references in My people to unlock matches.');
  });
}
$('reloadModels').addEventListener('click',async()=>{try{await api('/api/models/reload',{method:'POST'});await loadStatus();toast('AI models reloaded without reinstalling!');}catch(e){toast(e.message,true);}});
$('goCelebrities').addEventListener('click',()=>switchTab('people'));
function updateChallenge(result){
  const face=result.faces?.[0];
  let title='Selfie challenge',tip='Face the camera for the first challenge.';
  if(result.face_count>1){title='Group photo!';tip='Everyone in frame — nice!';}
  else if(face){
    const score=face.photo_aesthetics_score||0;
    if(score>=78){title='✨ Great capture!';tip='Nice lighting, clarity and framing. Try saving a selfie.';}
    else if(face.framing_score<70){title='🎯 Get centered';tip='Move your face a little closer to the center.';}
    else if(face.brightness<85){title='💡 Find the light';tip='Turn toward a window or brighter lamp.';}
    else {title='Almost there';tip=face.capture_tips?.[0]||'Hold the camera steady for a clearer photo.';}
  }
  $('challengeTitle').textContent=title;$('challengeText').textContent=tip;
}
$('saveSelfie').addEventListener('click',async()=>{
  const video=$('camera');if(!state.stream||!video.videoWidth)return;
  const c=document.createElement('canvas');c.width=video.videoWidth;c.height=video.videoHeight;
  const x=c.getContext('2d');x.save();x.filter=FaceEffects.byId(state.filter).css;x.translate(c.width,0);x.scale(-1,1);x.drawImage(video,0,0);x.restore();
  const effect=$('liveCanvas');if(effect.width)x.drawImage(effect,0,0,c.width,c.height);
  c.toBlob(blob=>{if(!blob)return;const url=URL.createObjectURL(blob);const a=document.createElement('a');a.download='FaceStudio-fun-selfie.png';a.href=url;a.click();setTimeout(()=>URL.revokeObjectURL(url),3000);toast('Selfie saved!');},'image/png');
});
async function refreshCelebrities(){
  try{
    const r=await api('/api/celebrities');const list=r.references;
    state.celebCount=list.length;$('celebrityCount').textContent=list.length;
    $('catalogDescription').textContent=`${r.catalog_size||60} curated names available · ${list.length} locally imported. You choose when to download reference photos.`;
    $('celebrityPrompt').classList.toggle('hidden',state.mode!=='celebrity'||list.length>0);
    $('celebrityList').innerHTML=list.length?list.map(p=>`<div class="reference-pill"><span>⭐</span><b>${escapeHTML(p.name)}</b><button type="button" data-celeb-id="${p.id}" title="Delete this reference">✕</button></div>`).join(''):'<div class="reference-empty">No celebrity references yet. Create a starter gallery or add a favorite portrait.</div>';
    for(const button of $('celebrityList').querySelectorAll('[data-celeb-id]'))button.addEventListener('click',async()=>{
      if(!confirm('Remove this celebrity reference?'))return;
      try{await api('/api/celebrities/'+button.dataset.celebId,{method:'DELETE'});await refreshCelebrities();toast('Reference removed.');}catch(e){toast(e.message,true);}
    });
    updateStarterStatus(r.starter);
  }catch(e){toast('Celebrity gallery unavailable: '+e.message,true);}
}
function updateStarterStatus(s){
  const label=s.state==='running'?`Adding references ${s.done}/${s.total} · saved ${s.added}`:(s.message||'Not started');
  $('importStatus').textContent=label;
  $('starterButton').disabled=s.state==='running';
  $('expandedButton').disabled=s.state==='running';
}
let importPolling=null;
async function installCelebrityPack(pack){
  const message=pack==='expanded'?'Download available public reference thumbnails for the expanded celebrity catalog? This can take time; webcam photos are NEVER uploaded.':'Import up to 16 celebrity portraits from Wikipedia? Webcam photos are NEVER uploaded.';
  if(!confirm(message))return;
  try{
    await api('/api/celebrities/starter?pack='+pack,{method:'POST'});
    $('starterButton').disabled=true;
    clearInterval(importPolling);
    importPolling=setInterval(async()=>{
      try{const r=await api('/api/celebrities');updateStarterStatus(r.starter);
        if(r.starter.state!=='running'){clearInterval(importPolling);importPolling=null;await refreshCelebrities();toast(r.starter.message);}
      }catch(e){clearInterval(importPolling);importPolling=null;toast(e.message,true);}
    },1300);
  }catch(e){toast(e.message,true);}
}
$('starterButton').addEventListener('click',()=>installCelebrityPack('starter'));
$('expandedButton').addEventListener('click',()=>installCelebrityPack('expanded'));
$('celebrityForm').addEventListener('submit',async e=>{
  e.preventDefault();const f=$('celebrityPhoto').files[0];if(!validatePhoto(f))return;
  if(!$('celebrityRights').checked)return;
  const data=new FormData();data.append('file',f);data.append('name',$('celebrityName').value.trim());data.append('authorized','true');
  const btn=$('celebritySubmit');btn.disabled=true;btn.textContent='Adding…';
  try{const r=await api('/api/celebrities',{method:'POST',body:data});toast(r.name+' added.');$('celebrityForm').reset();await refreshCelebrities();}
  catch(err){toast('Reference not saved: '+err.message,true);}finally{btn.disabled=false;btn.textContent='+ Add face';}
});
$('clearCelebrities').addEventListener('click',async()=>{
  if(!confirm('Remove every celebrity reference from this computer?'))return;
  try{
    const r=await api('/api/celebrities');
    for(const p of r.references) await api('/api/celebrities/'+p.id,{method:'DELETE'});
    await refreshCelebrities();toast('Celebrity gallery cleared.');
  }catch(e){toast(e.message,true);}
});

// The 10 photo looks are instantaneous CSS filters. Unlike face inference,
// browser effects do not require a server round-trip or additional AI models.
for(const look of FaceEffects.looks){
  const button=document.createElement('button');button.type='button';
  button.className='filter-choice'+(look.id===state.filter?' selected':'');
  button.dataset.look=look.id;button.setAttribute('aria-pressed',String(look.id===state.filter));
  button.innerHTML=`<span class="filter-orb" style="--orb-color:${look.tone}">${look.icon}</span><span>${escapeHTML(look.name)}</span>`;
  button.addEventListener('click',()=>{
    state.filter=look.id;
    $('camera').style.filter=look.css;
    for(const b of $('filterStrip').children){const yes=b.dataset.look===look.id;b.classList.toggle('selected',yes);b.setAttribute('aria-pressed',String(yes));}
    state.renderAt=0;
  });
  $('filterStrip').appendChild(button);
}
for(const morph of FaceEffects.morphs){
  const button=document.createElement('button');button.type='button';
  button.className='morph-choice'+(morph.id==='off'?' selected':'');
  button.textContent=morph.name;button.dataset.morph=morph.id;
  button.setAttribute('aria-pressed',String(morph.id==='off'));
  button.addEventListener('click',()=>{
    state.morph=morph.id;
    for(const b of $('morphButtons').children){const yes=b.dataset.morph===morph.id;b.classList.toggle('selected',yes);b.setAttribute('aria-pressed',String(yes));}
    state.renderAt=0;
    if(morph.id!=='off'&&state.models?.face_detection!=='YuNet AI')toast('Best results need the installed YuNet model for eye and mouth tracking.');
  });
  $('morphButtons').appendChild(button);
}
function renderLiveEffects(now){
  if(!state.stream || state.tab!=='live')return;
  // 15–20 overlay renders/s, while the video itself is drawn by the browser
  // independently and remains smooth even when face inference takes longer.
  if(now-state.renderAt>56){
    state.renderAt=now;
    const video=$('camera'),canvas=$('liveCanvas');
    if(video.videoWidth && video.videoHeight){
      let result=state.lastResult;
      if(!result)result={width:video.videoWidth,height:video.videoHeight,faces:[]};
      try{FaceEffects.frame(video,canvas,result,{mode:state.mode,filter:state.filter,morph:state.morph},now);}catch(err){
        // Optional artistic effect errors must never stop the webcam.
        console.warn('Camera overlay skipped:',err);
      }
    }
  }
  state.renderHandle=requestAnimationFrame(renderLiveEffects);
}

// Explicit opt-in age estimator setup, never a mandatory app startup download.
async function pollAgeDownload(){
  try{
    const r=await api('/api/models/age/status');
    const amount=r.state==='running'&&r.downloaded_mb?` · ${r.downloaded_mb} MB received`:'';
    $('ageDownloadStatus').textContent=r.message+amount;
    $('enableAge').disabled=r.state==='running';
    if(r.state==='complete'){
      clearInterval(state.agePoll);state.agePoll=null;
      await loadStatus();
      $('optAge').checked=true;
      toast('🎂 Age guessing is ready — point your camera at a face!');
    }
    if(r.state==='error'){
      clearInterval(state.agePoll);state.agePoll=null;
      $('enableAge').disabled=false;
      toast('Age model unavailable: '+r.message,true);
    }
  }catch(e){clearInterval(state.agePoll);state.agePoll=null;$('enableAge').disabled=false;toast(e.message,true);}
}
$('enableAge').addEventListener('click',async()=>{
  if(!confirm('Download the optional age-range estimation model to this computer? The download is large but does not block your camera.'))return;
  $('enableAge').disabled=true;
  try{
    await api('/api/models/age/install',{method:'POST'});
    await pollAgeDownload();
    clearInterval(state.agePoll);
    state.agePoll=setInterval(pollAgeDownload,1700);
  }catch(e){$('enableAge').disabled=false;toast(e.message,true);}
});
// Browser camera access is user-initiated, and stopping the camera cancels all pending analysis.
loadStatus();
refreshCelebrities();
