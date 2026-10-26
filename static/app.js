const $ = s => document.querySelector(s), app = $('#app');
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const THEME = {'Music':['🎵','#6d28d9','#db2777'],'Food & Drink':['🍲','#ea580c','#d97706'],'Culture':['🥁','#b91c1c','#f97316'],'Sports':['🏃','#0369a1','#16a34a'],
  'Nature & Safari':['🦁','#166534','#65a30d'],'Arts':['🎨','#be185d','#7c3aed'],'Business & Tech':['💡','#1e3a8a','#0891b2'],'Nightlife':['🌙','#312e81','#a21caf']};
const COUNTIES = ['Nairobi','Mombasa','Kisumu','Nakuru','Lamu','Narok','Nyeri','Kwale'];
const S = {token: localStorage.getItem('t'), user: JSON.parse(localStorage.getItem('u') || 'null'), cats: [], view: 'home',
           f: {county:'', category:'', q:'', free:'', page:1}};
const save = () => { S.token ? localStorage.setItem('t', S.token) : localStorage.removeItem('t'); localStorage.setItem('u', JSON.stringify(S.user)); };

async function api(path, o = {}) {
  const r = await fetch('/api' + path, {method: o.method || 'GET',
    headers: {'Content-Type': 'application/json', ...(S.token ? {Authorization: 'Bearer ' + S.token} : {})},
    body: o.body ? JSON.stringify(o.body) : undefined});
  const d = await r.json().catch(() => ({}));
  if (r.status === 401 && S.token) { logout(); }
  if (!r.ok) throw new Error(d.error || 'Something went wrong');
  return d;
}
const fmt = d => new Date(d + 'T00:00').toLocaleDateString('en-KE', {day:'numeric', month:'short', year:'numeric'});
const price = p => p ? 'KSh ' + p.toLocaleString() : 'Free Entry';
const th = c => THEME[c] || ['🎉','#374151','#6b7280'];
const grad = c => `linear-gradient(135deg,${th(c)[1]},${th(c)[2]})`;

/* ---------- chrome / routing ---------- */
function chrome() {
  const u = S.user, items = [['home','Events'], ['foryou','For You']];
  if (u?.role === 'attendee') items.push(['tickets','My Tickets']);
  if (u?.role === 'organizer') items.push(['mine','My Events']);
  if (u?.role === 'admin') items.push(['admin','Admin']);
  $('#nav').innerHTML = items.map(([v,l]) => `<a href="#" class="${S.view===v?'on':''}" onclick="go('${v}');return false">${l}</a>`).join('');
  $('#user').innerHTML = u ? `<span>${esc(u.name)} <small class="muted">(${u.role})</small></span><button class="btn ghost sm" onclick="logout()">Log out</button>`
                           : `<button class="btn" onclick="authModal()">Log in</button>`;
}
const VIEWS = {home, foryou, tickets, mine, admin};
async function go(v) { S.view = v; chrome(); try { await VIEWS[v](); } catch (e) { app.innerHTML = `<div class="wrap"><p class="err">${esc(e.message)}</p></div>`; } }
function logout() { S.token = null; S.user = null; save(); go('home'); }
function modal(html) { $('#sheet').innerHTML = html; $('#modal').classList.add('on'); }
function closeModal() { $('#modal').classList.remove('on'); }

/* ---------- cards ---------- */
const card = e => `<article class="card" onclick="openEvent(${e.id})"><div class="img" style="background:${grad(e.category)}">${th(e.category)[0]}</div>
  <div class="body"><span class="tag">${esc(e.category)}</span><h3>${esc(e.title)}</h3><p class="meta">📍 ${esc(e.county)} · ${fmt(e.event_date)}</p>
  <p class="price">${price(e.price)}${e.rating ? ' · ★ ' + e.rating : ''}</p>${e.reason ? `<p class="why">✨ ${esc(e.reason)}</p>` : ''}</div></article>`;
const feat = e => `<div class="fc" style="background:${grad(e.category)}" onclick="openEvent(${e.id})"><span class="em">${th(e.category)[0]}</span>
  <small>${fmt(e.event_date)} · ${esc(e.county)}</small><h3>${esc(e.title)}</h3><small>${price(e.price)} · ${e.going} going</small></div>`;

/* ---------- home: browse + search + filters ---------- */
async function home() {
  if (!S.cats.length) S.cats = await api('/categories');
  const fe = await api('/featured');
  app.innerHTML = `<section class="hero"><h1>Events in Kenya</h1><p>Festivals, safaris, concerts and things to do across all 47 counties.</p></section>
  <div class="wrap"><div class="feat">${fe.map(feat).join('')}</div><h2>Upcoming events</h2>
  <div class="chips">${['', ...COUNTIES].map(c => `<button class="chip ${S.f.county===c?'on':''}" onclick="setF('county','${c}')">${c || 'All Kenya'}</button>`).join('')}</div>
  <div class="filters"><input type="text" id="q" placeholder="Search events, venues..." value="${esc(S.f.q)}" onkeydown="if(event.key==='Enter')setF('q',this.value)">
   <select onchange="setF('category',this.value)"><option value="">All interests</option>${S.cats.map(c => `<option value="${c.id}" ${S.f.category==c.id?'selected':''}>${esc(c.name)}</option>`).join('')}</select>
   <label><input type="checkbox" ${S.f.free?'checked':''} onchange="setF('free',this.checked?'1':'')"> Free</label>
   <button class="btn g" onclick="setF('q',$('#q').value)">Search</button><button class="link" onclick="resetF()">Reset filters</button></div>
  <div id="list" style="margin-top:16px"></div></div>`;
  loadList();
}
function setF(k, v) { S.f[k] = v; if (k !== 'page') S.f.page = 1; k === 'page' ? loadList() : home(); }
function resetF() { S.f = {county:'', category:'', q:'', free:'', page:1}; home(); }
async function loadList() {
  const p = new URLSearchParams({...S.f, per: 9}); [...p].forEach(([k, v]) => { if (!v) p.delete(k); });
  const d = await api('/events?' + p);
  $('#list').innerHTML = `<p class="count">${d.total} Events Found</p><div class="grid">${d.events.map(card).join('') || '<p>No events match your filters.</p>'}</div>` +
    (d.pages > 1 ? `<div class="pager">${Array.from({length: d.pages}, (_, i) => `<button class="${d.page===i+1?'on':''}" onclick="setF('page',${i+1})">${i+1}</button>`).join('')}</div>` : '');
}

/* ---------- event detail, pay ---------- */
async function openEvent(id) {
  const e = await api('/events/' + id), [em] = th(e.category), u = S.user;
  let buy = '';
  if (!u) buy = `<button class="btn" onclick="authModal()">Log in to attend</button>`;
  else if (u.role === 'attendee') buy = e.price
    ? `<label class="f">M-Pesa phone number</label><input id="phone" value="07" maxlength="13"><p class="muted">Demo: numbers ending in 000 simulate a declined payment.</p>
       <button class="btn" onclick="pay(${e.id})">Pay ${price(e.price)} with M-Pesa</button>`
    : `<button class="btn g" onclick="pay(${e.id})">Register (free)</button>`;
  modal(`<div class="mhead" style="background:${grad(e.category)}">${em}</div><span class="tag">${esc(e.category)}</span><h2 style="margin:6px 0">${esc(e.title)}</h2>
   <p class="meta">📍 ${esc(e.venue)}, ${esc(e.county)} · 📅 ${fmt(e.event_date)} · 👤 ${esc(e.organizer)} · ${e.going} going${e.rating ? ' · ★ ' + e.rating : ''}</p>
   <p>${esc(e.description)}</p><p class="price big">${price(e.price)}</p>${buy}<p id="msg"></p>
   <h3>Reviews</h3>${e.reviews.map(r => `<p><b>${esc(r.name)}</b> ★${r.score}<br>${esc(r.comment)}</p>`).join('') || '<p class="muted">No reviews yet.</p>'}
   <p><button class="btn ghost sm" onclick="closeModal()">Close</button></p>`);
}
async function pay(id) {
  try { const r = await api('/pay', {method: 'POST', body: {event_id: id, phone: $('#phone')?.value || ''}});
    $('#msg').innerHTML = `<span class="ok">🎟️ ${esc(r.message)}</span>`; }
  catch (e) { $('#msg').innerHTML = `<span class="err">${esc(e.message)}</span>`; }
}

/* ---------- auth ---------- */
function authModal(tab = 'login') {
  const reg = tab === 'register';
  modal(`<h2>${reg ? 'Create account' : 'Log in'}</h2>
   ${reg ? `<label class="f">Full name</label><input id="n">` : ''}<label class="f">Email</label><input id="e" type="email"><label class="f">Password</label><input id="p" type="password">
   ${reg ? `<label class="f">I am an</label><select id="r"><option value="attendee">Attendee</option><option value="organizer">Event organizer</option></select>` : ''}
   <p id="msg" class="err"></p><button class="btn" onclick="${reg ? 'doReg()' : 'doLogin()'}">${reg ? 'Sign up' : 'Log in'}</button>
   <button class="link" onclick="authModal('${reg ? 'login' : 'register'}')">${reg ? 'Have an account? Log in' : 'New here? Sign up'}</button>
   ${reg ? '' : `<p class="muted">Demo: amina@demo.ke / pass123 (attendee) · organizer@demo.ke / org123 · admin@demo.ke / admin123</p>`}`);
}
async function authDone(r) { S.token = r.token; S.user = r.user; save(); closeModal(); go(S.user.role === 'organizer' ? 'mine' : S.user.role === 'admin' ? 'admin' : S.view); }
async function doLogin() { try { authDone(await api('/login', {method:'POST', body:{email:$('#e').value, password:$('#p').value}})); } catch (e) { $('#msg').textContent = e.message; } }
async function doReg() { try { authDone(await api('/register', {method:'POST', body:{name:$('#n').value, email:$('#e').value, password:$('#p').value, role:$('#r').value}})); } catch (e) { $('#msg').textContent = e.message; } }

/* ---------- For You (profile + recommender) ---------- */
async function foryou() {
  if (!S.user) { app.innerHTML = `<div class="wrap"><h2>For You</h2><p>Log in to get recommendations based on your interests, budget and location.</p><button class="btn" onclick="authModal()">Log in</button></div>`; return; }
  if (S.user.role !== 'attendee') { app.innerHTML = `<div class="wrap"><p>Recommendations are available to attendee accounts.</p></div>`; return; }
  if (!S.cats.length) S.cats = await api('/categories');
  const [me, recs] = await Promise.all([api('/me'), api('/recommend')]);
  S.user = me; save();
  app.innerHTML = `<section class="hero small"><h1>Recommended for you</h1><p>Ranked by your interests, budget, location and what similar attendees enjoyed.</p></section><div class="wrap">
  <details class="panel" ${me.interests.length ? '' : 'open'}><summary>Your preferences</summary>
   <div class="row"><div><label class="f">County</label><select id="loc">${COUNTIES.map(c => `<option ${me.location===c?'selected':''}>${c}</option>`).join('')}</select></div>
   <div><label class="f">Max budget (KSh, blank = any)</label><input id="bmax" type="number" min="0" value="${me.budget_max ?? ''}"></div></div>
   <label class="f">Interests</label>${S.cats.map(c => `<label class="chk"><input type="checkbox" class="int" value="${c.id}" ${me.interests.includes(c.id)?'checked':''}>${esc(c.name)}</label>`).join('')}
   <p><button class="btn g" onclick="saveProfile()">Save and refresh</button></p></details>
  <div class="grid">${recs.map(card).join('') || '<p>No matches yet. Set your interests and budget above.</p>'}</div></div>`;
}
async function saveProfile() {
  await api('/profile', {method:'PUT', body:{location:$('#loc').value, budget_min:0, budget_max:$('#bmax').value, interests:[...document.querySelectorAll('.int:checked')].map(x => x.value)}});
  foryou();
}

/* ---------- Attendee: tickets + ratings ---------- */
async function tickets() {
  const t = await api('/me/tickets');
  app.innerHTML = `<section class="hero small"><h1>My tickets</h1></section><div class="wrap"><table><tr><th>Event</th><th>Date</th><th>Paid</th><th>Receipt</th><th>Rating</th></tr>
  ${t.map(x => `<tr><td><b>${esc(x.title)}</b><br><span class="muted">${esc(x.venue)}, ${esc(x.county)}</span></td><td>${fmt(x.event_date)}</td><td>${price(x.price)}</td><td>${esc(x.receipt || '-')}</td>
   <td>${x.my_score ? '★ ' + x.my_score : x.can_rate ? `<button class="btn sm" onclick="rateModal(${x.id})">Rate</button>` : '<span class="muted">After event</span>'}</td></tr>`).join('') || '<tr><td colspan="5">No tickets yet.</td></tr>'}</table></div>`;
}
function rateModal(id) {
  modal(`<h2>Rate this event</h2><label class="f">Score</label><select id="sc">${[5,4,3,2,1].map(n => `<option value="${n}">${'★'.repeat(n)}</option>`).join('')}</select>
   <label class="f">Comment</label><textarea id="cm" rows="3"></textarea><p id="msg" class="err"></p><button class="btn" onclick="rate(${id})">Submit</button>`);
}
async function rate(id) { try { await api('/rate', {method:'POST', body:{event_id:id, score:$('#sc').value, comment:$('#cm').value}}); closeModal(); tickets(); } catch (e) { $('#msg').textContent = e.message; } }

/* ---------- Organizer ---------- */
async function mine() {
  if (!S.cats.length) S.cats = await api('/categories');
  const ev = await api('/my/events');
  app.innerHTML = `<section class="hero small"><h1>My events</h1><p>New listings are reviewed by an admin before they go live.</p></section><div class="wrap">
  <details class="panel"><summary>+ Create an event</summary><div class="row">
   <div><label class="f">Title</label><input id="t"></div><div><label class="f">Category</label><select id="c">${S.cats.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('')}</select></div>
   <div><label class="f">Venue</label><input id="v"></div><div><label class="f">County</label><select id="co">${COUNTIES.map(c => `<option>${c}</option>`).join('')}</select></div>
   <div><label class="f">Date</label><input id="d" type="date"></div><div><label class="f">Price (KSh, 0 = free)</label><input id="pr" type="number" min="0" value="0"></div></div>
   <label class="f">Description</label><textarea id="ds" rows="3" style="width:100%"></textarea><p id="msg" class="err"></p><button class="btn g" onclick="createEvent()">Submit for review</button></details>
  <table><tr><th>Event</th><th>Date</th><th>Price</th><th>Status</th><th>Going</th></tr>${ev.map(e => `<tr><td>${esc(e.title)}</td><td>${fmt(e.event_date)}</td><td>${price(e.price)}</td><td><span class="st ${e.status}">${e.status}</span></td><td>${e.going}</td></tr>`).join('')}</table></div>`;
}
async function createEvent() {
  try { await api('/events', {method:'POST', body:{title:$('#t').value, category_id:$('#c').value, venue:$('#v').value, county:$('#co').value, event_date:$('#d').value, price:$('#pr').value, description:$('#ds').value}}); mine(); }
  catch (e) { $('#msg').textContent = e.message; }
}

/* ---------- Admin: moderation + users ---------- */
async function admin() {
  const [pend, users] = await Promise.all([api('/admin/events?status=pending'), api('/admin/users')]);
  app.innerHTML = `<section class="hero small"><h1>Admin dashboard</h1></section><div class="wrap"><h2>Listings awaiting review (${pend.length})</h2>
  <table>${pend.map(e => `<tr><td><b>${esc(e.title)}</b><br><span class="muted">${esc(e.organizer)} · ${esc(e.county)} · ${fmt(e.event_date)} · ${price(e.price)}</span></td>
   <td><button class="btn g sm" onclick="mod(${e.id},'approved')">Approve</button> <button class="btn ghost sm" onclick="mod(${e.id},'rejected')">Reject</button></td></tr>`).join('') || '<tr><td>Nothing to review 🎉</td></tr>'}</table>
  <h2>Users</h2><table><tr><th>Name</th><th>Email</th><th>Role</th></tr>${users.map(u => `<tr><td>${esc(u.name)}</td><td>${esc(u.email)}</td><td>
   <select onchange="setRole(${u.id},this.value)" ${u.id===S.user.id?'disabled':''}>${['attendee','organizer','admin'].map(r => `<option ${u.role===r?'selected':''}>${r}</option>`).join('')}</select></td></tr>`).join('')}</table></div>`;
}
async function mod(id, status) { await api('/admin/events/' + id, {method:'PUT', body:{status}}); admin(); }
async function setRole(id, role) { await api('/admin/users/' + id, {method:'PUT', body:{role}}); }

chrome(); go('home');
