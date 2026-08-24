# Savacom — automatisation des flux comptables

Chaîne qui va des relevés bancaires reçus par Savacom Sàrl (fiduciaire, Cernier)
jusqu'aux écritures importées dans WinBiz et aux justificatifs archivés sur le
NAS. Remplace Multigest, qui quitte le marché suisse.

**Aucune donnée client dans ce dépôt.** Relevés, exports bancaires et
justificatifs restent chez le client. Voir `.gitignore`.

---

## Par où commencer

| Vous voulez… | Lisez |
|---|---|
| Comprendre le vocabulaire du projet | [`CONTEXT.md`](./CONTEXT.md) |
| Savoir pourquoi c'est fait ainsi | [`docs/adr/`](./docs/adr/) — 15 décisions |
| Intervenir chez le client | [`PROTOCOLE-INTERVENTION.md`](./PROTOCOLE-INTERVENTION.md) |
| Convertir un export UBS | `python ubs_vers_winbiz.py --help` |

Trois termes suffisent à ne pas se perdre : un **mandat** est une société dont
Savacom tient les comptes ; un **export bancaire** vient de la banque ; un
**fichier d'import** est ce que WinBiz avale. Les trois sont appelés « CSV » dans
les documents d'origine, et ce sont trois choses différentes.

---

## État

**Fait.** Convertisseur UBS validé sur 770 transactions réelles : 760 écritures
produites, chaîne des soldes intacte, total reconstituant le solde final au
centime.

**Décidé, non construit.** Registre anti-doublons (ADR 0011), quarantaine
(ADR 0005), table des mandats (ADR 0009), journal cumulatif (ADR 0014),
raccourci de lancement (ADR 0013).

**Ouvert — se tranche sur place.** Format exact d'import WinBiz ; place de la
référence QR ; CAMT natif ou conversion CSV (ADR 0007) ; forme et profondeur du
chemin d'archive.

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
