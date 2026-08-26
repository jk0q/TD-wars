---
name: releve-bancaire-vers-csv
description: >-
  Transforme un relevé bancaire suisse reçu en PDF, en scan ou en photo
  en fichier CSV au format d'export de la banque, prêt à importer dans un
  logiciel de comptabilité. Couvre BCN, UBS, PostFinance et BCF. Vérifie
  l'arithmétique du relevé avant d'écrire quoi que ce soit, et refuse de
  produire un CSV quand les totaux ne tombent pas juste. À utiliser dès
  qu'un relevé, un extrait de compte ou un avis bancaire est déposé en PDF
  ou en image et qu'il est question de comptabilité, d'import, d'écritures
  ou de saisie — y compris quand le mot « CSV » n'est jamais prononcé.
---

# Relevé bancaire → CSV

Un comptable reçoit le relevé d'un client en PDF, parfois en photo. Son
logiciel, lui, n'avale que le CSV que la banque produit. Cette skill fait le
pont : elle lit le document et réécrit son contenu **exactement comme la
banque l'aurait exporté**.

## Le principe qui gouverne tout le reste

Lire un CSV ne peut pas inventer de chiffre : on recopie. **Lire une image,
si.** Un 3 pris pour un 8, une virgule perdue, une ligne sautée entre deux
pages — et le chiffre faux part en comptabilité sans que personne ne le voie,
parce qu'il est plausible.

En comptabilité, un chiffre faux et crédible est pire qu'un trou. Un trou se
voit, se corrige. Un faux se propage.

D'où la règle : **on ne produit un CSV que si l'arithmétique du relevé se
referme.** Un relevé imprime ses propres totaux — c'est un cadeau, il porte sa
propre preuve. On lit, on recalcule, on compare. Si ça ne tombe pas juste, on
ne sort rien et on dit quelle ligne pose problème.

Le partage du travail découle de là : **la lecture est un travail de modèle,
l'arithmétique et les octets sont un travail de code.** Ne fais pas les
additions de tête sur deux cents lignes — passe par `scripts/verifier.py`.

## Étape 1 — Identifier la banque

Une erreur de banque et l'import est refusé, parce que le logiciel comptable
inspecte le fichier et compare avec la banque sélectionnée. Il faut donc être
sûr, pas confiant.

Trois sources, par ordre de fiabilité :

1. **L'IBAN**, s'il figure sur le document. Les chiffres 5 à 9 sont le numéro
   de clearing de la banque, et il ne ment pas :

   | Clearing | Banque | Exemple d'IBAN |
   |---|---|---|
   | `00766` | BCN — Banque Cantonale Neuchâteloise | `CH17 0076 6000 1034 3068 1` |
   | `00204` | UBS | `CH87 0020 4204 1952 8901 U` |
   | `09000` | PostFinance | `CH.. 0900 0000 ...` |
   | `00768` | BCF — Banque Cantonale de Fribourg | à confirmer sur un vrai relevé |

2. **L'en-tête du document** — logo, raison sociale, adresse.
3. **Ce que dit l'utilisateur.**

Si les sources se contredisent, ou si l'IBAN est absent et le logo illisible,
**demande**. Ne tranche pas au jugé : le coût d'une question est dix secondes,
le coût d'une erreur est un import rejeté chez le client, ou pire, un import
accepté dans le mauvais compte.

## Étape 2 — Lire le document

Lis **toutes les pages**, et vérifie la mention « page N sur M » : un scan
tronqué est le défaut le plus fréquent et le plus silencieux.

Le document arrive de deux manières, et elles ne se traitent pas pareil :

- **Déposé dans la conversation** — tu le vois déjà, page par page. Lis-le tel
  qu'il t'est présenté.
- **Un fichier sur le disque** — fais rendre chaque page en respectant son
  attribut `/Rotate`. N'extrais jamais l'image embarquée telle quelle : elle
  est souvent stockée pivotée alors que la page s'affiche droite, et tu lirais
  un document couché.

Pour chaque ligne du relevé, relève : la date, la date de valeur si elle est
distincte, le libellé complet, le montant au débit **ou** au crédit, et le
solde courant s'il est imprimé.

**Marque ce dont tu n'es pas sûr.** Un chiffre à moitié coupé, un caractère
ambigu, une ligne à cheval sur deux pages : mets `"confiance": "douteuse"` et
dis pourquoi dans `"note"`. Le vérificateur bloquera dessus, et c'est
exactement ce qu'on veut — un humain regardera. Deviner pour « finir proprement »
est le seul vrai échec possible ici.

Relève aussi les **totaux imprimés** : solde initial, solde final, total des
débits, total des crédits. Ce sont eux qui vont servir de preuve.

Écris tout ça dans un fichier JSON. Le format attendu est décrit en tête de
`scripts/verifier.py` — lis-le avant d'écrire.

## Étape 3 — Vérifier

```bash
python scripts/verifier.py controler releve.json
```

Le script recalcule et compare :

- somme des débits lus = total des débits imprimé
- somme des crédits lus = total des crédits imprimé
- solde initial − débits + crédits = solde final imprimé
- chaîne des soldes ligne à ligne, quand les soldes sont imprimés
- nombre de pages lues = nombre de pages annoncées
- aucune ligne marquée douteuse
- toutes les dates dans la période du relevé

Si une seule échoue, **arrête-toi**. N'écris pas de CSV. Montre le rapport et
dis à l'utilisateur quelle ligne relire — le script nomme l'écart au centime,
ce qui suffit presque toujours à retrouver le chiffre mal lu.

Ne contourne pas un contrôle en ajustant un total lu pour le faire tomber
juste. C'est la seule manière de rendre cet outil dangereux.

## Étape 4 — Écrire le CSV

```bash
python scripts/verifier.py ecrire releve.json --format formats/bcn.json -o releve_bcn.csv
```

Le fichier de format porte tout ce qui rend un CSV reconnaissable : encodage,
fin de ligne, séparateur, lignes de métadonnées avant l'en-tête, noms exacts
des colonnes dans l'ordre, format des dates, format des montants, sens de
lecture chronologique.

Lis le fichier de format de la banque concernée **avant** d'écrire. S'il porte
`"statut": "a_completer"`, la banque n'a pas encore été mesurée sur un vrai
export : dis-le à l'utilisateur et demande-lui un export CSV réel de cette
banque plutôt que d'inventer des colonnes. Un CSV au format deviné sera rejeté
à l'import, et l'utilisateur perdra plus de temps à comprendre pourquoi qu'il
n'en aurait passé à te fournir le fichier.

## Étape 5 — Rendre compte

Termine par un court récapitulatif, en clair :

- la banque retenue et **sur quelle preuve** (IBAN, logo, ou dire de l'utilisateur)
- le nombre de lignes lues et la période couverte
- les contrôles passés, avec les montants
- ce qui reste incertain, s'il reste quelque chose

L'utilisateur est un comptable : il doit pouvoir tracer d'où vient chaque
chiffre. Le CSV produit est une **transcription**, pas un export d'origine.
Dis-le dans le récapitulatif — mais **pas dans le nom du fichier** : le
logiciel qui l'avalera peut se servir du nom pour reconnaître la banque, et un
suffixe ajouté casserait cette reconnaissance. Le nom suit le gabarit de la
banque ; la provenance se dit en clair à côté.

## Fichiers de format disponibles

| Banque | Fichier | État |
|---|---|---|
| UBS | `formats/ubs.json` | partiel — mesuré sur un export réel, en-têtes à confirmer |
| PostFinance | `formats/postfinance.json` | indicatif — structure connue, mais en allemand et datée de 2017 |
| BCN | `formats/bcn.json` | à compléter — l'export CSV existe, sa structure n'est publiée nulle part |
| BCF | `formats/bcf.json` | **en attente** — faible volume, reprise plus tard |

Seul `"statut": "mesure"` autorise l'écriture. Tous les autres états font refuser
le script, et c'est le point : un format approché produit un fichier rejeté à
l'import, ce qui coûte plus cher à comprendre qu'à éviter.

## Compléter une banque

Un format à l'état `a_completer` ou `indicatif` ne se remplit pas de mémoire.
Il se **mesure**, sur un vrai export CSV de cette banque — celui qui passe déjà
l'import du logiciel comptable de l'utilisateur.

Demande-lui ce fichier, puis :

```bash
python scripts/diagnostic.py "l'export reel.csv"
```

Le diagnostic donne l'encodage, la fin de ligne, le séparateur, le nombre de
lignes de métadonnées avant la table, le nombre de colonnes, ce que contient
chacune, et les pièges — champs contenant le séparateur, sous-lignes,
colonnes irrégulières.

Reporte le tout dans le fichier de format en suivant `formats/_MODELE.json`,
en copiant-collant les noms de colonnes plutôt qu'en les retapant : les
accents, abréviations et espaces comptent. Passe `statut` à `"mesure"`
seulement quand chaque champ vient d'une observation.

Le même diagnostic sert à identifier n'importe quel fichier qu'on te tend en
disant « c'est le CSV » — il refuse proprement les PDF, les classeurs Excel et
les images.

## Fichiers

Pour ajouter une banque ou en compléter une : `formats/_MODELE.json` liste
tout ce qu'il faut mesurer, et sur quel fichier le mesurer.
