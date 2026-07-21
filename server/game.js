// ============================================================
// Simulation autoritaire d'une partie de TD Wars.
// ============================================================
import {
  GRID, WAYPOINTS, computePathCells,
  START_LIVES, START_GOLD, START_INCOME,
  INCOME_INTERVAL, WAVE_INTERVAL, FIRST_WAVE_DELAY, SELL_RATIO,
  ATK_VS_ARMOR, TOWERS, UNITS, WAVES, RESEARCH, RECIPES, findRecipe,
  LVL_DMG, LVL_COST, LVL_CD, LVL_RANGE,
  ENDLESS_SCALE, SEND_HP_SCALE_PER_WAVE,
} from '../shared/data.js';

const TICK = 0.05;          // 20 ticks/s
const BROADCAST_MS = 100;   // 10 snapshots/s
const CELL = GRID.cell;

// Chemin en pixels
const PTS = WAYPOINTS.map(([c, r]) => ({ x: c * CELL + CELL / 2, y: r * CELL + CELL / 2 }));
const SEG_LEN = [];
let PATH_LEN = 0;
for (let i = 0; i < PTS.length - 1; i++) {
  const l = Math.hypot(PTS[i + 1].x - PTS[i].x, PTS[i + 1].y - PTS[i].y);
  SEG_LEN.push(l);
  PATH_LEN += l;
}
const PATH_CELLS = computePathCells();

function posAt(dist) {
  let d = Math.max(0, dist);
  for (let i = 0; i < SEG_LEN.length; i++) {
    if (d <= SEG_LEN[i]) {
      const t = SEG_LEN[i] === 0 ? 0 : d / SEG_LEN[i];
      return {
        x: PTS[i].x + (PTS[i + 1].x - PTS[i].x) * t,
        y: PTS[i].y + (PTS[i + 1].y - PTS[i].y) * t,
      };
    }
    d -= SEG_LEN[i];
  }
  return { ...PTS[PTS.length - 1] };
}

function towerStats(type, lvl) {
  const base = TOWERS[type];
  const i = lvl - 1;
  return {
    dmg: Math.round(base.dmg * LVL_DMG[i]),
    cd: base.cd * LVL_CD[i],
    range: base.range + LVL_RANGE[i],
  };
}

function isMaxed(tower) {
  return TOWERS[tower.type].tier === 'combo' || tower.lvl >= 3;
}

let nextId = 1;
const uid = () => nextId++;

export class Game {
  constructor(io, roomCode, players) {
    this.io = io;
    this.roomCode = roomCode;
    this.time = 0;
    this.waveNum = 0;
    this.nextWaveAt = FIRST_WAVE_DELAY;
    this.nextIncomeAt = INCOME_INTERVAL;
    this.over = false;
    this.players = new Map();
    for (const p of players) {
      this.players.set(p.id, {
        id: p.id,
        name: p.name,
        alive: true,
        gold: START_GOLD,
        income: START_INCOME,
        lives: START_LIVES,
        research: { elementaire: 0, science: 0, evolution: 0 },
        towers: new Map(),   // id -> {id,type,x,y,lvl,cooldown,invested}
        creeps: new Map(),   // id -> creep
        spawnQueue: [],      // {at, def}
        shots: [],           // effets visuels accumulés entre deux broadcasts
        kills: 0,
        sent: 0,
      });
    }
  }

  start() {
    this.simTimer = setInterval(() => {
      try { this.tick(TICK); } catch (e) { console.error('tick error', e); }
    }, TICK * 1000);
    this.castTimer = setInterval(() => this.broadcast(), BROADCAST_MS);
  }

  stop() {
    clearInterval(this.simTimer);
    clearInterval(this.castTimer);
  }

  // ---------- Boucle principale ----------
  tick(dt) {
    if (this.over) return;
    this.time += dt;

    if (this.time >= this.nextWaveAt) {
      this.spawnWave();
      this.nextWaveAt = this.time + WAVE_INTERVAL;
    }
    if (this.time >= this.nextIncomeAt) {
      for (const p of this.players.values()) if (p.alive) p.gold += p.income;
      this.nextIncomeAt = this.time + INCOME_INTERVAL;
    }

    for (const p of this.players.values()) {
      if (!p.alive) continue;
      this.processSpawns(p);
      this.moveCreeps(p, dt);
      this.fireTowers(p, dt);
    }
    this.checkEnd();
  }

  processSpawns(p) {
    while (p.spawnQueue.length && p.spawnQueue[0].at <= this.time) {
      const { def } = p.spawnQueue.shift();
      const id = uid();
      p.creeps.set(id, {
        id, ...def,
        maxHp: def.hp,
        dist: 0,
        slowUntil: 0, slowPct: 0,
        burnUntil: 0, burnDps: 0,
        stunUntil: 0,
      });
    }
    // trie parfois nécessaire si des envois s'intercalent avec la vague
    if (p.spawnQueue.length > 1 && p.spawnQueue[0].at > p.spawnQueue[p.spawnQueue.length - 1].at) {
      p.spawnQueue.sort((a, b) => a.at - b.at);
    }
  }

  moveCreeps(p, dt) {
    for (const c of [...p.creeps.values()]) {
      // brûlure
      if (c.burnUntil > this.time) {
        c.hp -= c.burnDps * dt;
        if (c.hp <= 0) { this.killCreep(p, c); continue; }
      }
      if (c.stunUntil > this.time) continue;
      let speed = c.speed;
      if (c.slowUntil > this.time) speed *= (1 - c.slowPct);
      c.dist += speed * dt;
      if (c.dist >= PATH_LEN) {
        p.creeps.delete(c.id);
        p.lives -= c.leak;
        if (p.lives <= 0) this.eliminate(p);
      }
    }
  }

  killCreep(p, c) {
    p.creeps.delete(c.id);
    p.gold += c.bounty;
    p.kills++;
  }

  fireTowers(p, dt) {
    for (const t of p.towers.values()) {
      t.cooldown -= dt;
      if (t.cooldown > 0) continue;
      const base = TOWERS[t.type];
      const stats = towerStats(t.type, t.lvl);
      const tx = t.x * CELL + CELL / 2;
      const ty = t.y * CELL + CELL / 2;
      // cible : la plus avancée à portée
      let target = null;
      for (const c of p.creeps.values()) {
        if (c.hp <= 0) continue;
        const pos = posAt(c.dist);
        if (Math.hypot(pos.x - tx, pos.y - ty) <= stats.range) {
          if (!target || c.dist > target.dist) target = c;
        }
      }
      if (!target) continue;
      t.cooldown = stats.cd;
      const tpos = posAt(target.dist);
      p.shots.push({ fx: tx, fy: ty, tx: tpos.x, ty: tpos.y, color: base.color });
      this.hitCreep(p, target, stats.dmg, base);

      // dégâts de zone
      if (base.splash) {
        for (const c of [...p.creeps.values()]) {
          if (c === target || c.hp <= 0) continue;
          const pos = posAt(c.dist);
          if (Math.hypot(pos.x - tpos.x, pos.y - tpos.y) <= base.splash) {
            this.hitCreep(p, c, stats.dmg * 0.6, base);
          }
        }
      }
      // chaîne d'éclairs
      if (base.chain) {
        let from = tpos;
        let last = target;
        let mult = 0.6;
        const hitIds = new Set([target.id]);
        for (let n = 0; n < base.chain; n++) {
          let next = null, bestD = 90;
          for (const c of p.creeps.values()) {
            if (hitIds.has(c.id) || c.hp <= 0) continue;
            const pos = posAt(c.dist);
            const d = Math.hypot(pos.x - from.x, pos.y - from.y);
            if (d < bestD) { bestD = d; next = c; }
          }
          if (!next) break;
          const npos = posAt(next.dist);
          p.shots.push({ fx: from.x, fy: from.y, tx: npos.x, ty: npos.y, color: base.color });
          this.hitCreep(p, next, stats.dmg * mult, base);
          hitIds.add(next.id);
          from = npos; last = next; mult *= 0.6;
        }
      }
    }
  }

  hitCreep(p, c, rawDmg, base) {
    if (!p.creeps.has(c.id)) return;
    const mult = ATK_VS_ARMOR[base.atk][c.armor] ?? 1;
    c.hp -= rawDmg * mult;
    if (base.slowPct && (c.slowUntil <= this.time || base.slowPct >= c.slowPct)) {
      c.slowPct = base.slowPct;
      c.slowUntil = this.time + base.slowDur;
    }
    if (base.burnDps) {
      c.burnDps = Math.max(c.burnDps, base.burnDps);
      c.burnUntil = this.time + base.burnDur;
    }
    if (base.stunChance && Math.random() < base.stunChance) {
      c.stunUntil = Math.max(c.stunUntil, this.time + base.stunDur);
    }
    if (c.hp <= 0) this.killCreep(p, c);
  }

  // ---------- Vagues ----------
  spawnWave() {
    this.waveNum++;
    let def = WAVES[Math.min(this.waveNum - 1, WAVES.length - 1)];
    let hpScale = 1;
    if (this.waveNum > WAVES.length) {
      hpScale = Math.pow(ENDLESS_SCALE, this.waveNum - WAVES.length);
    }
    for (const p of this.players.values()) {
      if (!p.alive) continue;
      for (let i = 0; i < def.count; i++) {
        p.spawnQueue.push({
          at: this.time + i * 0.55,
          def: {
            kind: 'wave', name: def.name,
            hp: Math.round(def.hp * hpScale),
            speed: def.speed, armor: def.armor,
            leak: def.leak, bounty: def.bounty,
            color: def.color, boss: def.boss,
          },
        });
      }
      p.spawnQueue.sort((a, b) => a.at - b.at);
    }
    this.io.to(this.roomCode).emit('wave', { num: this.waveNum, name: def.name });
  }

  // ---------- Actions des joueurs ----------
  err(socket, msg) { socket.emit('toast', { type: 'error', msg }); }

  canBuild(p, type) {
    const def = TOWERS[type];
    if (!def || def.tier === 'combo') return false;
    if (def.req && p.research[def.req.branch] < def.req.lvl) return false;
    return true;
  }

  build(socket, pid, { x, y, type }) {
    const p = this.players.get(pid);
    if (!p || !p.alive || this.over) return;
    const def = TOWERS[type];
    if (!this.canBuild(p, type)) return this.err(socket, 'Tour non débloquée');
    x = x | 0; y = y | 0;
    if (x < 0 || y < 0 || x >= GRID.cols || y >= GRID.rows) return;
    if (PATH_CELLS.has(`${x},${y}`)) return this.err(socket, 'Impossible de construire sur le chemin');
    for (const t of p.towers.values()) {
      if (t.x === x && t.y === y) return this.err(socket, 'Case occupée');
    }
    if (p.gold < def.cost) return this.err(socket, 'Or insuffisant');
    p.gold -= def.cost;
    const id = uid();
    p.towers.set(id, { id, type, x, y, lvl: 1, cooldown: 0, invested: def.cost });
  }

  upgrade(socket, pid, { towerId }) {
    const p = this.players.get(pid);
    if (!p || !p.alive || this.over) return;
    const t = p.towers.get(towerId);
    if (!t) return;
    if (TOWERS[t.type].tier === 'combo') return this.err(socket, 'Les tours combinées sont déjà au maximum');
    if (t.lvl >= 3) return this.err(socket, 'Niveau maximum atteint');
    const next = t.lvl + 1;
    const evoNeeded = next - 1; // niv2 -> évo 1, niv3 -> évo 2
    if (p.research.evolution < evoNeeded) {
      return this.err(socket, `Recherche Évolution niv. ${evoNeeded} requise`);
    }
    const cost = Math.round(TOWERS[t.type].cost * LVL_COST[next - 1]);
    if (p.gold < cost) return this.err(socket, 'Or insuffisant');
    p.gold -= cost;
    t.invested += cost;
    t.lvl = next;
  }

  sell(socket, pid, { towerId }) {
    const p = this.players.get(pid);
    if (!p || !p.alive || this.over) return;
    const t = p.towers.get(towerId);
    if (!t) return;
    p.gold += Math.floor(t.invested * SELL_RATIO);
    p.towers.delete(towerId);
  }

  research(socket, pid, { branch }) {
    const p = this.players.get(pid);
    if (!p || !p.alive || this.over) return;
    const r = RESEARCH[branch];
    if (!r) return;
    const cur = p.research[branch];
    if (cur >= 3) return this.err(socket, 'Recherche au maximum');
    const cost = r.costs[cur];
    if (p.gold < cost) return this.err(socket, 'Or insuffisant');
    p.gold -= cost;
    p.research[branch] = cur + 1;
  }

  combine(socket, pid, { towerId, partnerId }) {
    const p = this.players.get(pid);
    if (!p || !p.alive || this.over) return;
    if (p.research.evolution < 3) return this.err(socket, 'Recherche Évolution niv. 3 requise');
    const a = p.towers.get(towerId);
    const b = p.towers.get(partnerId);
    if (!a || !b || a === b) return;
    if (Math.abs(a.x - b.x) > 1 || Math.abs(a.y - b.y) > 1) {
      return this.err(socket, 'Les tours doivent être adjacentes');
    }
    if (!isMaxed(a) || !isMaxed(b)) return this.err(socket, 'Les deux tours doivent être au niveau maximum');
    const recipe = findRecipe(a.type, b.type);
    if (!recipe) return this.err(socket, 'Ces tours ne se combinent pas');
    if (p.gold < recipe.cost) return this.err(socket, 'Or insuffisant');
    p.gold -= recipe.cost;
    const invested = a.invested + b.invested + recipe.cost;
    p.towers.delete(b.id);
    a.type = recipe.result;
    a.lvl = 1;
    a.cooldown = 0;
    a.invested = invested;
    socket.emit('toast', { type: 'success', msg: `⚡ ${TOWERS[recipe.result].name} créé !` });
  }

  sendUnit(socket, pid, { unit, count }) {
    const p = this.players.get(pid);
    if (!p || !p.alive || this.over) return;
    const def = UNITS[unit];
    if (!def) return;
    count = Math.max(1, Math.min(10, count | 0 || 1));
    const totalCost = def.cost * count;
    if (p.gold < totalCost) return this.err(socket, 'Or insuffisant');
    const targets = [...this.players.values()].filter(q => q.alive && q.id !== pid);
    // En solo, les unités arrivent sur son propre terrain (mode entraînement).
    const dests = targets.length ? targets : [p];
    p.gold -= totalCost;
    p.income += def.income * count;
    p.sent += count;
    const hpScale = 1 + SEND_HP_SCALE_PER_WAVE * this.waveNum;
    for (const q of dests) {
      for (let i = 0; i < count; i++) {
        q.spawnQueue.push({
          at: this.time + i * 0.4,
          def: {
            kind: 'sent', name: def.name,
            hp: Math.round(def.hp * hpScale),
            speed: def.speed, armor: def.armor,
            leak: def.leak, bounty: def.bounty,
            color: def.color, from: p.name,
          },
        });
      }
      q.spawnQueue.sort((a, b) => a.at - b.at);
    }
  }

  // ---------- Fin de partie ----------
  eliminate(p) {
    if (!p.alive) return;
    p.alive = false;
    p.lives = 0;
    p.creeps.clear();
    p.spawnQueue.length = 0;
    this.io.to(this.roomCode).emit('toast', { type: 'info', msg: `💀 ${p.name} est éliminé !` });
  }

  playerLeft(pid) {
    const p = this.players.get(pid);
    if (p && p.alive) {
      this.eliminate(p);
      this.checkEnd();
    }
  }

  checkEnd() {
    if (this.over) return;
    const alive = [...this.players.values()].filter(p => p.alive);
    if (this.players.size > 1 && alive.length <= 1) {
      this.over = true;
      const winner = alive[0] || null;
      this.io.to(this.roomCode).emit('gameOver', {
        winnerId: winner ? winner.id : null,
        winnerName: winner ? winner.name : null,
        wave: this.waveNum,
      });
      this.stop();
    } else if (this.players.size === 1 && alive.length === 0) {
      this.over = true;
      this.io.to(this.roomCode).emit('gameOver', {
        winnerId: null, winnerName: null, wave: this.waveNum,
      });
      this.stop();
    }
  }

  // ---------- Snapshot réseau ----------
  broadcast() {
    const snapshot = {
      t: Math.round(this.time * 100) / 100,
      wave: {
        num: this.waveNum,
        nextIn: Math.max(0, Math.round((this.nextWaveAt - this.time) * 10) / 10),
        nextDef: WAVES[Math.min(this.waveNum, WAVES.length - 1)],
      },
      incomeIn: Math.max(0, Math.round((this.nextIncomeAt - this.time) * 10) / 10),
      players: [...this.players.values()].map(p => ({
        id: p.id,
        name: p.name,
        alive: p.alive,
        gold: Math.floor(p.gold),
        income: p.income,
        lives: p.lives,
        research: p.research,
        kills: p.kills,
        towers: [...p.towers.values()].map(t => ({
          id: t.id, type: t.type, x: t.x, y: t.y, lvl: t.lvl,
        })),
        creeps: [...p.creeps.values()].map(c => {
          const pos = posAt(c.dist);
          return {
            id: c.id,
            x: Math.round(pos.x), y: Math.round(pos.y),
            hp: Math.max(0, Math.round(c.hp)), mhp: c.maxHp,
            color: c.color, boss: !!c.boss, kind: c.kind,
            slow: c.slowUntil > this.time,
            stun: c.stunUntil > this.time,
            burn: c.burnUntil > this.time,
          };
        }),
        shots: p.shots,
      })),
    };
    for (const p of this.players.values()) p.shots = [];
    this.io.to(this.roomCode).emit('state', snapshot);
  }
}
