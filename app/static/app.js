const $=s=>document.querySelector(s);
const form=$('#upload');
const kickForm=$('#kickImport');
const liveForm=$('#liveForm');
const message=$('#message');
$('#refresh').onclick=load;
form.file.onchange=()=>$('#filename').textContent=form.file.files[0]?.name||'Choose a video file';

form.onsubmit=async e=>{
  e.preventDefault();
  const btn=$('#uploadBtn');
  btn.disabled=true;
  btn.textContent='Analysing… this may take a while';
  message.textContent='Uploading and processing on this machine. Keep this tab open.';
  try{
    const res=await fetch('/api/upload',{method:'POST',body:new FormData(form)});
    const data=await res.json();
    if(!res.ok)throw Error(data.detail||'Upload failed');
    message.textContent=`Done. Created ${data.candidates_created} candidate clips from ${Math.round(data.duration)} seconds of footage.`;
    form.reset();
    $('#filename').textContent='Choose a video file';
    await load();
  }catch(err){message.textContent=err.message}
  finally{btn.disabled=false;btn.innerHTML='Analyse uploaded footage <span>↗</span>'}
};

kickForm.onsubmit=async e=>{
  e.preventDefault();
  const btn=$('#kickImportBtn');
  btn.disabled=true;btn.textContent='Fetching Kick clip…';
  message.textContent='Resolving the public clip, saving it locally, and analysing it. Keep this tab open.';
  try{
    const res=await fetch('/api/import-kick',{method:'POST',body:new FormData(kickForm)});
    const data=await res.json();
    if(!res.ok)throw Error(data.detail||'Kick import failed');
    message.textContent=`Done. Imported ${data.filename||'Kick clip'} and created ${data.candidates_created} candidate clips from ${Math.round(data.duration)} seconds of footage.`;
    kickForm.reset();
    const creator=kickForm.querySelector('[name="creator"]');if(creator)creator.value='3rdcollector';
    await load();
  }catch(err){message.textContent=err.message}
  finally{btn.disabled=false;btn.innerHTML='Import &amp; analyse Kick clip <span>↗</span>'}
};

liveForm.onsubmit=async e=>{
  e.preventDefault();
  const btn=$('#liveStartBtn');
  btn.disabled=true;btn.textContent='Starting authorized feed…';
  message.textContent='Connecting to the feed. If it is valid, completed segments will appear in the review queue.';
  try{
    const res=await fetch('/api/live/start',{method:'POST',body:new FormData(liveForm)});
    const data=await res.json();
    if(!res.ok)throw Error(data.detail||'Could not start live capture');
    message.textContent='Live capture started. Session '+data.session_id.slice(0,8)+'.';
    await load();
  }catch(err){message.textContent=err.message}
  finally{btn.disabled=false;btn.innerHTML='Start live clipping ↗'}
};

async function decide(id,status){
  const r=await fetch('/api/clips/'+id+'/decision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});
  if(!r.ok){const d=await r.json();alert(d.detail||'Could not save decision');return}
  await load();
}

async function uploadPrivately(id,title,description,button){
  button.disabled=true;button.textContent='Uploading privately…';
  try{
    const r=await fetch('/api/clips/'+id+'/youtube-upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,description})});
    const d=await r.json();
    if(!r.ok)throw Error(d.detail||'YouTube upload failed');
    message.textContent='Uploaded privately to YouTube. Review it there before making it public.';
    await load();
  }catch(err){message.textContent=err.message;button.disabled=false;button.textContent='Upload privately to YouTube'}
}

async function publishPublicly(id,button){
  if(!confirm('This will make the YouTube video PUBLIC. Have you reviewed the private upload and confirmed the rights?'))return;
  button.disabled=true;button.textContent='Publishing…';
  try{
    const r=await fetch('/api/clips/'+id+'/youtube-publish',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const d=await r.json();
    if(!r.ok)throw Error(d.detail||'Publishing failed');
    message.textContent='YouTube video is now public.';
    await load();
    window.open(d.url,'_blank','noopener');
  }catch(err){message.textContent=err.message;button.disabled=false;button.textContent='Publish publicly on YouTube'}
}

async function loadLive(){
  const host=$('#liveSessions');
  if(!host)return;
  try{
    const rows=await fetch('/api/live').then(r=>r.json());
    host.innerHTML='';
    if(!rows.length){host.innerHTML='<p class="empty">No live capture sessions yet.</p>';return}
    rows.forEach(x=>{
      const card=document.createElement('div');card.className='live-session';
      const title=document.createElement('strong');title.textContent=x.creator+' · '+x.status.toUpperCase();
      const sub=document.createElement('p');sub.textContent=x.source_descriptor+' · '+x.segment_seconds+'s segments'+(x.error?' · '+x.error:'');
      card.append(title,sub);
      if(x.status==='recording'){
        const stop=document.createElement('button');stop.className='stop-live';stop.textContent='Stop capture';
        stop.onclick=async()=>{
          stop.disabled=true;stop.textContent='Stopping…';
          try{const r=await fetch('/api/live/'+x.id+'/stop',{method:'POST'});const d=await r.json();if(!r.ok)throw Error(d.detail||'Stop failed');message.textContent='Stopping the feed; final segments are being processed.';await loadLive()}
          catch(err){message.textContent=err.message;stop.disabled=false;stop.textContent='Stop capture'}
        };
        card.append(stop);
      }
      host.append(card);
    });
  }catch(err){host.innerHTML='<p class="empty">Unable to load live sessions.</p>'}
}

async function load(){
  try{
    const [s,c,y]=await Promise.all([
      fetch('/api/stats').then(r=>r.json()),
      fetch('/api/clips').then(r=>r.json()),
      fetch('/api/youtube/status').then(r=>r.json())
    ]);
    Object.keys(s).forEach(k=>{if($('#'+k))$('#'+k).textContent=s[k]});
    $('#youtubeStatus').textContent=y.connected?'YouTube is connected. Approved clips can be uploaded privately.':(y.configured?'OAuth file found. Use Connect YouTube to authorize your channel.':'Setup needed: create a Google OAuth client file at data/client_secrets.json. See docs/YOUTUBE_AND_LIVE_SOURCES.md.');
    const host=$('#clips');host.innerHTML='';
    if(!c.length)host.innerHTML='<p class="empty">No clips yet. Add permitted footage to begin.</p>';
    c.forEach(x=>{
      const el=document.createElement('article');el.className='clip';
      const video=document.createElement('video');video.src=x.preview;video.controls=true;video.playsInline=true;
      const title=document.createElement('strong');title.textContent=x.filename+' · '+Math.round(x.start)+'s';
      const info=document.createElement('p');info.textContent=(x.creator||'Source not named')+' · '+x.status.toUpperCase();
      el.append(video,title,info);
      if(x.source_url&&x.source_url.startsWith('https://')){const source=document.createElement('a');source.href=x.source_url;source.textContent='Open source';source.target='_blank';source.rel='noopener noreferrer';source.className='source-link';el.append(source)}
      if(x.status==='pending'){
        const actions=document.createElement('div');actions.className='actions';
        const yes=document.createElement('button');yes.textContent='Approve';yes.onclick=()=>decide(x.id,'approved');
        const no=document.createElement('button');no.className='reject';no.textContent='Reject';no.onclick=()=>decide(x.id,'rejected');
        actions.append(yes,no);el.append(actions);
      }
      if(x.status==='approved'&&!x.youtube_video_id){
        const titleInput=document.createElement('input');titleInput.value=(x.filename.replace(/\.[^.]+$/,'')+' #Shorts').slice(0,100);titleInput.setAttribute('aria-label','YouTube title');
        const descInput=document.createElement('textarea');descInput.value='Gaming highlight. #shorts #gaming';descInput.setAttribute('aria-label','YouTube description');
        const upload=document.createElement('button');upload.textContent='Upload privately to YouTube';upload.onclick=()=>uploadPrivately(x.id,titleInput.value,descInput.value,upload);
        el.append(titleInput,descInput,upload);
      }
      if(x.youtube_video_id){
        const link=document.createElement('a');link.href='https://www.youtube.com/watch?v='+encodeURIComponent(x.youtube_video_id);link.target='_blank';link.rel='noopener noreferrer';link.className='source-link';link.textContent=x.status==='published'?'Open public YouTube video':'Open private YouTube upload';el.append(link);
        if(x.status!=='published'){
          const pub=document.createElement('button');pub.textContent='Publish publicly on YouTube';pub.onclick=()=>publishPublicly(x.id,pub);el.append(pub);
        }
      }
      host.append(el);
    });
    await loadLive();
  }catch(err){
    $('#clips').innerHTML='<p class="empty">Could not load the review queue. Check that the local app is running, then refresh.</p>';
  }
}
load();
setInterval(loadLive,4000);