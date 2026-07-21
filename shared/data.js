// ============================================================
// Données du jeu — partagées entre le serveur et le client.
// Module ES pur : aucune dépendance Node ni navigateur.
// ============================================================

// --- Plateau -------------------------------------------------
export const GRID = { cols: 16, rows: 12, cell: 40 };

// Chemin en serpentin (coordonnées de cellules [col, row])
export const WAYPOINTS = [
  [0, 1], [14, 1], [14, 4], [1, 4], [1, 7], [14, 7], [14, 10], [0, 10],
];

export function computePathCells() {
  const cells = new Set();
  for (let i = 0; i < WAYPOINTS.length - 1; i++) {
    const [c1, r1] = WAYPOINTS[i];
    const [c2, r2] = WAYPOINTS[i + 1];
    const dc = Math.sign(c2 - c1);
    const dr = Math.sign(r2 - r1);
    let c = c1, r = r1;
    cells.add(`${c},${r}`);
    while (c !== c2 || r !== r2) {
      c += dc; r += dr;
      cells.add(`${c},${r}`);
    }
  }
  return cells;
}

// --- Constantes de partie -----------------------------------
export const START_LIVES = 40;
export const START_GOLD = 180;
export const START_INCOME = 12;
export const INCOME_INTERVAL = 15;   // secondes entre deux paiements d'income
export const WAVE_INTERVAL = 25;     // secondes entre deux vagues
export const FIRST_WAVE_DELAY = 20;  // délai avant la première vague
export const SELL_RATIO = 0.7;       // remboursement à la vente
export const MAX_PLAYERS = 4;

// --- Types de dégâts vs armures (façon WC3) ------------------
export const ARMORS = ['legere', 'moyenne', 'lourde', 'fortifiee'];
export const ARMOR_NAMES = {
  legere: 'Légère', moyenne: 'Moyenne', lourde: 'Lourde', fortifiee: 'Fortifiée',
};
export const ATK_NAMES = {
  normal: 'Normal', perce: 'Perçant', siege: 'Siège', magie: 'Magie', chaos: 'Chaos',
};
export const ATK_VS_ARMOR = {
  normal: { legere: 1.0, moyenne: 1.0, lourde: 1.0, fortifiee: 0.7 },
  perce:  { legere: 1.5, moyenne: 1.1, lourde: 0.75, fortifiee: 0.4 },
  siege:  { legere: 0.8, moyenne: 1.0, lourde: 1.1, fortifiee: 1.5 },
  magie:  { legere: 1.0, moyenne: 1.4, lourde: 1.6, fortifiee: 0.6 },
  chaos:  { legere: 1.0, moyenne: 1.0, lourde: 1.0, fortifiee: 1.0 },
};

// --- Recherches ---------------------------------------------
export const RESEARCH = {
  elementaire: {
    name: 'Élémentaire',
    icon: '🔥',
    costs: [80, 200, 450],
    unlocks: [
      'Débloque les tours Feu et Glace',
      'Débloque la tour Foudre',
      'Débloque la tour Arcane',
    ],
  },
  science: {
    name: 'Science',
    icon: '⚙️',
    costs: [100, 250, 500],
    unlocks: [
      'Débloque la tour Tesla',
      'Débloque la tour Laser',
      'Débloque le Canon Rail',
    ],
  },
  evolution: {
    name: 'Évolution',
    icon: '🧬',
    costs: [120, 300, 600],
    unlocks: [
      'Permet d\'améliorer les tours au niveau 2',
      'Permet d\'améliorer les tours au niveau 3',
      'Débloque les COMBINAISONS de tours',
    ],
  },
};

// --- Multiplicateurs par niveau de tour ----------------------
// L'amélioration vers le niveau N coûte cost * LVL_COST[N-1].
export const LVL_DMG = [1, 2.1, 4.5];
export const LVL_COST = [0, 1.5, 3];
export const LVL_CD = [1, 0.92, 0.85];
export const LVL_RANGE = [0, 12, 25];

// --- Tours ---------------------------------------------------
// tier: base | elem | sci | combo
// req: { branch, lvl } recherche nécessaire pour construire
export const TOWERS = {
  archer: {
    name: 'Archer', tier: 'base', req: null, cost: 15,
    dmg: 6, cd: 0.7, range: 140, atk: 'perce', color: '#a3be5f',
    desc: 'Tir rapide et pas cher. Bon contre armure légère.',
  },
  canon: {
    name: 'Canon', tier: 'base', req: null, cost: 40,
    dmg: 14, cd: 1.8, range: 120, atk: 'siege', splash: 45, color: '#8a7a5c',
    desc: 'Dégâts de zone. Excellent contre armure fortifiée.',
  },
  feu: {
    name: 'Feu', tier: 'elem', req: { branch: 'elementaire', lvl: 1 }, cost: 60,
    dmg: 12, cd: 0.9, range: 130, atk: 'magie', splash: 25,
    burnDps: 8, burnDur: 3, color: '#e2593b',
    desc: 'Enflamme les ennemis (dégâts sur la durée) + petite zone.',
  },
  glace: {
    name: 'Glace', tier: 'elem', req: { branch: 'elementaire', lvl: 1 }, cost: 60,
    dmg: 8, cd: 1.0, range: 130, atk: 'magie',
    slowPct: 0.35, slowDur: 2, color: '#5fc7e2',
    desc: 'Ralentit les ennemis de 35% pendant 2s.',
  },
  foudre: {
    name: 'Foudre', tier: 'elem', req: { branch: 'elementaire', lvl: 2 }, cost: 140,
    dmg: 26, cd: 1.1, range: 150, atk: 'magie', chain: 3, color: '#e2d05f',
    desc: 'Éclair en chaîne qui rebondit sur 3 cibles.',
  },
  arcane: {
    name: 'Arcane', tier: 'elem', req: { branch: 'elementaire', lvl: 3 }, cost: 320,
    dmg: 70, cd: 1.0, range: 160, atk: 'chaos', color: '#b25fe2',
    desc: 'Dégâts de chaos purs, efficaces contre tout.',
  },
  tesla: {
    name: 'Tesla', tier: 'sci', req: { branch: 'science', lvl: 1 }, cost: 70,
    dmg: 5, cd: 0.25, range: 125, atk: 'perce', color: '#5fe2c7',
    desc: 'Cadence de tir extrême.',
  },
  laser: {
    name: 'Laser', tier: 'sci', req: { branch: 'science', lvl: 2 }, cost: 160,
    dmg: 45, cd: 1.5, range: 170, atk: 'perce', color: '#e25f9d',
    desc: 'Gros dégâts monocible à longue portée.',
  },
  rail: {
    name: 'Canon Rail', tier: 'sci', req: { branch: 'science', lvl: 3 }, cost: 350,
    dmg: 150, cd: 2.5, range: 200, atk: 'siege', splash: 30, color: '#7a8ae2',
    desc: 'Obus dévastateur à très longue portée.',
  },
  // --- Tours de combinaison (Évolution niv. 3) ---
  vapeur: {
    name: 'Vapeur', tier: 'combo', cost: 0,
    dmg: 90, cd: 0.8, range: 150, atk: 'magie', splash: 50,
    slowPct: 0.3, slowDur: 1.5, color: '#9fd8e8',
    desc: 'Feu + Glace : zone brûlante qui ralentit.',
  },
  plasma: {
    name: 'Plasma', tier: 'combo', cost: 0,
    dmg: 130, cd: 0.7, range: 160, atk: 'chaos', chain: 4, color: '#ff7a4d',
    desc: 'Feu + Foudre : chaîne de chaos à haute cadence.',
  },
  orage: {
    name: 'Orage', tier: 'combo', cost: 0,
    dmg: 110, cd: 0.9, range: 160, atk: 'magie', chain: 2,
    stunChance: 0.2, stunDur: 0.5, color: '#6d7ce8',
    desc: 'Glace + Foudre : 20% de chance d\'étourdir.',
  },
  gatling: {
    name: 'Gatling', tier: 'combo', cost: 0,
    dmg: 18, cd: 0.12, range: 150, atk: 'perce', color: '#c9d65f',
    desc: 'Archer + Tesla : déluge de balles.',
  },
  obusier: {
    name: 'Obusier', tier: 'combo', cost: 0,
    dmg: 320, cd: 2.2, range: 190, atk: 'siege', splash: 70, color: '#a8845c',
    desc: 'Canon + Rail : explosion massive.',
  },
  photon: {
    name: 'Photon', tier: 'combo', cost: 0,
    dmg: 160, cd: 0.5, range: 180, atk: 'chaos', color: '#ff9de2',
    desc: 'Tesla + Laser : rayon de chaos rapide.',
  },
  cataclysme: {
    name: 'Cataclysme', tier: 'combo', cost: 0,
    dmg: 400, cd: 0.8, range: 200, atk: 'chaos', splash: 60,
    slowPct: 0.3, slowDur: 1.5, stunChance: 0.15, stunDur: 0.5, color: '#e84d4d',
    desc: 'ULTIME — Vapeur + Orage : tempête dévastatrice.',
  },
  apocalypse: {
    name: 'Apocalypse', tier: 'combo', cost: 0,
    dmg: 300, cd: 0.3, range: 200, atk: 'chaos', chain: 5, color: '#ffd24d',
    desc: 'ULTIME — Plasma + Photon : annihilation en chaîne.',
  },
};

// --- Recettes de combinaison --------------------------------
// Deux tours ADJACENTES au niveau max se combinent (Évolution niv. 3).
export const RECIPES = [
  { a: 'feu', b: 'glace', result: 'vapeur', cost: 200 },
  { a: 'feu', b: 'foudre', result: 'plasma', cost: 250 },
  { a: 'glace', b: 'foudre', result: 'orage', cost: 250 },
  { a: 'archer', b: 'tesla', result: 'gatling', cost: 180 },
  { a: 'canon', b: 'rail', result: 'obusier', cost: 400 },
  { a: 'tesla', b: 'laser', result: 'photon', cost: 350 },
  { a: 'vapeur', b: 'orage', result: 'cataclysme', cost: 800 },
  { a: 'plasma', b: 'photon', result: 'apocalypse', cost: 900 },
];

export function findRecipe(typeA, typeB) {
  return RECIPES.find(r =>
    (r.a === typeA && r.b === typeB) || (r.a === typeB && r.b === typeA)) || null;
}

// --- Unités à envoyer (système d'income) ---------------------
export const UNITS = {
  gobelin: {
    name: 'Gobelin', cost: 20, income: 2, hp: 45, speed: 60,
    armor: 'legere', leak: 1, bounty: 3, color: '#7ec850',
  },
  loup: {
    name: 'Loup', cost: 35, income: 4, hp: 60, speed: 95,
    armor: 'legere', leak: 1, bounty: 4, color: '#9a9a9a',
  },
  orc: {
    name: 'Orc', cost: 60, income: 6, hp: 140, speed: 60,
    armor: 'moyenne', leak: 1, bounty: 6, color: '#4f7a3a',
  },
  harpie: {
    name: 'Harpie', cost: 120, income: 12, hp: 110, speed: 110,
    armor: 'legere', leak: 1, bounty: 8, color: '#c87ec8',
  },
  ogre: {
    name: 'Ogre', cost: 200, income: 18, hp: 450, speed: 50,
    armor: 'lourde', leak: 2, bounty: 15, color: '#b0713a',
  },
  chevalier: {
    name: 'Chevalier', cost: 350, income: 30, hp: 700, speed: 65,
    armor: 'lourde', leak: 2, bounty: 25, color: '#c0c8d8',
  },
  golem: {
    name: 'Golem', cost: 700, income: 60, hp: 1800, speed: 45,
    armor: 'fortifiee', leak: 3, bounty: 50, color: '#6a6a7a',
  },
  dragon: {
    name: 'Dragon', cost: 1500, income: 130, hp: 4200, speed: 70,
    armor: 'moyenne', leak: 5, bounty: 120, color: '#e04040',
  },
};

// --- Vagues --------------------------------------------------
const WAVE_NAMES = [
  'Gobelins', 'Loups affamés', 'Squelettes', 'Araignées géantes', 'Orcs',
  'Bandits', 'Harpies', 'Golems de pierre', 'Chevaliers noirs', 'SEIGNEUR OGRE',
  'Zombies', 'Trolls', 'Élémentaires de feu', 'Gargouilles', 'Berserkers',
  'Sorciers', 'Wyvernes', 'Golems de fer', 'Paladins déchus', 'ROI LICHE',
  'Abominations', 'Chevaliers du chaos', 'Démons', 'Ombres', 'Géants',
  'Hydres', 'Seigneurs de guerre', 'Golems d\'obsidienne', 'Archidémons', 'DRAGON ANCESTRAL',
];
const FAST_WAVES = new Set([1, 6, 16, 23]);
const WAVE_COLORS = ['#7ec850', '#9a9a9a', '#d8d8c0', '#5a3a6a', '#4f7a3a',
  '#8a6a4a', '#c87ec8', '#8a8a9a', '#3a3a4a', '#b0713a'];

function buildWaves() {
  const waves = [];
  for (let i = 0; i < 30; i++) {
    const boss = (i + 1) % 10 === 0;
    let hp = Math.round(32 * Math.pow(1.23, i));
    let count = 10;
    let speed = FAST_WAVES.has(i) ? 100 : 50 + (i % 3) * 8;
    let leak = 1;
    let armor = ARMORS[i % 4];
    if (boss) {
      hp *= 12; count = 1; speed = 45; leak = 5; armor = 'fortifiee';
    }
    waves.push({
      num: i + 1,
      name: WAVE_NAMES[i] + (boss ? ' (BOSS)' : ''),
      count, hp, speed, armor, leak, boss,
      bounty: Math.max(2, Math.round(3 + hp * (boss ? 0.1 : 0.06))),
      color: WAVE_COLORS[i % WAVE_COLORS.length],
    });
  }
  return waves;
}
export const WAVES = buildWaves();

// Au-delà de la vague 30 : mode sans fin, la vague 30 est répétée
// avec ce multiplicateur de PV appliqué à chaque répétition.
export const ENDLESS_SCALE = 1.35;
// Les unités envoyées gagnent des PV avec les vagues pour rester utiles.
export const SEND_HP_SCALE_PER_WAVE = 0.06;
