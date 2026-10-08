const $ = (id) => document.getElementById(id);
const pairScreen = $('pairScreen'), appScreen = $('appScreen');
const camera = $('camera'), orb = $('orb');
$('modelSelect').setAttribute('aria-label','Model');
document.querySelector('.camera-label').textContent='One frame is sent with each question while the camera is on.';
let cameraStream = null, micStream = null, recognition = null, analyser = null;
let audioContext = null, levelFrame = 0, busy = false, privacy = false, generation = 0;
let status = 'ready', useNextFrame = false;
let scanImage = null;
let speechPlayer = null, speechURL = null, speechAbort = null, speechEpoch = 0;
let spokenReplies = true;
let speechProvider = 'fish';
let selectedChat = null, chatLoadGeneration = 0, workspaceReady = false, harnessStatus = null;
let activePanel = null, workspaceRefresh = null;
const ambient = $('ambientVideo');
let motionEnabled = !matchMedia('(prefers-reduced-motion: reduce)').matches;
function updateMotion(){
  if(motionEnabled && !document.hidden) ambient.play().catch(()=>{}); else ambient.pause();
  $('motionButton').textContent=motionEnabled?'Pause background':'Play background';
  $('motionButton').setAttribute('aria-pressed',String(motionEnabled));
}
$('motionButton').onclick=()=>{motionEnabled=!motionEnabled;updateMotion();};
document.addEventListener('visibilitychange',updateMotion);
updateMotion();
$('audioReplies').onclick=()=>{spokenReplies=!spokenReplies;if(!spokenReplies){stopAudio();setState('ready','Spoken replies paused');}$('audioReplies').textContent=spokenReplies?'Spoken replies on':'Spoken replies off';$('audioReplies').setAttribute('aria-pressed',String(spokenReplies));};

function setState(next, line, hint='') {
  status = next;
  document.body.classList.remove('listening','thinking','speaking','privacy');
  document.body.classList.add(next);
  $('statusText').textContent = line;
  $('hintText').textContent = hint;
  $('stateTag').textContent = next;
  $('micButton').classList.toggle('active', next === 'listening');
  $('micButton').setAttribute('aria-label', next === 'listening' ? 'Stop listening' : 'Start listening');
}
function notice(message) {
  const scanning=!$('scanReview').classList.contains('hidden');
  $('notice').textContent=message; $('notice').classList.toggle('hidden',!message||scanning);
  $('scanNotice').textContent=message; $('scanNotice').classList.toggle('hidden',!message||!scanning);
}
function showApp() { pairScreen.classList.add('hidden'); appScreen.classList.remove('hidden'); setState('ready','Ready when you are','Tap the mic and ask a question'); refreshStatus(); }
async function request(path, options={}) {
  const response = await fetch(path, {credentials:'same-origin',...options});
  let body = {}; try { body = await response.json(); } catch {}
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}
async function refreshStatus() {
  try {
    const info = await request('/status');
    if(appScreen.classList.contains('hidden')){pairScreen.classList.add('hidden');appScreen.classList.remove('hidden');setState('ready','Ready when you are','Talk, type, or use your camera');}
    speechProvider=info.speech_provider || 'fish';
    $('modelSelect').querySelector('[value="kimi"]').disabled=!info.kimi;
    $('modelInfo').textContent = `local ${info.local_text?'configured':'not set'} · vision ${info.local_vision?'configured':'not set'} · Drive ${info.drive_configured?'configured':'not connected'}`;
    if(!workspaceReady){workspaceReady=true;await initializeWorkspace();}
  } catch { pairScreen.classList.remove('hidden'); appScreen.classList.add('hidden'); $('stateTag').textContent='unpaired'; }
}
function stopAudio() {
  speechEpoch++;
  if(speechAbort){speechAbort.abort();speechAbort=null;}
  if(speechPlayer){speechPlayer.pause();speechPlayer.removeAttribute('src');speechPlayer=null;}
  if(speechURL){URL.revokeObjectURL(speechURL);speechURL=null;}
  if (recognition) { try { recognition.abort(); } catch {} recognition=null; }
  if (micStream) { micStream.getTracks().forEach(t=>t.stop()); micStream=null; }
  if (levelFrame) cancelAnimationFrame(levelFrame);
  levelFrame=0; orb.style.setProperty('--level','1');
  if (audioContext) { audioContext.close().catch(()=>{}); audioContext=null; }
  window.speechSynthesis?.cancel();
}
function stopCamera() {
  if (cameraStream) cameraStream.getTracks().forEach(t=>t.stop());
  cameraStream=null; camera.srcObject=null; $('cameraPanel').classList.add('hidden');
  $('cameraButton').setAttribute('aria-label','Turn camera on');
}
function stopEverything() { generation++; stopAudio(); stopCamera(); busy=false; useNextFrame=false; }
function addMessage(who, text) {
  document.body.classList.add('has-messages');
  const empty = $('conversation').querySelector('.empty'); if (empty) empty.remove();
  const row=document.createElement('div'); row.className=`message ${who}`;
  const label=document.createElement('div'); label.className='who'; label.textContent=who==='assistant'?'GIG':'You';
  const content=document.createElement('div'); content.textContent=text;
  row.append(label,content); $('conversation').append(row); $('conversation').scrollTop=$('conversation').scrollHeight;
}
function element(tag, className='', value='') {
  const node=document.createElement(tag);if(className)node.className=className;
  if(value)node.textContent=value;return node;
}
function clearConversation() {
  $('conversation').replaceChildren();document.body.classList.remove('has-messages');
}
async function initializeWorkspace() {
  try {await loadChats(); harnessStatus=await request('/harness/status');
    if(!selectedChat){const chats=await request('/chats');if(chats.length)await selectChat(chats[0].id);else await createChat();}
    workspaceRefresh=setInterval(()=>{if(!document.hidden&&activePanel==='tasks')renderTasks().catch(err=>notice(err.message));},4000);
  }catch(err){notice('Workspace unavailable: '+err.message);}
}
async function loadChats() {
  const chats=await request('/chats');const list=$('chatList');list.replaceChildren();
  if(!chats.length)list.append(element('p','sidebar-empty','No saved chats yet.'));
  for(const chat of chats){const button=element('button','chat-entry',chat.title);button.type='button';button.title=chat.title;
    button.classList.toggle('selected',chat.id===selectedChat);
    button.onclick=()=>{if(busy){notice('Wait for the current reply before changing chats.');return;}selectChat(chat.id).catch(err=>notice(err.message));};
    list.append(button);}
  $('chatSearch').dispatchEvent(new Event('input'));
}
$('chatSearch').oninput=()=>{const query=$('chatSearch').value.toLowerCase();for(const button of $('chatList').querySelectorAll('.chat-entry'))button.classList.toggle('hidden',!button.textContent.toLowerCase().includes(query));};
async function createChat(){if(busy)return;const chat=await request('/chats',{method:'POST'});await selectChat(chat.id);}
async function selectChat(id){const current=++chatLoadGeneration;
  const chat=await request('/chats/'+encodeURIComponent(id));if(current!==chatLoadGeneration)return;
  selectedChat=id;stopAudio();clearConversation();$('chatTitle').textContent=chat.title;
  for(const message of chat.messages)addMessage(message.role==='user'?'user':'assistant',message.content);
  await loadChats();$('workspaceSidebar').classList.remove('mobile-open');
}
function panelHeader(title,description){const panel=$('workspacePanel');panel.replaceChildren();
  const head=element('div','panel-heading');head.append(element('h2','',title));
  const close=element('button','','Close');close.type='button';close.onclick=()=>{panel.classList.add('hidden');activePanel=null;};head.append(close);panel.append(head);
  if(description)panel.append(element('p','panel-description',description));panel.classList.remove('hidden');return panel;
}
async function renderMemory(search=''){activePanel='memory';const panel=panelHeader('Memory','Only notes you explicitly save appear here. Every paired device shares this workspace.');
  const form=element('form','memory-form');const input=element('input');input.type='text';input.maxLength=4000;input.placeholder='Something GIG should remember';input.setAttribute('aria-label','Memory note');
  const save=element('button','','Remember');save.type='submit';form.append(input,save);panel.append(form);
  form.onsubmit=async(event)=>{event.preventDefault();if(!input.value.trim())return;
    try{await request('/memories',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:input.value})});await renderMemory();}catch(err){notice(err.message);}};
  const searchInput=element('input','memory-search');searchInput.type='search';searchInput.placeholder='Find a memory';searchInput.setAttribute('aria-label','Search memories');searchInput.value=search;
  searchInput.oninput=()=>{const needle=searchInput.value.toLowerCase();for(const row of panel.querySelectorAll('.memory-row'))row.classList.toggle('hidden',!row.querySelector('span').textContent.toLowerCase().includes(needle));};
  panel.append(searchInput);
  const entries=await request('/memories');const list=element('div','memory-list');panel.append(list);
  if(!entries.length)list.append(element('p','panel-empty','No memories yet. Add one above.'));
  for(const item of entries){const row=element('div','memory-row');row.append(element('span','',item.text));
    const edit=element('button','','Edit');edit.type='button';edit.onclick=async()=>{const revised=prompt('Edit memory',item.text);if(!revised?.trim())return;
      try{await request('/memories/'+item.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:revised.trim()})});await renderMemory(searchInput.value);}catch(err){notice(err.message);}};
    const remove=element('button','','Forget');remove.type='button';remove.onclick=async()=>{if(!confirm('Forget this memory?'))return;
      try{await request('/memories/'+item.id,{method:'DELETE'});await renderMemory(searchInput.value);}catch(err){notice(err.message);}};row.append(edit,remove);list.append(row);}
  searchInput.dispatchEvent(new Event('input'));
}
async function renderTasks(){activePanel='tasks';const panel=panelHeader('Agent tasks','Each task is reviewed before it starts. This gateway cannot stop an already running task.');
  const configured=harnessStatus?.ready;
  const state=element('p','agent-state',configured?'OpenClaw gateway reachable for approved tasks.':'Agent execution is not ready on this server.');panel.append(state);
  const draft=document.querySelector('.agent-form textarea')?.value||'';
  const form=element('form','agent-form');const input=element('textarea');input.rows=3;input.maxLength=4000;input.placeholder='Describe one task for the agent';input.setAttribute('aria-label','Agent task');input.value=draft;
  const prepare=element('button','','Review task');prepare.type='submit';prepare.disabled=!configured;form.append(input,prepare);panel.append(form);
  form.onsubmit=async(event)=>{event.preventDefault();if(!selectedChat||!input.value.trim())return;
    try{const task=await request('/chats/'+selectedChat+'/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:input.value})});
      input.value='';await renderTasks();notice('Task queued for your approval. No action has started.');}catch(err){notice(err.message);}};
  const runs=await request('/runs');const list=element('div','run-list');panel.append(list);
  if(!runs.length)list.append(element('p','panel-empty','No agent tasks yet.'));
  for(const run of runs){const row=element('article','run-row');row.append(element('div','run-prompt',run.prompt));row.append(element('small','run-state','State: '+run.state));
    if(run.result)row.append(element('p','run-result',run.result));
    const traceButton=element('button','trace-button','Show timeline');traceButton.type='button';
    traceButton.onclick=async()=>{const existing=row.querySelector('.run-timeline');if(existing){existing.remove();traceButton.textContent='Show timeline';return;}
      try{const events=await request('/runs/'+run.id+'/events');const timeline=element('ol','run-timeline');
        for(const event of events){const item=element('li','',`${event.phase} · ${event.detail}`);timeline.append(item);}row.append(timeline);traceButton.textContent='Hide timeline';}
      catch(err){notice(err.message);}};row.append(traceButton);
    if(run.state==='awaiting_approval'){const controls=element('div','run-controls');const approve=element('button','','Approve and start'),reject=element('button','','Reject');
      approve.onclick=async()=>{if(!confirm('Start this task? The agent may use tools allowed by its server policy.'))return;
        try{await request('/runs/'+run.id+'/approve',{method:'POST'});await renderTasks();}catch(err){notice(err.message);}};
      reject.onclick=async()=>{try{await request('/runs/'+run.id+'/reject',{method:'POST'});await renderTasks();}catch(err){notice(err.message);}};
      controls.append(approve,reject);row.append(controls);}
    list.append(row);}
}
function renderConnections(){activePanel='connections';const panel=panelHeader('Connections','Availability is reported by this server. An account is not connected just because a button exists.');
  const status=harnessStatus?.integrations||{};
  for(const [name,ready] of Object.entries(status)){const row=element('div','connection-row');row.append(element('strong','',name.replace('_',' ')),element('span','',ready?'Configured':'Not connected'));panel.append(row);}
  panel.append(element('p','panel-description',harnessStatus?.retention||''));
}
$('newChatButton').onclick=()=>createChat().catch(err=>notice(err.message));
$('openSidebar').onclick=()=>$('workspaceSidebar').classList.add('mobile-open');
$('closeSidebar').onclick=()=>$('workspaceSidebar').classList.remove('mobile-open');
$('memoryButton').onclick=()=>{ $('workspaceSidebar').classList.remove('mobile-open');renderMemory().catch(err=>notice(err.message));};
$('tasksButton').onclick=()=>{ $('workspaceSidebar').classList.remove('mobile-open');renderTasks().catch(err=>notice(err.message));};
$('connectionsButton').onclick=()=>{ $('workspaceSidebar').classList.remove('mobile-open');renderConnections();};
$('renameChatButton').onclick=async()=>{if(!selectedChat)return;const title=prompt('Rename chat', $('chatTitle').textContent);
  if(!title?.trim())return;try{await request('/chats/'+selectedChat,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:title.trim()})});
    $('chatTitle').textContent=title.trim();await loadChats();}catch(err){notice(err.message);}};
$('exportChatButton').onclick=async()=>{if(!selectedChat)return;
  try{const chat=await request('/chats/'+selectedChat);const blob=new Blob([JSON.stringify({title:chat.title,messages:chat.messages},null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='gig-chat-'+selectedChat.slice(0,8)+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  catch(err){notice(err.message);}};
$('deleteChatButton').onclick=async()=>{if(!selectedChat||busy||!confirm('Delete this chat and its messages? This cannot be undone.'))return;
  try{const old=selectedChat;selectedChat=null;await request('/chats/'+old,{method:'DELETE'});const chats=await request('/chats');
    if(chats.length)await selectChat(chats[0].id);else await createChat();}catch(err){notice(err.message);}};
function frame() {
  if (!cameraStream || !camera.videoWidth) return null;
  const canvas=document.createElement('canvas'); const scale=Math.min(1,1600/camera.videoWidth);
  canvas.width=Math.round(camera.videoWidth*scale); canvas.height=Math.round(camera.videoHeight*scale);
  canvas.getContext('2d').drawImage(camera,0,0,canvas.width,canvas.height);
  return canvas.toDataURL('image/jpeg',.72);
}
async function speak(text) {
  if(privacy)return;
  if(!spokenReplies){setState('ready','Reply ready','Spoken replies are off');return;}
  stopAudio();
  const epoch=speechEpoch;
  const controller=new AbortController();speechAbort=controller;
  const timeout=setTimeout(()=>controller.abort(),45000);
  setState('thinking','Preparing voice',speechProvider==='fish'?'Fish Audio · spoken reply text is processed online':'Local voice · preparing your reply');
  try {
    const response=await fetch('/speech',{method:'POST',credentials:'same-origin',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({text}),signal:controller.signal});
    if(!response.ok){let error={};try{error=await response.json();}catch{}throw new Error(error.detail||'Speech service unavailable');}
    const blob=await response.blob();
    if(epoch!==speechEpoch||privacy)return;
    speechURL=URL.createObjectURL(blob);speechPlayer=new Audio(speechURL);
    speechPlayer.onended=()=>{if(epoch===speechEpoch){stopAudio();setState('ready','Ready when you are');}};
    speechPlayer.onerror=()=>{if(epoch===speechEpoch){stopAudio();notice('Audio playback failed. The reply remains in the conversation.');setState('ready','Ready when you are');}};
    await speechPlayer.play();
    if(epoch===speechEpoch&&!privacy)setState('speaking','Speaking','Tap stop to interrupt');
  }catch(error){
    if(epoch!==speechEpoch||privacy)return;
    notice(error.name==='NotAllowedError'?'Your browser blocked audio playback. Tap the mic to start a voice interaction.':error.name==='AbortError'?'Voice request timed out. Your text answer is still available.':error.message);
    stopAudio();setState('ready','Text answer available','Voice could not play; no browser-voice fallback was used');
  }finally{clearTimeout(timeout);if(epoch===speechEpoch)speechAbort=null;}
}
async function ask(text) {
  text=text.trim(); if (!text || busy || privacy) return;
  if(!selectedChat){notice('Workspace is still loading. Try again in a moment.');return;}
  // Deliberately narrow commands. The model cannot authorize storage or uploads.
  if (/^(?:please\s+)?(?:scan\b|save\s+(?:it|this|that|the\s+(?:page|document))\b)/i.test(text)) {
    addMessage('user',text); stopAudio();
    if (!scanImage && !captureScan()) return;
    const format = text.match(/\b(pdf|jpeg|jpg|txt|text|markdown|md)\b/i)?.[1]?.toLowerCase();
    if (format) $('documentFormat').value = ({jpeg:'jpg',text:'txt',markdown:'md'})[format] || format;
    $('documentDestination').value = /\bdrive\b/i.test(text) ? 'drive' : 'local';
    destinationChanged();
    $('scanReview').classList.remove('hidden');
    const line = 'Review the captured page, choose a format and destination, then tap Save. Nothing has been saved yet.';
    addMessage('assistant',line); speak(line); return;
  }
  busy=true; notice(''); stopAudio();
  const image=cameraStream?frame():null; useNextFrame=false;
  addMessage('user',text+(image?' · camera frame attached':''));
  setState('thinking','Thinking',image?'Looking at your captured frame':'Working on your question');
  const thisGeneration=generation;
  try {
    const result=await request('/ask',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({chat_id:selectedChat,text,model:$('modelSelect').value,image})});
    if (privacy || thisGeneration!==generation) return;
    addMessage('assistant',result.answer); $('modelInfo').textContent=`${result.model} · ${Math.round(result.model_request_ms)} ms model request`;
    loadChats().catch(()=>{});
    speak(result.answer);
  } catch(err) { if(!privacy && thisGeneration===generation) { notice(err.message); setState('ready','Try again','Check the model connection or choose another model'); } }
  finally { busy=false; }
}
async function startListening() {
  const SpeechRecognition=window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) { notice('Speech recognition is unavailable in this browser. Type a question below, or use a supported browser.'); return; }
  try { micStream=await navigator.mediaDevices.getUserMedia({audio:true}); }
  catch { notice('Microphone access was blocked. Allow it in your browser settings.'); return; }
  if (privacy) { stopAudio(); return; }
  notice(''); window.speechSynthesis?.cancel();
  audioContext=new (window.AudioContext || window.webkitAudioContext)();
  analyser=audioContext.createAnalyser(); analyser.fftSize=256;
  audioContext.createMediaStreamSource(micStream).connect(analyser);
  const samples=new Uint8Array(analyser.frequencyBinCount);
  const tick=()=>{if(!micStream)return; analyser.getByteFrequencyData(samples); const average=samples.reduce((a,b)=>a+b,0)/samples.length;
    orb.style.setProperty('--level',String(1+Math.min(.23,average/330))); levelFrame=requestAnimationFrame(tick);}; tick();
  recognition=new SpeechRecognition(); recognition.lang=navigator.language || 'en-US'; recognition.continuous=false; recognition.interimResults=true;
  let transcript='';
  recognition.onresult=(event)=>{transcript=Array.from(event.results).map(r=>r[0].transcript).join(' ');
    $('hintText').textContent=transcript;};
  recognition.onerror=(event)=>{ if(event.error!=='aborted') notice(`Speech recognition: ${event.error}. You can type instead.`); };
  recognition.onend=()=>{ const spoken=transcript.trim(); stopAudio(); if(spoken&&!privacy) ask(spoken); else if(!privacy) setState('ready','Ready when you are','Tap the mic and ask a question'); };
  try { recognition.start(); setState('listening','Listening','Speak naturally; pause to send'); }
  catch { stopAudio(); notice('Could not start speech recognition. Type a question instead.'); }
}

$('pairForm').addEventListener('submit',async(event)=>{event.preventDefault();$('pairError').textContent='';
  try {await request('/pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:$('pairCode').value})});showApp();}
  catch(err){$('pairError').textContent=err.message;}});
$('micButton').addEventListener('click',()=>{if(privacy)return;if(status==='listening'){stopAudio();setState('ready','Ready when you are');}else startListening();});
$('cameraButton').addEventListener('click',async()=>{if(privacy)return;if(cameraStream){stopCamera();useNextFrame=false;return;}
  try {cameraStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280}},audio:false});
    camera.srcObject=cameraStream;$('cameraPanel').classList.remove('hidden');useNextFrame=true;
    $('cameraButton').setAttribute('aria-label','Turn camera off');notice('Camera on. Your next question will include one frame, not a live stream.');}
  catch {notice('Camera access was blocked. Allow it in browser settings.');}});
$('privacyButton').addEventListener('click',()=>{privacy=!privacy;stopEverything();
  if(privacy) discardScan();
  $('privacyButton').classList.toggle('active',privacy);$('privacyButton').setAttribute('aria-pressed',String(privacy));
  $('privacyButton').textContent=privacy?'Privacy on':'Privacy off';
  setState(privacy?'privacy':'ready',privacy?'Capture paused':'Ready when you are',privacy?'Mic and camera are off':'Tap the mic and ask a question');
  notice(privacy?'Software capture is off. This is not a physical hardware cut-off.':'');});
$('stopButton').addEventListener('click',()=>{stopAudio();if(!privacy)setState('ready','Ready when you are');});
$('textForm').addEventListener('submit',(event)=>{event.preventDefault();if(busy||privacy){notice(privacy?'Turn Privacy off before sending. Your draft is kept.':'Please wait for the current reply. Your draft is kept.');return;}const input=$('textInput');const value=input.value;input.value='';ask(value);});
$('forgetButton').addEventListener('click',async()=>{stopEverything();try{await request('/forget',{method:'POST'});}catch{}location.reload();});
refreshStatus().then(()=>{});

function captureScan() {
  if (privacy || busy) return false;
  const image = frame();
  if (!image) { notice('Turn the camera on, point it at a page and try again.'); return false; }
  scanImage=image; $('scanPreview').src=image; $('documentText').value='';
  $('documentTitle').value='Scan '+new Date().toISOString().slice(0,10);
  $('scanReview').classList.remove('hidden');
  notice('Page captured in this browser. Review before saving.');
  return true;
}
function discardScan() {
  scanImage=null; $('scanPreview').removeAttribute('src'); $('documentText').value='';
  $('scanReview').classList.add('hidden');
}
function destinationChanged() {
  const drive = $('documentDestination').value==='drive';
  $('saveDocumentButton').textContent=drive?'Save & upload to Drive':'Save private file';
  $('destinationHelp').textContent=drive
    ? 'Uploads this reviewed file to your connected Google Drive and keeps a private GIG copy. No public sharing permissions are added.'
    : 'Private link; requires a paired device and the server online. Nothing is published publicly.';
}
function fileLink(file, parent) {
  const link=document.createElement('a'); link.href=file.url; link.textContent='Download '+file.filename;
  parent.append(link);
  if(file.drive_url) { const drive=document.createElement('a'); drive.href=file.drive_url; drive.textContent='Open in Drive'; drive.target='_blank'; drive.rel='noopener noreferrer'; parent.append(drive); }
}
async function loadFiles() {
  try {
    const result=await request('/documents'); $('savedFiles').replaceChildren();
    if (!result.documents.length) $('savedFiles').textContent='No saved files yet.';
    for(const file of result.documents) {
      const row=document.createElement('div'); row.className='saved-file'; fileLink(file,row);
      const remove=document.createElement('button'); remove.textContent='Delete local copy'; remove.type='button';
      remove.onclick=async()=>{if(!confirm('Delete '+file.filename+' from GIG? Any Drive copy stays unchanged.'))return;
        try {await request('/documents/'+file.id,{method:'DELETE'});await loadFiles();}catch(err){notice(err.message);}};
      row.append(remove); $('savedFiles').append(row);
    }
    $('savedPanel').classList.remove('hidden');
  } catch(err) {notice(err.message);}
}
$('identifyButton').onclick=()=>{if(!frame()){notice('Turn the camera on and point it at an object first.');return;}ask('Identify the main object in this image. Briefly explain what it is. Say if the view is unclear.');};
$('scanButton').onclick=()=>captureScan();
$('libraryButton').onclick=()=>loadFiles();
$('discardScanButton').onclick=()=>{generation++;discardScan();};
$('documentDestination').onchange=destinationChanged;
$('extractButton').onclick=async()=>{
  if(!scanImage||busy||privacy)return;
  const current=generation; busy=true; $('extractButton').disabled=true; notice('Extracting text locally unless you explicitly selected the cloud model…');
  try {
    const result=await request('/ask',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text:'Transcribe this page.',model:$('modelSelect').value,image:scanImage,operation:'scan'})});
    if(current!==generation||privacy)return;
    $('documentText').value=result.answer;
    notice('Text extracted. Check names, dates and numbers before saving.');
    $('modelInfo').textContent=Math.round(result.model_request_ms)+' ms extraction request';
  }catch(err){if(current===generation&&!privacy)notice(err.message);}
  finally{busy=false;$('extractButton').disabled=false;}
};
$('saveDocumentButton').onclick=async()=>{
  if(!scanImage||busy||privacy)return;
  busy=true; const current=generation; $('saveDocumentButton').disabled=true;
  // Capture immutable choices before awaiting network operations.
  const destination=$('documentDestination').value;
  try {
    const saved=await request('/documents',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({title:$('documentTitle').value,format:$('documentFormat').value,
        text:$('documentText').value,image:scanImage,consent:true})});
    if(destination==='drive'&&current===generation&&!privacy) {
      await request('/documents/'+saved.id+'/drive',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({sha256:saved.sha256,confirm_upload:true})});
    }
    if(current!==generation||privacy)return;
    await loadFiles(); notice(destination==='drive'?'Saved and uploaded to Drive. Open Your saved files for the links.':'Saved privately. Open Your saved files for the download link.');
    addMessage('assistant','Saved '+saved.filename+(destination==='drive'?' to Drive and private GIG files.':' to private GIG files.'));
  }catch(err){if(current===generation&&!privacy){notice(err.message);await loadFiles();}}
  finally{busy=false;$('saveDocumentButton').disabled=false;}
};
