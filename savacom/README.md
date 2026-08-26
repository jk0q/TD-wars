# Savacom — relevés bancaires vers CSV

Savacom Sàrl (fiduciaire, Cernier) reçoit les relevés de ses mandats en PDF,
parfois en photo. Son logiciel comptable, **AE Pro Easy**, n'avale que le CSV
que la banque produit. Le travail consiste à faire le pont : lire le document
et le réécrire exactement comme la banque l'aurait exporté.

Quatre banques : **BCN, UBS, PostFinance, BCF**.

**Aucune donnée client dans ce dépôt.** Relevés, exports bancaires et
justificatifs restent chez le client. Voir `.gitignore`.

---

## Par où commencer

| Vous voulez… | Lisez |
|---|---|
| **Le livrable** | [`skills/releve-bancaire-vers-csv/`](./skills/releve-bancaire-vers-csv/SKILL.md) |
| Comprendre le vocabulaire du projet | [`CONTEXT.md`](./CONTEXT.md) |
| Savoir pourquoi c'est fait ainsi | [`docs/adr/`](./docs/adr/) — 15 décisions |
| Identifier un fichier inconnu | `python diagnostic.py "fichier.csv"` |

### Ce qui a changé

Le projet visait d'abord à produire des fichiers d'import **WinBiz** à partir
d'exports bancaires CSV. Les captures de l'écran d'AE Pro Easy ont montré que
ce logiciel fait déjà ce travail : il connaît le compte comptable de chaque
mandat, numérote les pièces, gère le compte d'attente et fabrique les écritures.

Le besoin réel est en amont : **partir d'un PDF ou d'une photo**, là où AE Pro
Easy n'a rien à se mettre sous la dent.

`ubs_vers_winbiz.py`, `PROTOCOLE-INTERVENTION.md`, `COMMANDES.md` et les
lanceurs `.bat` appartiennent à cette première direction. Ils restent dans le
dépôt — la connaissance des formats qu'ils contiennent alimente directement les
fichiers de format de la skill — mais ils ne sont plus le livrable.

`diagnostic.py`, lui, sert plus que jamais : c'est l'outil qui mesure un export
bancaire réel pour en déduire le format à imiter.

Trois termes suffisent à ne pas se perdre : un **mandat** est une société dont
Savacom tient les comptes ; un **export bancaire** vient de la banque ; un
**fichier d'import** est ce que WinBiz avale. Les trois sont appelés « CSV » dans
les documents d'origine, et ce sont trois choses différentes.

---

## État

**Fait.** La skill : méthode de lecture, contrôles arithmétiques, écriture
byte-exacte. Le vérificateur attrape les quatre modes d'échec d'une lecture de
scan — chiffre mal lu, ligne sautée, page manquante, lecture douteuse — et
refuse d'écrire un CSV tant qu'un seul contrôle échoue.

**Bloqué sur un fichier.** Les formats **BCN** et **PostFinance** n'ont jamais
été mesurés. Il faut, par banque, **un export CSV réel qui passe déjà l'import
d'AE Pro Easy** : c'est la spécification, et rien ne la remplace. Deviner des
colonnes produirait un fichier rejeté à l'import.

**En attente.** La **BCF** — faible volume. C'était aussi la plus incertaine :
aucune source publique n'atteste qu'elle produise un CSV (ADR 0017).

**Partiel.** UBS : encodage, fin de ligne, séparateur, nombre de colonnes et
format des montants sont mesurés ; les noms de colonnes verbatim et les lignes
de métadonnées restent à relever sur le fichier réel.

**À tester, sans code.** AE Pro Easy répond « le fichier semble être un extrait
Raiffeisen » quand on lui donne l'export UBS `11_Konto_*.csv` — qui a exactement
la forme d'un export Raiffeisen. Charger `transactions(13).csv` à la place
pourrait suffire à débloquer UBS.

**Hors périmètre.** Factures fournisseurs (ADR 0002), rapprochement automatique
des encaissements (ADR 0003), agent WhatsApp.

---

## Méthode

Une boucle, appliquée à chaque fichier inconnu :

1. **Mesurer** — encodage, fin de ligne, séparateur, colonnes, formats. Jamais
   lire : compter.
2. **Caractériser** — structure des enregistrements, cas particuliers.
3. **Chercher une invariante** — une règle vraie indépendamment de notre code.
4. **Transformer**, puis **vérifier la sortie contre l'invariante**.

Ce qui est mesuré et ce qui est supposé restent distincts, dans le code comme
devant le client.

### Invariantes utilisées

| Invariante | Ce qu'elle détecte | Statut |
|---|---|---|
| `solde[i] = solde[i+1] + montant[i]` | ligne perdue, dupliquée, signe inversé | 0 rupture / 769 |
| `somme(sous-montants) = montant de la ligne mère` | double comptage des versements collectifs | 102 / 102 |
| `encaissements − décaissements = variation de solde` | justesse globale de la conversion | exact au centime |
| `solde initial − débits + crédits = solde final` | intégrité d'un relevé | vérifié (BCN) |
| `page N sur M` | scan incomplet | avertissement |

---

## Formats

### Exports bancaires — trois formats, tous nommés « CSV »

| | `transactions(n).csv` (UBS e-banking) | `11_Konto_*.csv` | BCN |
|---|---|---|---|
| Encodage | UTF-8 **avec BOM** | Windows-1252 | scan 1 bit |
| Fin de ligne | LF | CRLF | — |
| Avant l'en-tête | 8 lignes de méta + 1 vide | rien | — |
| Colonnes | 15 | 6 | 6 visuelles |
| Montant | `Débit` / `Crédit` séparés, 2 décimales | 1 colonne signée | colonnes séparées, apostrophe |
| `;` dans les champs | **1754 occurrences** | aucune | — |
| Référence QR | **présente** (sous-lignes) | absente | — |
| Rotation | — | — | `/Rotate 270` |

`11_Konto` est un export appauvri : il a perdu les références QR nécessaires au
rapprochement. Ne pas l'utiliser comme source.

Un relevé scanné doit être **rendu** en respectant `/Rotate`, jamais extrait
comme image embarquée — le bitmap est stocké pivoté.

### Cible WinBiz

*Comptabilité → Écritures → Actions → Import/Export → Importation standard.*
Texte séparé par `;`, **ANSI 1252**, **CRLF**. Colonnes 1 à 7 pour une écriture
simple : `Date ; Pièce ; Débit ; Crédit ; Libellé ; Montant ; Journal`. Jusqu'à
15 avec TVA.

**Les colonnes 3 et 4 sont des numéros de compte, pas des montants** — le
montant est en colonne 6. Aucun fichier d'import ne peut donc être produit sans
décision d'imputation ; d'où le compte d'attente (ADR 0008).

À confirmer sur place : ligne d'en-tête attendue ou non, longueurs maximales,
existence d'un champ de référence dédié.

---

## Pièges rencontrés

1. **Guillemets d'échappement.** 640 libellés UBS sur 760 contiennent un `;`.
   La RFC 4180 les échappe, mais rien ne garantit qu'un importateur métier sache
   les relire. Le séparateur est retiré du contenu, jamais échappé.
2. **Versements collectifs.** 102 crédits décomposés en sous-lignes. Les compter
   produirait 102 écritures en double.
3. **Troncature des numéros de pièce.** Les numéros UBS ne diffèrent parfois que
   par leur dernier caractère : tronquer à gauche fabriquait 12 collisions.
4. **Collisions dans la source.** UBS réutilise un numéro pour un virement et
   ses « Frais de tiers ». Suffixé et tracé.
5. **Caractères hors cp1252.** Translittérés explicitement, jamais supprimés.
6. **Lignes à 0.00.** Écartées (10 cas).
7. **Faux ami.** WinBiz annonce renuméroter les écritures « pour éviter les
   doublons » : cela porte sur les numéros, pas sur le contenu. Rien ne protège
   d'un import chevauchant — d'où l'ADR 0011.

---

## Usage

```bash
python ubs_vers_winbiz.py transactions13.csv \
    --compte-banque 1020 --compte-attente 9999 --journal BQ
```

Produit le fichier d'import (ANSI 1252, CRLF) et un rapport : contrôles,
anomalies, écritures à imputer, références QR disponibles.

Le script sort en code 1 si une invariante est violée. **Ne rien importer dans
WinBiz tant que le rapport n'est pas propre.**
