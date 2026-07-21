// ============================================================
// Rendu du plateau sur canvas, avec interpolation des creeps
// entre deux snapshots serveur (10/s) pour un rendu fluide.
// ============================================================
import { GRID, WAYPOINTS, computePathCells, TOWERS, LVL_RANGE } from '/shared/data.js';

const CELL = GRID.cell;
const PATH_CELLS = computePathCells();
const PTS = WAYPOINTS.map(([c, r]) => ({ x: c * CELL + CELL / 2, y: r * CELL + CELL / 2 }));

let canvas, ctx;
let shotFx = [];   // {fx,fy,tx,ty,color,until}

export function initRender(canvasEl) {
  canvas = canvasEl;
  ctx = canvas.getContext('2d');
}

export function addShots(shots) {
  const until = performance.now() + 130;
  for (const s of shots) shotFx.push({ ...s, until });
}

/**
 * @param prev  snapshot précédent du joueur affiché (ou null)
 * @param cur   snapshot courant du joueur affiché
 * @param alpha interpolation [0..1] entre prev et cur
 * @param ui    { hoverCell, placingType, selectedTowerId, comboPartners }
 */
export function draw(prev, cur, alpha, ui) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawGrid();
  if (!cur) return;

  // portée de la tour sélectionnée / en placement
  if (ui.selectedTowerId) {
    const t = cur.towers.find(t => t.id === ui.selectedTowerId);
    if (t) drawRange(t.x, t.y, TOWERS[t.type].range + LVL_RANGE[t.lvl - 1], TOWERS[t.type].color);
  }
  if (ui.placingType && ui.hoverCell) {
    const def = TOWERS[ui.placingType];
    const { x, y } = ui.hoverCell;
    const blocked = PATH_CELLS.has(`${x},${y}`) || cur.towers.some(t => t.x === x && t.y === y);
    drawRange(x, y, def.range, blocked ? '#e25f5f' : def.color);
    ctx.globalAlpha = 0.6;
    drawTowerShape(x, y, ui.placingType, 1);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = blocked ? '#e25f5f' : '#6fce7e';
    ctx.lineWidth = 2;
    ctx.strokeRect(x * CELL + 2, y * CELL + 2, CELL - 4, CELL - 4);
  }

  // tours
  const partnerIds = new Set(ui.comboPartners || []);
  for (const t of cur.towers) {
    drawTowerShape(t.x, t.y, t.type, t.lvl);
    if (t.id === ui.selectedTowerId) {
      ctx.strokeStyle = '#f0c860';
      ctx.lineWidth = 2;
      ctx.strokeRect(t.x * CELL + 2, t.y * CELL + 2, CELL - 4, CELL - 4);
    } else if (partnerIds.has(t.id)) {
      ctx.strokeStyle = '#6fce7e';
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 3]);
      ctx.strokeRect(t.x * CELL + 2, t.y * CELL + 2, CELL - 4, CELL - 4);
      ctx.setLineDash([]);
    }
  }

  // creeps (interpolés)
  const prevById = new Map((prev?.creeps || []).map(c => [c.id, c]));
  for (const c of cur.creeps) {
    const p = prevById.get(c.id);
    const x = p ? p.x + (c.x - p.x) * alpha : c.x;
    const y = p ? p.y + (c.y - p.y) * alpha : c.y;
    drawCreep(x, y, c);
  }

  // tirs
  const now = performance.now();
  shotFx = shotFx.filter(s => s.until > now);
  for (const s of shotFx) {
    ctx.globalAlpha = Math.max(0.15, (s.until - now) / 130);
    ctx.strokeStyle = s.color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(s.fx, s.fy);
    ctx.lineTo(s.tx, s.ty);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
}

function drawGrid() {
  for (let r = 0; r < GRID.rows; r++) {
    for (let c = 0; c < GRID.cols; c++) {
      const onPath = PATH_CELLS.has(`${c},${r}`);
      ctx.fillStyle = onPath ? '#2b3042' : ((c + r) % 2 ? '#171a26' : '#191d2b');
      ctx.fillRect(c * CELL, r * CELL, CELL, CELL);
    }
  }
  // flèches de direction du chemin
  ctx.strokeStyle = 'rgba(255,255,255,0.10)';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(PTS[0].x, PTS[0].y);
  for (let i = 1; i < PTS.length; i++) ctx.lineTo(PTS[i].x, PTS[i].y);
  ctx.stroke();
  // entrée / sortie
  ctx.fillStyle = 'rgba(111, 206, 126, 0.5)';
  ctx.fillRect(0, WAYPOINTS[0][1] * CELL, 6, CELL);
  ctx.fillStyle = 'rgba(226, 95, 95, 0.6)';
  ctx.fillRect(0, WAYPOINTS[WAYPOINTS.length - 1][1] * CELL, 6, CELL);
}

function drawRange(cx, cy, range, color) {
  ctx.beginPath();
  ctx.arc(cx * CELL + CELL / 2, cy * CELL + CELL / 2, range, 0, Math.PI * 2);
  ctx.fillStyle = color + '18';
  ctx.fill();
  ctx.strokeStyle = color + '55';
  ctx.lineWidth = 1;
  ctx.stroke();
}

function drawTowerShape(cx, cy, type, lvl) {
  const def = TOWERS[type];
  const x = cx * CELL + CELL / 2;
  const y = cy * CELL + CELL / 2;
  const r = CELL * 0.34;
  ctx.fillStyle = def.color;
  ctx.strokeStyle = 'rgba(0,0,0,0.45)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  if (def.tier === 'combo') {
    // losange étoilé pour les tours combinées
    ctx.moveTo(x, y - r * 1.15);
    ctx.lineTo(x + r * 1.15, y);
    ctx.lineTo(x, y + r * 1.15);
    ctx.lineTo(x - r * 1.15, y);
    ctx.closePath();
  } else {
    ctx.arc(x, y, r, 0, Math.PI * 2);
  }
  ctx.fill();
  ctx.stroke();
  // pips de niveau
  if (def.tier !== 'combo' && lvl > 1) {
    ctx.fillStyle = '#fff';
    for (let i = 0; i < lvl; i++) {
      ctx.beginPath();
      ctx.arc(x - (lvl - 1) * 4 + i * 8, y + r + 4, 2.4, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

function drawCreep(x, y, c) {
  const r = c.boss ? 13 : 7;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = c.color || '#c8c8c8';
  ctx.fill();
  if (c.kind === 'sent') {
    ctx.strokeStyle = '#f0c860';
    ctx.lineWidth = 2;
    ctx.stroke();
  }
  if (c.burn) {
    ctx.strokeStyle = '#ff7a30';
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(x, y, r + 2.5, 0, Math.PI * 2); ctx.stroke();
  }
  if (c.slow) {
    ctx.strokeStyle = '#5fc7e2';
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(x, y, r + 4.5, 0, Math.PI * 2); ctx.stroke();
  }
  if (c.stun) {
    ctx.fillStyle = '#ffe060';
    ctx.font = '10px sans-serif';
    ctx.fillText('✦', x - 3, y - r - 4);
  }
  // barre de vie
  const w = c.boss ? 26 : 16;
  const frac = Math.max(0, Math.min(1, c.hp / c.mhp));
  ctx.fillStyle = 'rgba(0,0,0,0.6)';
  ctx.fillRect(x - w / 2, y - r - 8, w, 3);
  ctx.fillStyle = frac > 0.5 ? '#6fce7e' : frac > 0.25 ? '#f0c860' : '#e25f5f';
  ctx.fillRect(x - w / 2, y - r - 8, w * frac, 3);
}
