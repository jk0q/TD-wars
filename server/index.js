// ============================================================
// Serveur TD Wars — Express (statique) + Socket.IO (lobby & jeu)
// ============================================================
import express from 'express';
import http from 'http';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';
import { Server } from 'socket.io';
import { Game } from './game.js';
import { MAX_PLAYERS } from '../shared/data.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
app.use(express.static(path.join(__dirname, '../public')));
app.use('/shared', express.static(path.join(__dirname, '../shared')));

const server = http.createServer(app);
const io = new Server(server);

/** code -> { code, hostId, started, game, players: [{id, name}] } */
const rooms = new Map();

function makeCode() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let code;
  do {
    code = Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
  } while (rooms.has(code));
  return code;
}

function roomInfo(room) {
  return {
    code: room.code,
    hostId: room.hostId,
    started: room.started,
    players: room.players.map(p => ({ id: p.id, name: p.name })),
  };
}

function cleanName(name) {
  return String(name || '').trim().slice(0, 16) || 'Joueur';
}

io.on('connection', (socket) => {
  socket.data.room = null;

  socket.on('createRoom', ({ name }, cb) => {
    if (socket.data.room) return;
    const code = makeCode();
    const room = {
      code, hostId: socket.id, started: false, game: null,
      players: [{ id: socket.id, name: cleanName(name) }],
    };
    rooms.set(code, room);
    socket.join(code);
    socket.data.room = code;
    cb?.({ ok: true, room: roomInfo(room) });
  });

  socket.on('joinRoom', ({ name, code }, cb) => {
    if (socket.data.room) return;
    code = String(code || '').trim().toUpperCase();
    const room = rooms.get(code);
    if (!room) return cb?.({ ok: false, error: 'Salon introuvable' });
    if (room.started) return cb?.({ ok: false, error: 'La partie a déjà commencé' });
    if (room.players.length >= MAX_PLAYERS) return cb?.({ ok: false, error: 'Salon complet' });
    room.players.push({ id: socket.id, name: cleanName(name) });
    socket.join(code);
    socket.data.room = code;
    cb?.({ ok: true, room: roomInfo(room) });
    io.to(code).emit('roomUpdate', roomInfo(room));
  });

  socket.on('leaveRoom', () => leaveRoom(socket));

  socket.on('startGame', () => {
    const room = rooms.get(socket.data.room);
    if (!room || room.started || room.hostId !== socket.id) return;
    room.started = true;
    room.game = new Game(io, room.code, room.players);
    room.game.start();
    io.to(room.code).emit('gameStarted', {
      players: room.players.map(p => ({ id: p.id, name: p.name })),
    });
  });

  // --- Actions en jeu ---
  const gameAction = (handler) => (payload) => {
    const room = rooms.get(socket.data.room);
    if (!room?.game) return;
    handler(room.game, payload || {});
  };
  socket.on('build', gameAction((g, p) => g.build(socket, socket.id, p)));
  socket.on('upgrade', gameAction((g, p) => g.upgrade(socket, socket.id, p)));
  socket.on('sell', gameAction((g, p) => g.sell(socket, socket.id, p)));
  socket.on('research', gameAction((g, p) => g.research(socket, socket.id, p)));
  socket.on('combine', gameAction((g, p) => g.combine(socket, socket.id, p)));
  socket.on('sendUnit', gameAction((g, p) => g.sendUnit(socket, socket.id, p)));

  socket.on('disconnect', () => leaveRoom(socket));
});

function leaveRoom(socket) {
  const code = socket.data.room;
  if (!code) return;
  const room = rooms.get(code);
  socket.data.room = null;
  socket.leave(code);
  if (!room) return;
  room.players = room.players.filter(p => p.id !== socket.id);
  if (room.game) room.game.playerLeft(socket.id);
  if (room.players.length === 0) {
    room.game?.stop();
    rooms.delete(code);
    return;
  }
  if (room.hostId === socket.id) room.hostId = room.players[0].id;
  io.to(code).emit('roomUpdate', roomInfo(room));
}

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`⚔️  TD Wars — serveur lancé sur http://localhost:${PORT}`);
  const lanIps = Object.values(os.networkInterfaces()).flat()
    .filter(i => i && i.family === 'IPv4' && !i.internal)
    .map(i => i.address);
  for (const ip of lanIps) {
    console.log(`📱 Depuis un téléphone sur le même réseau : http://${ip}:${PORT}`);
  }
});
