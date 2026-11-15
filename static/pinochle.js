const $ = id => document.getElementById(id);
const suits = {S:'♠',H:'♥',D:'♦',C:'♣'};
let state, version = -1, busy = false, sending = false, lastMessage = 0;
let selected = new Set();
function face(c) { const f=c.split(':')[0]; return f.slice(0,-1)+suits[f.slice(-1)]; }
function node(tag, text, className) { const el=document.createElement(tag); el.textContent=text; if(className)el.className=className; return el; }
function button(text, handler, disabled=false) { const el=node('button',text); el.type='button'; el.disabled=disabled; el.onclick=handler; return el; }
function card(c) {
  const f=c.split(':')[0], s=f.slice(-1), el=node('button',f.slice(0,-1),'card'+('HD'.includes(s)?' red':''));
  el.type='button'; el.append(node('small',suits[s]),node('b',suits[s]));
  el.setAttribute('aria-label',f.slice(0,-1)+' of '+({S:'spades',H:'hearts',D:'diamonds',C:'clubs'}[s]));
  return el;
}
async function refresh() {
  try {
    const response=await fetch('state/',{cache:'no-store'});
    if(!response.ok)throw new Error('Could not reach this room. It may have reset; return home to create a new table.');
    const next=await response.json();
    // Ignore an older response if a move and a poll complete out of order.
    if(state && next.version < state.version)return;
    state=next; $('connection').textContent='● Connected'; renderMessages(state.messages||[]);
    if(version!==state.version){version=state.version;render();}
  } catch(e){$('connection').textContent='Reconnecting…';$('error').textContent=e.message;}
}
async function move(action, extra={}) {
  if(busy||!state)return;
  busy=true; $('error').textContent='';
  try{
    const response=await fetch('action/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value},body:JSON.stringify({action,version:state.version,...extra})});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not save that move.');
    if(action==='exchange')selected.clear();
  }catch(e){$('error').textContent=e.message;}
  finally{busy=false;await refresh();}
}
function render() {
  const s=state, me=s.players.find(p=>p.you), phase=s.phase, controls=$('controls');
  $('round').textContent=s.round?`PINOCHLE · HAND ${s.round}`:'PINOCHLE · WAITING FOR FOUR';
  $('message').textContent=s.message; $('last-move').textContent=s.last_move||'';
  const phaseNames={lobby:'Gather your four.',bidding:'Time to bid.',trump:'Choose trump.',passing:'A private exchange.',melding:'Show your meld.',playing:'Play the trick.',trick_review:'A trick well played.',round_over:'The hand is scored.',finished:`Team ${(s.winner??0)+1} wins!`};
  $('status').textContent=phaseNames[phase];
  $('contract').textContent=s.bid?`Bid ${s.bid} · ${s.bidder!==null?s.players[s.bidder].name:''}${s.trump?' · Trump '+suits[s.trump]:''}`:'';
  $('players').replaceChildren();s.players.forEach(p=>{
    const row=node('div','','player'+(p.turn&&['bidding','trump','playing'].includes(phase)?' current':''));
    row.append(node('strong',`${p.seat+1}. ${p.name}${p.you?' (you)':''}`),node('small',`Team ${p.team+1} · ${p.count} cards${p.ready?' · Ready':''}${p.passed&&phase==='bidding'?' · Passed':''}${p.host?' · Host':''}`));$('players').append(row);
  });
  $('scoreboard').replaceChildren();(s.scores||[0,0]).forEach((score,i)=>{
    const names=s.players.filter(p=>p.team===i).map(p=>p.name).join(' & ')||'Seats open';
    const row=node('div');row.append(node('strong',`Team ${i+1} · ${score}`),node('small',names),node('small',`This hand: ${s.trick_points?.[i]||0} trick points · ${s.tricks_won?.[i]||0} tricks`));$('scoreboard').append(row);
  });
  const r=s.rules;
  $('rules').textContent=`80 cards · Target ${r.target} · Opening bid ${r.opening_bid} · ${r.pass_count} cards exchanged · Minimum meld ${r.minimum_meld} · Minimum trick points ${r.minimum_tricks} (must win a trick) · Trump marriage ${r.marriage_required?'required':'optional'} · Bids above 60 ${r.bid_fives?'in fives':'any integer'} · Must beat ${r.must_beat?'yes':'no'}. Rules stay fixed for rematches.`;
  $('trick').replaceChildren();
  (s.trick||[]).forEach(e=>{const item=node('div');const c=card(e.card);c.disabled=true;item.append(c,node('small',s.players[e.seat].name));$('trick').append(item);});
  if(!(s.trick||[]).length&&(s.last_trick||[]).length){const line=node('p','Previous trick: '+s.last_trick.map(e=>s.players[e.seat].name+' '+face(e.card)).join(' · '));$('trick').append(line);}
  controls.replaceChildren();
  if(['lobby','round_over','finished'].includes(phase)&&me.host)controls.append(button(phase==='lobby'?'Deal the first hand':phase==='finished'?'Play again':'Deal the next hand',()=>move(phase==='lobby'?'start':phase==='finished'?'rematch':'next'),s.players.length!==4));
  if(phase==='bidding'&&s.your_turn){
    const form=node('form');form.className='pin-bid';const label=node('label','Your bid');label.htmlFor='bid-input';
    const input=node('input');input.id='bid-input';input.type='number';input.min=Math.max(r.opening_bid,s.bid+1);input.max=10000;input.step=1;
    input.value=r.bid_fives&&Number(input.min)>60?Math.ceil(Number(input.min)/5)*5:input.min;input.required=true;
    const submit=node('button','Bid');submit.type='submit';form.append(label,input,submit);form.onsubmit=e=>{e.preventDefault();move('bid',{bid:Number(input.value)});};
    controls.append(form,button('Pass',()=>move('pass')));
  }
  if(phase==='trump'&&s.your_turn){
    let valid=0;Object.entries(suits).forEach(([suit,symbol])=>{const has=['K','Q'].every(rank=>me.hand.some(c=>c.split(':')[0]===rank+suit));const disabled=r.marriage_required&&!has;if(!disabled)valid++;controls.append(button(symbol+' Trump',()=>move('trump',{suit}),disabled));});
    if(!valid)controls.append(button('No marriage · concede bid',()=>move('concede')));
  }
  if(['melding','trick_review'].includes(phase))controls.append(button(me.ready?'Waiting for the others…':phase==='melding'?'Meld reviewed · Ready':'Trick reviewed · Ready',()=>move('ready'),me.ready));
  const exchange=phase==='passing'&&me.team===s.bidder%2&&!s.exchange_submitted;
  if(exchange){controls.append(button(`Pass ${r.pass_count} selected cards`,()=>move('exchange',{cards:[...selected]}),selected.size!==r.pass_count));}
  $('hand-count').textContent=me.hand.length+' cards';
  const who=s.players.find(p=>p.turn)?.name;
  $('hint').textContent=exchange?`Select exactly ${r.pass_count} cards, then confirm above. Your partner cannot see them until both submit.`:phase==='passing'?'Waiting for the bidding partners’ private exchange.':phase==='playing'?(s.your_turn?'Your turn. Highlighted cards are legal to play.':`${who} is playing. Your hand stays private.`):['bidding','trump'].includes(phase)?(s.your_turn?'Your turn. Choose an option above.':`Waiting for ${who}.`):phase==='lobby'?'Four players are required. Join order sets your partnership.':'Review the table and use the controls above.';
  $('hand').replaceChildren();
  const sorted=[...me.hand].sort((a,b)=>'SHDC'.indexOf(a.split(':')[0].slice(-1))-'SHDC'.indexOf(b.split(':')[0].slice(-1))||['A','10','K','Q','J'].indexOf(a.split(':')[0].slice(0,-1))-['A','10','K','Q','J'].indexOf(b.split(':')[0].slice(0,-1)));
  sorted.forEach(c=>{const el=card(c), legal=s.legal.includes(c);el.disabled=!(exchange||legal);el.classList.toggle('legal',legal);el.classList.toggle('selected',selected.has(c));el.setAttribute('aria-pressed',String(selected.has(c)));el.onclick=()=>{if(exchange){if(selected.has(c))selected.delete(c);else if(selected.size<r.pass_count)selected.add(c);render();}else move('card',{card:c});};$('hand').append(el);});
  $('melds').replaceChildren();(s.melds||[]).forEach((m,i)=>{const section=node('section','','pin-meld');section.append(node('h3',`${s.players[i].name} · ${m.points} meld`),node('p',m.details.map(d=>`${d.count} × ${d.name}: ${d.points}`).join(' · ')||'No meld'),node('p',m.cards.map(face).join(' ')));$('melds').append(section);});
  $('meld-section').hidden=!(s.melds||[]).length;
  if(phase==='melding')$('meld-section').open=true;
  $('history').replaceChildren();[...(s.history||[])].reverse().forEach(h=>{const line=node('p',`Hand ${h.round} · Team ${h.bid_team+1} ${h.made?'made':'missed'} ${h.bid} · Meld ${h.meld.join(' / ')} · Trick points ${h.trick_points.join(' / ')} · Change ${h.delta.join(' / ')} · Totals ${h.scores.join(' / ')}`);$('history').append(line);});
}
function renderMessages(messages){
  const log=$('chat-messages'), fresh=messages.filter(m=>m.id>lastMessage);if(!fresh.length)return;
  const bottom=log.scrollHeight-log.scrollTop-log.clientHeight<60;
  fresh.forEach(m=>{const row=node('div','','chat-message'+(m.kind==='event'?' game-event':''));row.append(node('strong',m.kind==='event'?'Server · Game event':m.author+' · Player'),node('span',m.text));log.append(row);lastMessage=m.id;});
  while(log.children.length>80)log.firstElementChild.remove();if(bottom)log.scrollTop=log.scrollHeight;
}
$('chat-form').onsubmit=async e=>{e.preventDefault();if(sending)return;const input=$('chat-input'),text=input.value.trim();if(!text)return;sending=true;$('chat-send').disabled=true;$('chat-error').textContent='';try{const response=await fetch('chat/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value},body:JSON.stringify({text})});const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not send.');input.value='';await refresh();}catch(error){$('chat-error').textContent=error.message;}finally{sending=false;$('chat-send').disabled=false;}};
$('copy').onclick=async()=>{try{await navigator.clipboard.writeText(location.href);$('copy').textContent='Invite link copied ✓';}catch{$('error').textContent='Copy this link: '+location.href;}};
async function poll(){await refresh();setTimeout(poll,1500);}poll();
