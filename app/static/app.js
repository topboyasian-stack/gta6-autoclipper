const $=s=>document.querySelector(s);
const form=$('#upload');
const kickForm=$('#kickImport');
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
  }catch(err){
    message.textContent=err.message;
  }finally{
    btn.disabled=false;
    btn.innerHTML='Analyse uploaded footage <span>↗</span>';
  }
};

kickForm.onsubmit=async e=>{
  e.preventDefault();
  const btn=$('#kickImportBtn');
  btn.disabled=true;
  btn.textContent='Fetching Kick clip…';
  message.textContent='Resolving the public clip, saving it locally, and analysing it. Keep this tab open.';
  try{
    const res=await fetch('/api/import-kick',{method:'POST',body:new FormData(kickForm)});
    const data=await res.json();
    if(!res.ok)throw Error(data.detail||'Kick import failed');
    message.textContent=`Done. Imported ${data.filename||'Kick clip'} and created ${data.candidates_created} candidate clips from ${Math.round(data.duration)} seconds of footage.`;
    kickForm.reset();
    await load();
  }catch(err){
    message.textContent=err.message;
  }finally{
    btn.disabled=false;
    btn.innerHTML='Import &amp; analyse Kick clip <span>↗</span>';
  }
};

async function decide(id,status){
  const r=await fetch('/api/clips/'+id+'/decision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});
  if(!r.ok){const d=await r.json();alert(d.detail||'Could not save decision');return}
  load();
}

async function load(){
  try{
    const [s,c]=await Promise.all([fetch('/api/stats').then(r=>r.json()),fetch('/api/clips').then(r=>r.json())]);
    Object.keys(s).forEach(k=>{if($('#'+k))$('#'+k).textContent=s[k]});
    const host=$('#clips');
    host.innerHTML='';
    if(!c.length){host.innerHTML='<p class="empty">No clips yet. Add permitted footage to begin.</p>';return}
    c.forEach(x=>{
      const el=document.createElement('article');
      el.className='clip';
      const video=document.createElement('video');
      video.src=x.preview;
      video.controls=true;
      video.playsInline=true;
      const title=document.createElement('strong');
      title.textContent=x.filename+' · '+Math.round(x.start)+'s';
      const info=document.createElement('p');
      info.textContent=(x.creator||'Source not named')+' · '+x.status.toUpperCase();
      el.append(video,title,info);
      if(x.source_url){
        const source=document.createElement('a');
        source.href=x.source_url;
        source.textContent='Open source';
        source.target='_blank';
        source.rel='noopener noreferrer';
        source.className='source-link';
        el.append(source);
      }
      if(x.status==='pending'){
        const actions=document.createElement('div');
        actions.className='actions';
        const yes=document.createElement('button');
        yes.textContent='Approve';
        yes.onclick=()=>decide(x.id,'approved');
        const no=document.createElement('button');
        no.className='reject';
        no.textContent='Reject';
        no.onclick=()=>decide(x.id,'rejected');
        actions.append(yes,no);
        el.append(actions);
      }
      host.append(el);
    });
  }catch(err){
    $('#clips').innerHTML='<p class="empty">Could not load the review queue. Check that the local app is running, then refresh.</p>';
  }
}
load();