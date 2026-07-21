// Test de fumée : lance le serveur, connecte 2 clients, crée/rejoint un
// salon, démarre la partie, construit, recherche, envoie des unités,
// et vérifie que la simulation tourne (snapshots cohérents).
import { spawn } from 'child_process';
import { io } from 'socket.io-client';

const PORT = 3123;
const URL = `http://localhost:${PORT}`;

const fail = (msg) => { console.error('❌ ' + msg); process.exit(1); };
const ok = (msg) => console.log('✅ ' + msg);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const server = spawn('node', ['server/index.js'], {
  env: { ...process.env, PORT },
  stdio: ['ignore', 'pipe', 'inherit'],
});
server.stdout.on('data', d => process.stdout.write('[server] ' + d));

const cleanup = () => server.kill();
process.on('exit', cleanup);

await sleep(1200);

const emit = (sock, ev, payload) => new Promise(r => sock.emit(ev, payload, r));
const connect = () => new Promise((resolve, reject) => {
  const s = io(URL, { transports: ['websocket'] });
  s.on('connect', () => resolve(s));
  s.on('connect_error', reject);
});

try {
  const alice = await connect();
  const bob = await connect();
  ok('Deux clients connectés');

  const created = await emit(alice, 'createRoom', { name: 'Alice' });
  if (!created?.ok) fail('createRoom a échoué');
  const code = created.room.code;
  ok(`Salon créé : ${code}`);

  const joined = await emit(bob, 'joinRoom', { name: 'Bob', code });
  if (!joined?.ok) fail('joinRoom a échoué');
  if (joined.room.players.length !== 2) fail('le salon devrait avoir 2 joueurs');
  ok('Bob a rejoint le salon');

  const started = new Promise(r => alice.on('gameStarted', r));
  alice.emit('startGame');
  await started;
  ok('Partie démarrée');

  let lastSnap = null;
  const toasts = [];
  alice.on('state', s => { lastSnap = s; });
  alice.on('toast', t => toasts.push(t));

  await sleep(500);
  if (!lastSnap) fail('aucun snapshot reçu');
  if (lastSnap.players.length !== 2) fail('snapshot: 2 joueurs attendus');
  ok('Snapshots reçus');

  // Construction valide (case hors chemin : 2,2)
  alice.emit('build', { x: 2, y: 2, type: 'archer' });
  // Construction invalide (sur le chemin : ligne 1)
  alice.emit('build', { x: 5, y: 1, type: 'archer' });
  await sleep(400);
  const meP = () => lastSnap.players.find(p => p.name === 'Alice');
  if (meP().towers.length !== 1) fail(`1 tour attendue, ${meP().towers.length} trouvée(s)`);
  if (!toasts.some(t => t.msg.includes('chemin'))) fail('la construction sur le chemin devrait être refusée');
  ok('Construction validée (et chemin protégé)');

  // Recherche élémentaire puis construction d'une tour Feu
  alice.emit('research', { branch: 'elementaire' });
  await sleep(300);
  if (meP().research.elementaire !== 1) fail('recherche élémentaire non prise en compte');
  alice.emit('build', { x: 3, y: 2, type: 'feu' });
  await sleep(300);
  if (meP().towers.length !== 2) fail('la tour Feu aurait dû être construite');
  ok('Recherche + tour élémentaire');

  // Envoi d'unités : income doit augmenter, creeps chez Bob
  const incomeBefore = meP().income;
  alice.emit('sendUnit', { unit: 'gobelin', count: 1 });
  await sleep(1500);
  if (meP().income !== incomeBefore + 2) fail(`income attendu ${incomeBefore + 2}, obtenu ${meP().income}`);
  const bobP = lastSnap.players.find(p => p.name === 'Bob');
  if (!bobP.creeps.some(c => c.kind === 'sent')) fail('les gobelins devraient être chez Bob');
  ok('Envoi d\'unités : income +2, creeps chez Bob');

  // La simulation avance et les creeps bougent
  const t1 = lastSnap.t;
  const c1 = bobP.creeps[0] && { ...bobP.creeps[0] };
  await sleep(1000);
  if (lastSnap.t <= t1) fail('le temps de simulation ne progresse pas');
  const c2 = lastSnap.players.find(p => p.name === 'Bob').creeps.find(c => c.id === c1?.id);
  if (c1 && c2 && c1.x === c2.x && c1.y === c2.y) fail('les creeps ne bougent pas');
  ok('Simulation active, creeps en mouvement');

  // Déconnexion de Bob -> Alice gagne
  const over = new Promise(r => alice.on('gameOver', r));
  bob.disconnect();
  const result = await over;
  if (result.winnerName !== 'Alice') fail('Alice devrait gagner après la déconnexion de Bob');
  ok('Fin de partie correcte (victoire d\'Alice)');

  console.log('\n🎉 Tous les tests passent');
  alice.disconnect();
  process.exit(0);
} catch (e) {
  fail(e.stack || String(e));
}
