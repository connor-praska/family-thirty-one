const code = document.body.dataset.code;
let state, busy = false, lastVersion = -1;
let lastMessageId = 0, seenKnock = '', sendingChat = false;
const $ = id => document.getElementById(id);
const symbols = {S:'♠',H:'♥',D:'♦',C:'♣'};
function card(el, value) {
  el.replaceChildren(); el.classList.remove('red');
  if (!value) { el.textContent = '—'; return; }
  const rank = value.slice(0,-1), suit = value.slice(-1);
  el.classList.toggle('red', suit === 'H' || suit === 'D');
  el.setAttribute('aria-label', `${rank} of ${{S:'spades',H:'hearts',D:'diamonds',C:'clubs'}[suit]}`);
  el.append(document.createTextNode(rank));
  const small = document.createElement('small'); small.textContent = symbols[suit];
  const big = document.createElement('b'); big.textContent = symbols[suit]; el.append(small,big);
}
async function refresh() {
  try {
    const response = await fetch('state/', {cache:'no-store'});
    if (!response.ok) throw new Error('Could not reconnect. Refresh this page to rejoin.');
    state = await response.json(); $('connection').textContent = '● Connected';
    renderMessages(state.messages || []);
    if (state.version !== lastVersion) { lastVersion = state.version; render(); }
  } catch (e) { $('connection').textContent = 'Reconnecting…'; $('error').textContent = e.message; }
}
async function act(action, index) {
  if (busy || !state) return;
  busy = true; $('error').textContent = '';
  try {
    const response = await fetch('action/', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value}, body:JSON.stringify({action,index,version:state.version})});
    const result = await response.json(); if (!response.ok) throw new Error(result.error || 'Your move could not be saved.');
  } catch(e) { $('error').textContent = e.message; }
  finally { busy = false; await refresh(); }
}
function render() {
  const s = state, me = s.players.find(p=>p.you), playing = s.phase === 'playing';
  $('round').textContent = s.round ? `ROUND ${s.round} · ${s.phase === 'finished' ? 'GAME COMPLETE' : 'FAMILY TIME'}` : 'WAITING FOR YOUR FAMILY';
  $('message').textContent = s.message;
  $('last-move').textContent = s.last_move || '';
  const notice = $('knock-notice');
  notice.hidden = !s.knock_notice;
  notice.textContent = s.knock_notice || '';
  if (s.knock_key && s.knock_key !== seenKnock) {
    notice.classList.remove('knock-arrived');
    void notice.offsetWidth;
    notice.classList.add('knock-arrived');
  }
  seenKnock = s.knock_key || '';
  $('status').textContent = s.phase === 'lobby' ? 'Everyone’s welcome here.' : playing ? (s.your_turn ? 'It’s your turn.' : `${s.players.find(p=>p.turn).name}’s turn`) : s.phase === 'finished' ? 'A game well played.' : 'Let’s see those cards.';
  $('players').replaceChildren();
  s.players.forEach(p=>{const row=document.createElement('div');row.className='player'+(p.turn&&playing?' current':'');const n=document.createElement('strong');n.textContent=p.name+(p.you?' (you)':'');const meta=document.createElement('small');meta.textContent=p.lives ? '♥'.repeat(p.lives)+(p.knocked?' · Knocked':p.host?' · Host':'') : 'Watching';row.append(n,meta);$('players').append(row);});
  $('piles').hidden = !playing; card($('pile'),s.top);
  $('deck').disabled = $('pile').disabled = !s.your_turn || s.drawn;
  $('deck').title = `${s.deck_count} cards remaining`;
  $('pile').disabled ||= !s.top;
  $('deal').hidden = playing || !me.host;
  $('deal').disabled = s.players.length < 2;
  $('deal').textContent = s.phase === 'lobby' ? 'Deal the first round →' : s.phase === 'finished' ? 'Play again →' : 'Deal the next round →';
  $('deal').onclick = ()=>act(s.phase === 'lobby' ? 'start' : s.phase === 'finished' ? 'rematch' : 'next');
  $('score').textContent = me.hand.length ? `Best suit · ${s.score} points` : 'Waiting for the deal';
  $('hint').textContent = playing ? !me.lives ? 'You’re out of lives. Stay and watch the game.' : s.your_turn ? s.drawn ? 'Choose a card below to discard.' : 'Draw a card, or knock if you’re ready.' : 'Make yourself comfortable. Your turn is coming.' : s.phase === 'lobby' ? 'Share your invite link. The host can deal when at least two players join.' : 'The host can deal when everyone is ready.';
  $('hand').replaceChildren(); me.hand.forEach((c,i)=>{const el=document.createElement('button');el.className='card';card(el,c);el.disabled=!(playing&&s.your_turn&&s.drawn);el.onclick=()=>act('discard',i);$('hand').append(el);});
  $('knock').hidden = !(playing && s.your_turn && !s.drawn && !s.knocked);
  $('results').replaceChildren();
  s.result.forEach(r=>{const row=document.createElement('div');row.className='result-row';const title=document.createElement('strong');title.textContent=`${r.name} · ${r.score} points${r.lost?' · −1 life':''}`;const cards=document.createElement('span');cards.textContent=r.hand.map(c=>c.slice(0,-1)+symbols[c.slice(-1)]).join('  ');row.append(title,cards);$('results').append(row);});
}
function renderMessages(messages) {
  const log = $('chat-messages');
  const fresh = messages.filter(m => m.id > lastMessageId);
  if (!fresh.length) return;
  const nearBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 60;
  if (!lastMessageId) log.replaceChildren();
  fresh.forEach(m => {
    const row = document.createElement('div');
    row.className = 'chat-message' + (m.kind === 'event' ? ' game-event' : '');
    const author = document.createElement('strong');
    author.textContent = m.kind === 'event' ? 'Server · Game event' : m.author + ' · Player';
    const message = document.createElement('span'); message.textContent = m.text;
    row.append(author, message); log.append(row);
    lastMessageId = m.id;
  });
  while (log.children.length > 80) log.firstElementChild.remove();
  if (nearBottom) log.scrollTop = log.scrollHeight;
}
$('chat-form').onsubmit = async e => {
  e.preventDefault();
  if (sendingChat) return;
  const input = $('chat-input'), text = input.value.trim();
  if (!text) return;
  sendingChat = true; $('chat-send').disabled = true; $('chat-error').textContent = '';
  try {
    const response = await fetch('chat/', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value}, body:JSON.stringify({text})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not send your message.');
    input.value = ''; await refresh();
  } catch (error) { $('chat-error').textContent = error.message; }
  finally { sendingChat = false; $('chat-send').disabled = false; }
};
$('deck').onclick=()=>act('deck'); $('pile').onclick=()=>act('pile'); $('knock').onclick=()=>act('knock');
$('copy').onclick=async()=>{try{await navigator.clipboard.writeText(location.href);$('copy').textContent='Invite link copied ✓';}catch{ $('error').textContent=`Copy this link: ${location.href}`; }};
async function poll(){await refresh();setTimeout(poll,1500);} poll();
