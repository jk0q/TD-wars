// ============================================================
// Client TD Wars — réseau, lobby et interface de jeu.
// ============================================================
import {
  GRID, TOWERS, UNITS, RESEARCH, RECIPES, findRecipe,
  ATK_NAMES, ARMOR_NAMES, LVL_DMG, LVL_COST, LVL_CD, LVL_RANGE, SELL_RATIO,
} from '/shared/data.js';
import { initRender, draw, addShots } from './render.js';

const socket = io();
const $ = (id) => document.getElementById(id);

// ---------- État client ----------
let myId = null;
let room = null;
let prevSnap = null, curSnap = null;
let prevTime = 0, curTime = 0;
let viewedId = null;          // joueur dont on affiche le plateau
let placingType = null;       // type de tour en cours de placement
let selectedTowerId = null;
let activeTab = 'build';
let hoverCell = null;
let lastResearchKey = '';     // pour rafraîchir les onglets sans tout reconstruire

const canvas = $('board');
initRender(canvas);

// ============================================================
// LOBBY
// ============================================================
$('name-input').value = localStorage.getItem('tdw-name') || '';

function myName() {
  const n = $('name-input').value.trim() || 'Joueur';
  localStorage.setItem('tdw-name', n);
  return n;
}

$('create-btn').onclick = () => {
  socket.emit('createRoom', { name: myName() }, (res) => {
    if (res?.ok) showRoom(res.room);
  });
};
$('join-btn').onclick = () => {
  socket.emit('joinRoom', { name: myName(), code: $('code-input').value }, (res) => {
    if (!res?.ok) return toast('error', res?.error || 'Erreur');
    showRoom(res.room);
  });
};
$('code-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('join-btn').click(); });
$('leave-btn').onclick = () => { socket.emit('leaveRoom'); showHome(); };
$('start-btn').onclick = () => socket.emit('startGame');
$('go-back').onclick = () => location.reload();

socket.on('connect', () => { myId = socket.id; });
socket.on('roomUpdate', (r) => { room = r; renderRoom(); });
socket.on('disconnect', () => toast('error', 'Connexion perdue…'));

function showHome() {
  room = null;
  $('lobby-home').classList.remove('hidden');
  $('lobby-room').classList.add('hidden');
}

function showRoom(r) {
  room = r;
  $('lobby-home').classList.add('hidden');
  $('lobby-room').classList.remove('hidden');
  renderRoom();
}

function renderRoom() {
  if (!room) return;
  $('room-code').textContent = room.code;
  const ul = $('room-players');
  ul.innerHTML = '';
  for (const p of room.players) {
    const li = document.createElement('li');
    li.textContent = p.name + (p.id === myId ? ' (vous)' : '');
    if (p.id === room.hostId) li.classList.add('host');
    ul.appendChild(li);
  }
  const isHost = room.hostId === myId;
  $('start-btn').classList.toggle('hidden', !isHost);
  $('wait-host').classList.toggle('hidden', isHost);
}

// ============================================================
// DÉMARRAGE / FIN DE PARTIE
// ============================================================
socket.on('gameStarted', () => {
  $('lobby').classList.add('hidden');
  $('game').classList.remove('hidden');
  viewedId = myId;
  setTab('build');
  requestAnimationFrame(frame);
});

socket.on('gameOver', ({ winnerName, wave }) => {
  const overlay = $('gameover');
  overlay.classList.remove('hidden');
  if (winnerName === null) {
    $('go-title').textContent = '💀 Défaite…';
    $('go-detail').textContent = `Vous avez tenu jusqu'à la vague ${wave}.`;
  } else if (me()?.alive && winnerName === me()?.name) {
    $('go-title').textContent = '🏆 Victoire !';
    $('go-detail').textContent = `Vous remportez la partie à la vague ${wave} !`;
  } else {
    $('go-title').textContent = 'Partie terminée';
    $('go-detail').textContent = `${winnerName} remporte la partie (vague ${wave}).`;
  }
});

socket.on('wave', ({ num, name }) => {
  const b = $('wave-banner');
  b.textContent = `🌊 Vague ${num} — ${name}`;
  b.classList.add('show');
  setTimeout(() => b.classList.remove('show'), 2500);
});

socket.on('toast', ({ type, msg }) => toast(type, msg));

// ============================================================
// SNAPSHOTS
// ============================================================
socket.on('state', (snap) => {
  prevSnap = curSnap; prevTime = curTime;
  curSnap = snap; curTime = performance.now();
  const viewed = viewedPlayer();
  if (viewed) addShots(viewed.shots || []);
  updateHud();
});

function me() { return curSnap?.players.find(p => p.id === myId); }
function viewedPlayer() { return curSnap?.players.find(p => p.id === viewedId) || me(); }
function prevViewedPlayer() { return prevSnap?.players.find(p => p.id === viewedId); }

// ============================================================
// BOUCLE DE RENDU
// ============================================================
function frame() {
  const dt = curTime - prevTime;
  const alpha = (prevSnap && dt > 0) ? Math.min(1, (performance.now() - curTime) / dt) : 1;
  draw(prevViewedPlayer(), viewedPlayer(), alpha, {
    hoverCell, placingType,
    selectedTowerId: viewedId === myId ? selectedTowerId : null,
    comboPartners: viewedId === myId ? comboPartnerIds() : [],
  });
  requestAnimationFrame(frame);
}

// ============================================================
// HUD (top bar, ressources, onglets)
// ============================================================
function updateHud() {
  const m = me();
  if (!m) return;
  $('res-gold').textContent = m.gold;
  $('res-income').textContent = m.income;
  $('res-lives').textContent = m.lives;
  $('wave-num').textContent = curSnap.wave.num;
  $('wave-timer').textContent = Math.ceil(curSnap.wave.nextIn);
  $('income-timer').textContent = Math.ceil(curSnap.incomeIn);

  // barre des joueurs
  const bar = $('topbar');
  bar.innerHTML = '';
  for (const p of curSnap.players) {
    const chip = document.createElement('div');
    chip.className = 'pchip';
    if (p.id === myId) chip.classList.add('me');
    if (p.id === viewedId) chip.classList.add('viewing');
    if (!p.alive) chip.classList.add('dead');
    chip.innerHTML = `<span>${escapeHtml(p.name)}</span>` +
      `<span>❤️${p.lives}</span><span>📈<b>${p.income}</b></span><span>☠️${p.kills}</span>`;
    chip.onclick = () => { viewedId = p.id; updateViewBanner(); };
    bar.appendChild(chip);
  }
  updateViewBanner();

  // rafraîchit l'onglet si les recherches/l'or ont changé le déblocage
  const key = JSON.stringify(m.research) + '|' + (m.gold > 0);
  if (key !== lastResearchKey) { lastResearchKey = key; renderTab(); }
  refreshCardAffordability();
  renderSelection();
}

function updateViewBanner() {
  const banner = $('view-banner');
  if (viewedId && viewedId !== myId) {
    const p = curSnap?.players.find(p => p.id === viewedId);
    banner.textContent = `👁️ Plateau de ${p ? p.name : '?'} — cliquer pour revenir`;
    banner.classList.remove('hidden');
    banner.onclick = () => { viewedId = myId; updateViewBanner(); };
  } else {
    banner.classList.add('hidden');
  }
}

// ============================================================
// ONGLETS
// ============================================================
for (const btn of document.querySelectorAll('.tab')) {
  btn.onclick = () => setTab(btn.dataset.tab);
}

function setTab(tab) {
  activeTab = tab;
  for (const btn of document.querySelectorAll('.tab')) {
    btn.classList.toggle('active', btn.dataset.tab === tab);
  }
  renderTab();
}

function renderTab() {
  const c = $('tab-content');
  c.innerHTML = '';
  if (activeTab === 'build') renderBuildTab(c);
  else if (activeTab === 'research') renderResearchTab(c);
  else renderSendTab(c);
}

function towerUnlocked(m, def) {
  return !def.req || (m && m.research[def.req.branch] >= def.req.lvl);
}

function renderBuildTab(c) {
  const m = me();
  for (const [type, def] of Object.entries(TOWERS)) {
    if (def.tier === 'combo') continue;
    const unlocked = towerUnlocked(m, def);
    const card = document.createElement('div');
    card.className = 'card' + (unlocked ? '' : ' locked') + (placingType === type ? ' selected' : '');
    card.dataset.cost = def.cost;
    const reqTxt = def.req ? ` — requiert ${RESEARCH[def.req.branch].name} ${def.req.lvl}` : '';
    card.innerHTML =
      `<div class="swatch" style="background:${def.color}"></div>` +
      `<div class="info"><div class="cname">${def.name} <small style="color:var(--muted)">(${ATK_NAMES[def.atk]})</small></div>` +
      `<div class="cdesc">${def.desc}${unlocked ? '' : reqTxt}</div></div>` +
      `<div class="cost">💰${def.cost}</div>`;
    card.onclick = () => {
      if (!unlocked) return toast('error', `Requiert la recherche ${RESEARCH[def.req.branch].name} niv. ${def.req.lvl}`);
      selectedTowerId = null;
      placingType = placingType === type ? null : type;
      canvas.classList.toggle('placing', !!placingType);
      renderTab();
    };
    c.appendChild(card);
  }
  const hint = document.createElement('p');
  hint.className = 'hint';
  hint.textContent = 'Cliquez une tour puis une case libre. Échap ou clic droit pour annuler. Cliquez une tour posée pour l\'améliorer, la vendre ou la combiner.';
  c.appendChild(hint);
}

function renderResearchTab(c) {
  const m = me();
  for (const [branch, def] of Object.entries(RESEARCH)) {
    const lvl = m ? m.research[branch] : 0;
    const div = document.createElement('div');
    div.className = 'branch';
    const pips = '●'.repeat(lvl) + '○'.repeat(3 - lvl);
    const nextDesc = lvl < 3 ? def.unlocks[lvl] : 'Recherche complète !';
    div.innerHTML =
      `<div class="bhead"><span class="bname">${def.icon} ${def.name}</span>` +
      `<span class="pips">${pips}</span></div>` +
      `<div class="bdesc">${lvl < 3 ? 'Prochain niveau : ' : ''}${nextDesc}</div>`;
    const btn = document.createElement('button');
    btn.className = 'btn';
    if (lvl < 3) {
      btn.textContent = `Rechercher niv. ${lvl + 1} — 💰${def.costs[lvl]}`;
      btn.dataset.cost = def.costs[lvl];
      btn.onclick = () => socket.emit('research', { branch });
    } else {
      btn.textContent = 'Terminé';
      btn.disabled = true;
    }
    div.appendChild(btn);
    c.appendChild(div);
  }
}

function renderSendTab(c) {
  const info = document.createElement('p');
  info.className = 'hint';
  info.textContent = 'Envoyer des unités chez TOUS vos adversaires augmente votre income (or reçu périodiquement). En solo, elles arrivent chez vous (entraînement).';
  c.appendChild(info);
  for (const [id, def] of Object.entries(UNITS)) {
    const card = document.createElement('div');
    card.className = 'card';
    card.dataset.cost = def.cost;
    card.innerHTML =
      `<div class="swatch" style="background:${def.color};border-radius:50%"></div>` +
      `<div class="info"><div class="cname">${def.name}</div>` +
      `<div class="cdesc">PV ${def.hp} · ${ARMOR_NAMES[def.armor]} · +${def.income} income</div></div>` +
      `<div class="cost">💰${def.cost}</div>`;
    const x5 = document.createElement('button');
    x5.className = 'mini-btn';
    x5.textContent = '×5';
    x5.dataset.cost = def.cost * 5;
    x5.onclick = (e) => { e.stopPropagation(); socket.emit('sendUnit', { unit: id, count: 5 }); };
    card.appendChild(x5);
    card.onclick = () => socket.emit('sendUnit', { unit: id, count: 1 });
    c.appendChild(card);
  }
}

function refreshCardAffordability() {
  const gold = me()?.gold ?? 0;
  for (const el of $('tab-content').querySelectorAll('[data-cost]')) {
    const short = Number(el.dataset.cost) > gold;
    el.style.opacity = (short && !el.classList.contains('locked')) ? 0.55 : '';
  }
}

// ============================================================
// SÉLECTION D'UNE TOUR (améliorer / vendre / combiner)
// ============================================================
function comboPartnerIds() {
  const m = me();
  if (!m || !selectedTowerId) return [];
  const t = m.towers.find(t => t.id === selectedTowerId);
  if (!t) return [];
  const tMax = TOWERS[t.type].tier === 'combo' || t.lvl >= 3;
  if (!tMax || m.research.evolution < 3) return [];
  return m.towers.filter(o =>
    o.id !== t.id &&
    Math.abs(o.x - t.x) <= 1 && Math.abs(o.y - t.y) <= 1 &&
    (TOWERS[o.type].tier === 'combo' || o.lvl >= 3) &&
    findRecipe(t.type, o.type)
  ).map(o => o.id);
}

function renderSelection() {
  const box = $('selection');
  const m = me();
  const t = m?.towers.find(t => t.id === selectedTowerId);
  if (!t) { box.classList.add('hidden'); return; }
  box.classList.remove('hidden');
  const def = TOWERS[t.type];
  const i = t.lvl - 1;
  const dmg = Math.round(def.dmg * LVL_DMG[i]);
  const cd = (def.cd * LVL_CD[i]).toFixed(2);
  const range = def.range + LVL_RANGE[i];
  const lvlTxt = def.tier === 'combo' ? 'MAX (combinée)' : `${t.lvl}/3`;

  let html = `<h3><span style="color:${def.color}">■</span> ${def.name} — niv. ${lvlTxt}</h3>` +
    `<div class="stats">Dégâts <b>${dmg}</b> (${ATK_NAMES[def.atk]}) · Cadence <b>${cd}s</b> · Portée <b>${range}</b>` +
    (def.splash ? ` · Zone <b>${def.splash}</b>` : '') +
    (def.chain ? ` · Chaîne <b>${def.chain}</b>` : '') +
    (def.slowPct ? ` · Ralenti <b>${Math.round(def.slowPct * 100)}%</b>` : '') +
    (def.burnDps ? ` · Brûlure <b>${def.burnDps}/s</b>` : '') +
    (def.stunChance ? ` · Étourdit <b>${Math.round(def.stunChance * 100)}%</b>` : '') +
    `<br>${def.desc}</div>`;
  box.innerHTML = html;

  const row = document.createElement('div');
  row.className = 'row';

  if (def.tier !== 'combo' && t.lvl < 3) {
    const cost = Math.round(def.cost * LVL_COST[t.lvl]);
    const up = document.createElement('button');
    up.className = 'btn primary';
    const evoNeeded = t.lvl; // niv2 -> évo1, niv3 -> évo2
    const evoOk = m.research.evolution >= evoNeeded;
    up.textContent = `⬆️ Niv. ${t.lvl + 1} — 💰${cost}`;
    if (!evoOk) { up.disabled = true; up.title = `Requiert Évolution niv. ${evoNeeded}`; }
    up.onclick = () => socket.emit('upgrade', { towerId: t.id });
    row.appendChild(up);
    if (!evoOk) {
      const note = document.createElement('span');
      note.className = 'hint';
      note.textContent = `🧬 Évolution niv. ${evoNeeded} requise`;
      row.appendChild(note);
    }
  }

  // combinaisons possibles
  for (const pid of comboPartnerIds()) {
    const partner = m.towers.find(o => o.id === pid);
    const recipe = findRecipe(t.type, partner.type);
    const btn = document.createElement('button');
    btn.className = 'btn';
    btn.style.borderColor = 'var(--ok)';
    btn.textContent = `⚡ ${TOWERS[recipe.result].name} (avec ${TOWERS[partner.type].name}) — 💰${recipe.cost}`;
    btn.onclick = () => socket.emit('combine', { towerId: t.id, partnerId: pid });
    row.appendChild(btn);
  }
  if (m.research.evolution < 3) {
    const maxed = TOWERS[t.type].tier === 'combo' || t.lvl >= 3;
    if (maxed && RECIPES.some(r => r.a === t.type || r.b === t.type)) {
      const note = document.createElement('span');
      note.className = 'hint';
      note.textContent = '🧬 Évolution niv. 3 débloque les combinaisons';
      row.appendChild(note);
    }
  }

  const sellBtn = document.createElement('button');
  sellBtn.className = 'btn danger';
  sellBtn.textContent = `Vendre (${Math.round(SELL_RATIO * 100)}%)`;
  sellBtn.onclick = () => { socket.emit('sell', { towerId: t.id }); selectedTowerId = null; };
  row.appendChild(sellBtn);

  const close = document.createElement('button');
  close.className = 'btn';
  close.textContent = '✕';
  close.onclick = () => { selectedTowerId = null; renderSelection(); };
  row.appendChild(close);

  box.appendChild(row);
}

// ============================================================
// INTERACTIONS CANVAS
// ============================================================
function cellFromEvent(e) {
  const rect = canvas.getBoundingClientRect();
  const x = Math.floor((e.clientX - rect.left) / rect.width * GRID.cols);
  const y = Math.floor((e.clientY - rect.top) / rect.height * GRID.rows);
  if (x < 0 || y < 0 || x >= GRID.cols || y >= GRID.rows) return null;
  return { x, y };
}

canvas.addEventListener('mousemove', (e) => { hoverCell = cellFromEvent(e); });
canvas.addEventListener('mouseleave', () => { hoverCell = null; });

canvas.addEventListener('click', (e) => {
  if (viewedId !== myId) return; // spectateur : pas d'interaction
  const cell = cellFromEvent(e);
  if (!cell) return;
  if (placingType) {
    socket.emit('build', { x: cell.x, y: cell.y, type: placingType });
    if (!e.shiftKey) {
      placingType = null;
      canvas.classList.remove('placing');
      renderTab();
    }
    return;
  }
  const m = me();
  const t = m?.towers.find(t => t.x === cell.x && t.y === cell.y);
  selectedTowerId = t ? t.id : null;
  renderSelection();
});

canvas.addEventListener('contextmenu', (e) => {
  e.preventDefault();
  placingType = null;
  selectedTowerId = null;
  canvas.classList.remove('placing');
  renderTab();
  renderSelection();
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    placingType = null;
    selectedTowerId = null;
    canvas.classList.remove('placing');
    renderTab();
    renderSelection();
  }
});

// ============================================================
// TOASTS
// ============================================================
let lastToast = { msg: '', at: 0 };
function toast(type, msg) {
  const now = Date.now();
  if (msg === lastToast.msg && now - lastToast.at < 1000) return;
  lastToast = { msg, at: now };
  const el = document.createElement('div');
  el.className = `toast ${type || 'info'}`;
  el.textContent = msg;
  $('toasts').appendChild(el);
  setTimeout(() => el.remove(), 2600);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}
