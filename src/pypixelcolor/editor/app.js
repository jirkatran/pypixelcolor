'use strict';
const $=id=>document.getElementById(id), W=96,H=16;
const frame=document.createElement('canvas');frame.width=W;frame.height=H;
const ctx=frame.getContext('2d',{willReadFrequently:true}),view=$('display'),v=view.getContext('2d');
let tool='text',history=[],drawing=false,lastPoint=null,saveTimer,ready=false;
const fields=['text','size','align','color','background','ink','address','animation','speed'];
function status(message,type=''){$('status').textContent=message;$('status').className=type;}
function snapshot(){history.push(ctx.getImageData(0,0,W,H));if(history.length>40)history.shift();}
let motionFrame=null,motionStart=0;
function preview(save=true){v.fillStyle='#050506';v.fillRect(0,0,view.width,view.height);const data=(motionFrame||ctx).getImageData(0,0,W,H).data;for(let y=0;y<H;y++)for(let x=0;x<W;x++){const i=(y*W+x)*4;v.fillStyle=`rgb(${data[i]},${data[i+1]},${data[i+2]})`;if($('grid').checked){if(data[i]+data[i+1]+data[i+2]<12)v.fillStyle='#151619';v.beginPath();v.arc(x*12+6,y*12+6,4.5,0,Math.PI*2);v.fill();}else v.fillRect(x*12,y*12,12,12);}if(!ready||!save)return;clearTimeout(saveTimer);saveTimer=setTimeout(()=>{try{localStorage.setItem('bazar-led-draft',JSON.stringify(project()));}catch{}},300);}
function project(){return{version:1,width:W,height:H,image:frame.toDataURL('image/png'),settings:Object.fromEntries(fields.map(id=>[id,$(id).value]))};}
function render(remember=true){
 motionStart=0;
 if(remember)snapshot();
 ctx.fillStyle=$('background').value;ctx.fillRect(0,0,W,H);
 const scale=Number($('size').value)>=14?2:1;
 const lines=$('text').value.split('\n');
 const lineHeight=7*scale,gap=scale,total=lines.length*lineHeight+(lines.length-1)*gap;
 const top=Math.floor((H-total)/2);
 ctx.fillStyle=$('color').value;
 lines.forEach((line,i)=>{
  const width=LED_FONT.width(line,scale);
  const x=$('align').value==='center'?Math.floor((W-width)/2):$('align').value==='left'?0:W-width;
  LED_FONT.draw(ctx,line,x,top+i*(lineHeight+gap),scale);
 });
 const overflow=lines.some(line=>LED_FONT.width(line,scale)>W)||total>H;
 $('hint').textContent=$('animation').value==='scroll_left'?'← Orientační náhled; panel používá výchozí písmo 16 px.':overflow?'Text přesahuje panel. Zmenši písmo nebo zkrať text.':'Tento náhled odpovídá odesílanému obrázku 96 × 16 px.';
 preview();
}

function selectTool(value){tool=value;for(const id of ['pencil','eraser','textTool'])$(id).setAttribute('aria-pressed',String((id==='textTool'?'text':id)===value));}
$('pencil').onclick=()=>selectTool('pencil');$('eraser').onclick=()=>selectTool('eraser');$('textTool').onclick=()=>selectTool('text');
for(const id of ['text','size','align','color','background'])$(id).addEventListener('input',()=>{selectTool('text');render();});
for(const id of ['ink','address'])$(id).addEventListener('input',preview);
$('render').onclick=()=>render();$('grid').onchange=preview;
function point(e){const r=view.getBoundingClientRect();return{x:Math.min(95,Math.max(0,Math.floor((e.clientX-r.left)/r.width*W))),y:Math.min(15,Math.max(0,Math.floor((e.clientY-r.top)/r.height*H)))};}
function paint(e){const p=point(e);ctx.fillStyle=tool==='eraser'?$('background').value:$('ink').value;const a=lastPoint||p,n=Math.max(Math.abs(p.x-a.x),Math.abs(p.y-a.y),1);for(let i=0;i<=n;i++)ctx.fillRect(Math.round(a.x+(p.x-a.x)*i/n),Math.round(a.y+(p.y-a.y)*i/n),1,1);lastPoint=p;preview();}
view.onpointerdown=e=>{if(tool==='text'||$('animation').value==='scroll_left')return;snapshot();drawing=true;lastPoint=null;view.setPointerCapture(e.pointerId);paint(e);};view.onpointermove=e=>{if(drawing)paint(e);};view.onpointerup=view.onpointercancel=()=>{drawing=false;lastPoint=null;};
$('undo').onclick=()=>{if(history.length){ctx.putImageData(history.pop(),0,0);preview();}};
$('clear').onclick=()=>{snapshot();ctx.fillStyle=$('background').value;ctx.fillRect(0,0,W,H);preview();};
const quickTextKey='bazar-led-quick-texts';
let quickTexts=['BAZAR','AKCE -30 %','OTEVRENO'];
try{
 const saved=localStorage.getItem(quickTextKey);
 if(saved!==null){
  const parsed=JSON.parse(saved);
  if(Array.isArray(parsed))quickTexts=[...new Set(parsed.filter(text=>typeof text==='string'&&text.trim()&&text.length<=180))];
 }
}catch{$('quickTextInfo').textContent='Uložené texty se nepodařilo načíst.';}
function updateQuickTexts(next){
 try{localStorage.setItem(quickTextKey,JSON.stringify(next));}
 catch{$('quickTextInfo').textContent='Texty nelze uložit. Zkontroluj volné místo a povolení ukládání v prohlížeči.';return false;}
 quickTexts=next;renderQuickTexts();return true;
}
function renderQuickTexts(){
 $('quickTexts').replaceChildren();
 for(const text of quickTexts){
  const item=document.createElement('div');item.className='quick-text';
  const load=document.createElement('button');load.type='button';load.className='quick-text-load';load.textContent=text;load.title=text;
  load.onclick=()=>{$('text').value=text;selectTool('text');render();$('quickTextInfo').textContent='Text byl vložen do editoru.';};
  const remove=document.createElement('button');remove.type='button';remove.className='quick-text-delete';remove.textContent='×';remove.title='Smazat text';remove.setAttribute('aria-label',`Smazat text: ${text}`);
  remove.onclick=()=>{if(updateQuickTexts(quickTexts.filter(value=>value!==text)))$('quickTextInfo').textContent='Text byl smazán z rychlého startu.';};
  item.append(load,remove);$('quickTexts').append(item);
 }
 if(!quickTexts.length)$('quickTextInfo').textContent='Zatím tu nejsou žádné texty. Napiš text a ulož ho tlačítkem výše.';
}
$('saveQuickText').onclick=()=>{
 const text=$('text').value.trim();
 if(!text){$('quickTextInfo').textContent='Nejdřív napiš text do editoru.';return;}
 if(quickTexts.includes(text)){$('quickTextInfo').textContent='Tento text už je v rychlém startu uložený.';return;}
 if(updateQuickTexts([...quickTexts,text]))$('quickTextInfo').textContent='Text byl uložen do rychlého startu.';
};
renderQuickTexts();

function download(blob,name){const a=document.createElement('a'),url=URL.createObjectURL(blob);a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('export').onclick=()=>frame.toBlob(blob=>download(blob,'banner-96x16.png'));
$('save').onclick=()=>download(new Blob([JSON.stringify(project(),null,2)],{type:'application/json'}),'banner.led.json');
function loadImage(src){return new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error('Obrázek nelze načíst.'));image.src=src;});}
async function restore(data){if(data.version!==1||data.width!==W||data.height!==H||typeof data.image!=='string'||!data.image.startsWith('data:image/png;base64,'))throw new Error('Neplatný projekt 96 × 16.');const image=await loadImage(data.image);if(image.width!==W||image.height!==H)throw new Error('Neplatné rozměry projektu.');snapshot();for(const id of fields)if(typeof data.settings?.[id]==='string')$(id).value=id==='size'?({'9':'7','12':'7','15':'14'}[data.settings[id]]||data.settings[id]):data.settings[id];connectionUI({});motionSettings();ctx.drawImage(image,0,0);preview();}
$('load').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;if(file.size>1000000)throw new Error('Projekt je příliš velký.');await restore(JSON.parse(await file.text()));status('Projekt byl načten.');}catch(err){status(err.message,'error');}finally{e.target.value='';}};
$('image').onchange=async e=>{let url;try{const file=e.target.files[0];if(!file)return;if(file.size>10000000)throw new Error('Obrázek musí být menší než 10 MB.');url=URL.createObjectURL(file);const image=await loadImage(url);snapshot();ctx.fillStyle=$('background').value;ctx.fillRect(0,0,W,H);const scale=Math.min(W/image.width,H/image.height),w=Math.max(1,Math.round(image.width*scale)),h=Math.max(1,Math.round(image.height*scale));ctx.imageSmoothingEnabled=false;ctx.drawImage(image,Math.floor((W-w)/2),Math.floor((H-h)/2),w,h);preview();selectTool('pencil');status('Obrázek vložen.');}catch(err){status(err.message,'error');}finally{if(url)URL.revokeObjectURL(url);e.target.value='';}};
let connectedAddress='',btBusy=false,knownDevices=[];
try{const saved=JSON.parse(localStorage.getItem('bazar-led-devices')||'[]');if(Array.isArray(saved))knownDevices=saved.filter(d=>typeof d.name==='string'&&typeof d.address==='string');}catch{}
function deviceOptions(found=[]){
 const selected=$('address').value.trim();
 for(const device of found){const existing=knownDevices.find(d=>d.address===device.address);if(existing)existing.name=device.name;else knownDevices.push(device);}
 if(selected&&!knownDevices.some(d=>d.address===selected))knownDevices.push({name:'Ručně zadaný panel',address:selected});
 $('devices').replaceChildren(new Option('Vyber banner…',''));
 for(const device of knownDevices){const visible=found.some(d=>d.address===device.address);$('devices').add(new Option(`${device.name} · ${visible?'v dosahu':'uložený'} · ${device.address}`,device.address));}
 $('devices').value=selected;
 try{localStorage.setItem('bazar-led-devices',JSON.stringify(knownDevices));}catch{}
}
function connectionUI(data){
 if(typeof data.connected==='boolean')connectedAddress=data.connected?data.address:'';
 const matches=connectedAddress&&connectedAddress===$('address').value.trim();
 $('connectionState').textContent=connectedAddress?`● Připojeno: ${connectedAddress}${matches?'':' (jiný než vybraný panel)'}`:'● Nepřipojeno';
 $('connectionState').classList.toggle('online',Boolean(connectedAddress));
 for(const id of ['scan','connect','send','devices','address'])$(id).disabled=btBusy;
 $('disconnect').disabled=btBusy||!connectedAddress;
 $('connect').textContent=matches?'Připojeno':'Připojit';$('connect').disabled=btBusy||Boolean(matches);
}
async function api(action,payload={}){const response=await fetch('/api/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();connectionUI(data);if(!response.ok)throw new Error(data.error||'Operace selhala.');return data;}
async function btOperation(task){if(btBusy)return;btBusy=true;connectionUI({});try{await task();}catch(err){status(err.message,'error');}finally{btBusy=false;connectionUI({});}}
$('devices').onchange=()=>{$('address').value=$('devices').value;connectionUI({});preview();};
$('address').addEventListener('input',()=>{$('devices').value=$('address').value.trim();connectionUI({});});
$('scan').onclick=()=>btOperation(async()=>{
 $('scan').textContent='Hledám…';$('scanInfo').textContent='Prohledávám okolí po dobu 6 sekund…';
 try{const data=await api('scan');deviceOptions(data.devices);$('scanInfo').textContent=data.devices.length?`Nalezeno bannerů: ${data.devices.length}. Vyber jeden ze seznamu.`:'Žádný banner nebyl nalezen. Zapni panel a odpoj mobilní aplikaci. Uložené panely zůstávají v seznamu.';}
 catch(err){$('scanInfo').textContent='Vyhledávání selhalo.';throw err;}
 finally{$('scan').textContent='⌕ Vyhledat bannery';}
});
$('connect').onclick=()=>btOperation(async()=>{const address=$('address').value.trim();if(!address)throw new Error('Nejdřív vyber banner nebo zadej adresu.');status('Připojuji vybraný panel…');await api('connect',{address});deviceOptions();status('Panel je připojený a připravený k odesílání.','success');});
$('disconnect').onclick=()=>btOperation(async()=>{await api('disconnect');status('Panel byl odpojen.');});
$('send').onclick=()=>btOperation(async()=>{
 const address=$('address').value.trim();if(!address)throw new Error('Nejdřív vyber banner nebo zadej adresu.');
 $('send').textContent='Odesílám…';status('Připojuji vybraný panel a odesílám banner…');
 try{const data=await api('send',{address,image:frame.toDataURL('image/png'),animation:$('animation').value,text:$('text').value,speed:Number($('speed').value),size:Number($('size').value),color:$('color').value,background:$('background').value});deviceOptions();status(data.message,'success');}
 finally{$('send').textContent='Odeslat do panelu ↗';}
});
setInterval(()=>{if(!btBusy)btOperation(async()=>{await api('status');});},5000);
function motionSettings(){
 const scrolling=$('animation').value==='scroll_left';
 $('motionNote').hidden=!scrolling;$('speed').disabled=!scrolling;
 $('speedValue').value=$('speed').value;
 if(scrolling){$('size').value='16';$('background').value='#000000';}
 for(const id of ['align','pencil','eraser','image','size','background'])$(id).disabled=scrolling;
 motionStart=0;motionFrame=null;preview();
}
$('animation').onchange=()=>{motionSettings();render();};
$('speed').oninput=()=>{motionSettings();preview();};
const motionCanvas=document.createElement('canvas');motionCanvas.width=W;motionCanvas.height=H;
const motionContext=motionCanvas.getContext('2d',{willReadFrequently:true});
function animate(time){
 if(ready&&$('animation').value==='scroll_left'){
  if(!motionStart)motionStart=time;
  motionContext.fillStyle=$('background').value;motionContext.fillRect(0,0,W,H);
  motionContext.font=`bold ${$('size').value}px monospace`;motionContext.textBaseline='middle';motionContext.fillStyle=$('color').value;
  const text=$('text').value.replace(/\n/g,' '),width=motionContext.measureText(text).width;
  const travel=W+width+16,position=((time-motionStart)/1000*(8+Number($('speed').value)*.7))%travel;
  motionContext.fillText(text,W-position,8);motionFrame=motionContext;preview(false);
 }else if(motionFrame){motionFrame=null;preview(false);}
 requestAnimationFrame(animate);
}
requestAnimationFrame(animate);
async function init(){render(false);try{const response=await fetch('/api/config');const config=await response.json();$('address').value=config.address;const saved=localStorage.getItem('bazar-led-draft');if(saved)await restore(JSON.parse(saved));history=[];ready=true;preview();deviceOptions();motionSettings();await api('status');}catch(err){status('Návrh je připraven. '+err.message,'error');}}
init();
