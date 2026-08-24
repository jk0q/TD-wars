# Savacom — automatisation des flux comptables

Convertisseurs et notes techniques pour la mission Savacom Sàrl (Cédric Schwartz).
Objectif : PDF / relevés bancaires → CSV importable dans WinBiz, avec archivage
des justificatifs.

**Aucune donnée client dans ce dépôt.** Les relevés, exports bancaires et
justificatifs restent chez le client. Voir `.gitignore`.

---

## Méthode

Une seule boucle, appliquée à chaque fichier inconnu :

1. **Mesurer** — encodage, fin de ligne, séparateur, nombre de colonnes,
   formats de date et de montant. Jamais lire : compter.
2. **Caractériser** — structure des enregistrements, cas particuliers,
   valeurs aberrantes.
3. **Chercher une invariante** — une règle vraie indépendamment de notre code,
   qui servira de juge.
4. **Transformer**, puis **vérifier la sortie contre l'invariante**.

Ce qui est mesuré et ce qui est supposé doivent rester distincts, à l'oral
comme dans le code.

## Invariantes utilisées

| Invariante | Ce qu'elle détecte | Statut |
|---|---|---|
| `solde[i] = solde[i+1] + montant[i]` | ligne perdue, dupliquée, signe inversé | 0 rupture / 769 |
| `somme(sous-montants) = montant de la ligne mère` | double comptage des versements collectifs | 102 / 102 |
| `encaissements − décaissements = solde final − solde initial` | justesse globale de la conversion | exact au centime |
| `solde initial − débits + crédits = solde final` (pied de page BCN) | intégrité d'un relevé scanné | vérifié |
| `page N sur M` | scan incomplet | le relevé BCN reçu s'arrête à 2/3 |

## Formats constatés

### Exports bancaires — trois formats distincts, tous nommés « CSV »

| | `transactions(n).csv` (UBS e-banking) | `11_Konto_*.csv` | BCN |
|---|---|---|---|
| Encodage | UTF-8 **avec BOM** | Windows-1252 | scan 1 bit |
| Fin de ligne | LF | CRLF | — |
| Avant l'en-tête | 8 lignes de méta + 1 vide | rien | — |
| Colonnes | 15 | 6 | 6 (visuelles) |
| Montant | `Débit` et `Crédit` séparés, 2 décimales | 1 colonne signée, décimales variables | colonnes séparées, apostrophe de milliers |
| `;` dans les champs | **1754 occurrences** | aucune | — |
| Référence QR du payeur | **présente** (sous-lignes) | absente | — |
| Orientation | — | — | **pivoté à 90°** |

Le fichier `11_Konto` est un export appauvri : il a perdu les références QR
nécessaires au rapprochement. Ne pas l'utiliser comme source.

### Cible WinBiz

D'après la documentation Winbiz (*Comptabilité → Écritures → Actions →
Import/Export → Importation standard*) :

- texte séparé par `;`, encodage **ANSI 1252**, fin de ligne **CRLF** ;
- colonnes 1 à 7 pour une écriture simple :
  `Date ; Pièce ; Débit ; Crédit ; Libellé ; Montant ; Journal` ;
- colonnes 1 à 15 dès qu'il y a de la TVA ; 1 à 9 plus 16 et 17 en devises.

**Les colonnes 3 et 4 sont des numéros de compte, pas des montants.** Le
montant est en colonne 6. Conséquence : aucun fichier d'import ne peut être
produit sans décision d'imputation. Le convertisseur écrit le compte bancaire
d'un côté et un compte d'attente de l'autre ; l'imputation reste manuelle.

À confirmer sur place : présence ou non d'une ligne d'en-tête, longueur maximale
des champs `Pièce` et `Libellé`, code journal attendu.

## Pièges rencontrés

1. **Guillemets d'échappement.** 640 libellés UBS sur 760 contiennent un `;`.
   La RFC 4180 les échappe entre guillemets, mais rien ne garantit qu'un
   importateur métier sache les relire. Le séparateur est retiré du contenu,
   jamais échappé.
2. **Versements collectifs.** 102 crédits sont décomposés en sous-lignes.
   Les compter produirait 102 écritures en double.
3. **Troncature des numéros de pièce.** Les numéros UBS ne diffèrent parfois
   que par leur dernier caractère : tronquer à gauche fabriquait 12 collisions.
   On tronque par la fin.
4. **Collisions dans la source.** UBS réutilise un numéro pour un virement et
   ses « Frais de tiers » (3 cas). Suffixé et tracé.
5. **Caractères hors cp1252.** Translittérés explicitement, jamais supprimés
   en silence.
6. **Lignes à 0.00.** Écartées (10 cas, « Solde décompte des prix prestations »).

## Usage

```bash
python ubs_vers_winbiz.py transactions13.csv \
    --compte-banque 1020 \
    --compte-attente 9999 \
    --journal BQ
```

Produit `transactions13_winbiz.csv` (ANSI 1252, CRLF) et
`transactions13_rapport.txt` : contrôles, anomalies, écritures à imputer,
références QR disponibles pour le rapprochement.

Le script sort en code 1 si une invariante est violée. Ne rien importer dans
WinBiz tant que le rapport n'est pas propre.

## Mandats identifiés

Savacom est une fiduciaire : les comptes traités appartiennent à ses clients,
pas à elle. Trois mandats apparaissent dans les fichiers d'exemple, chacun avec
sa banque et son format. Le routage vers le NAS et le plan comptable sont donc
propres à chaque mandat.

## Questions ouvertes

- Aucun **fichier d'import WinBiz réussi** n'a encore été observé. Tous les
  fichiers reçus sont des exports bancaires. Le format cible reste à confirmer.
- WinBiz lit nativement les **CAMT.053 / 054** avec un moteur de règles.
  Si la fonction est disponible, une grande partie du traitement bancaire ne
  nécessite ni conversion ni IA. À trancher avant d'industrialiser.
- Niveau d'imputation attendu : compte de charge et code TVA proposés, ou
  seulement la ligne bancaire ?
