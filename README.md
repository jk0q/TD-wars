# ⚔️ TD Wars — Tower Defense Wars multijoueur

Un Tower Defense Wars multijoueur (2 à 4 joueurs) dans l'esprit des TD wars
de Warcraft 3 (Wintermaul Wars, Legion TD) : chaque joueur défend son propre
couloir contre des vagues automatiques, et **envoie des monstres chez ses
adversaires pour booster son income**. Le dernier joueur en vie gagne.

## Lancer le jeu

```bash
npm install
npm start          # serveur sur http://localhost:3000
```

Ouvrez `http://localhost:3000`, créez un salon, partagez le code à 4 lettres
avec vos adversaires (jusqu'à 4 joueurs), puis l'hôte lance la partie.
Vous pouvez aussi lancer en solo pour vous entraîner (vos envois d'unités
arrivent alors sur votre propre terrain).

```bash
npm test           # test de fumée bout-en-bout (serveur + 2 clients simulés)
```

## 📱 Jouer sur Android (téléphone / tablette)

Le jeu est entièrement tactile et fonctionne comme une **PWA** (application
web installable) :

1. Lancez le serveur (`npm start`) — il affiche l'adresse réseau local à
   utiliser (ex. `http://192.168.1.42:3000`).
2. Sur le téléphone (même Wi-Fi), ouvrez cette adresse dans Chrome.
3. Menu ⋮ → **« Ajouter à l'écran d'accueil »** (ou « Installer l'appli ») :
   le jeu se lance alors en plein écran paysage, comme une vraie app.

Contrôles tactiles : touchez une carte de tour, puis une case libre — un
premier tap affiche l'aperçu (portée comprise), un second tap confirme.
Touchez une tour posée pour l'améliorer, la vendre ou la combiner.

Pour jouer **hors de chez vous** (amis à distance), déployez le serveur sur
un hébergeur Node.js (Render, Railway, Fly.io, VPS…) et partagez l'URL —
la PWA s'installe alors depuis n'importe où en HTTPS.

### APK natif (optionnel, via Capacitor)

Si vous voulez un vrai APK à installer/distribuer, enveloppez l'URL de
votre serveur déployé avec [Capacitor](https://capacitorjs.com) :

```bash
npm install @capacitor/core @capacitor/cli @capacitor/android
npx cap init "TD Wars" ch.kapt.tdwars --web-dir public
# dans capacitor.config.json, pointez l'app vers votre serveur :
#   "server": { "url": "https://votre-serveur.example.com" }
npx cap add android
npx cap open android   # puis Build > Build APK dans Android Studio
```

L'APK n'est qu'une coquille WebView : le multijoueur passe toujours par
votre serveur, tous les joueurs (web, PWA, APK) jouent ensemble.

## Principes du jeu

- **Vagues** : une vague de monstres toutes les 25 s (30 vagues, boss toutes
  les 10, puis mode sans fin). Chaque monstre qui atteint la sortie vous
  coûte des vies (40 au départ).
- **Income** : votre income est versé en or toutes les 15 s. Envoyer des
  unités chez **tous** vos adversaires coûte de l'or mais **augmente
  définitivement votre income** — le cœur de l'économie, comme dans Legion TD.
- **Armures et dégâts** (façon WC3) : Perçant, Siège, Magie, Chaos contre
  armures Légère, Moyenne, Lourde, Fortifiée. Variez vos tours !

## Recherches (3 branches)

| Branche | Débloque |
|---|---|
| 🔥 **Élémentaire** | Feu & Glace → Foudre → Arcane |
| ⚙️ **Science** | Tesla → Laser → Canon Rail |
| 🧬 **Évolution** | Tours niveau 2 → niveau 3 → **Combinaisons** |

## Combinaisons de tours

Deux tours **adjacentes au niveau maximum** peuvent fusionner (Évolution 3) :

- Feu + Glace → **Vapeur** · Feu + Foudre → **Plasma** · Glace + Foudre → **Orage**
- Archer + Tesla → **Gatling** · Canon + Rail → **Obusier** · Tesla + Laser → **Photon**
- Ultimes : Vapeur + Orage → **Cataclysme** · Plasma + Photon → **Apocalypse**

## Architecture

- `server/` — serveur Node.js autoritaire (Express + Socket.IO) : lobby à
  salons, simulation à 20 ticks/s, diffusion d'états à 10/s.
- `public/` — client HTML5 Canvas sans build (modules ES), rendu interpolé.
- `shared/data.js` — toutes les données d'équilibrage (tours, unités,
  vagues, recettes, recherches) partagées serveur/client : c'est **le**
  fichier à éditer pour équilibrer le jeu.
